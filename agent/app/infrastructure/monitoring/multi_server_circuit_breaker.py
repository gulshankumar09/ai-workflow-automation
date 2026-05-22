"""
Enhanced Multi-Server Circuit Breaker System

This module provides an enhanced circuit breaker system specifically designed for
multi-server MCP environments with intelligent fallback mechanisms, alternative
tool suggestions, and comprehensive monitoring capabilities.

Key Features:
- Per-server circuit breaker isolation
- Intelligent fallback mechanisms
- Alternative tool suggestions
- Server health scoring and ranking
- Adaptive threshold management
- Comprehensive monitoring and analytics
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from statistics import mean, median

from app.shared.exceptions import (
    ExternalServiceException,
    ConfigurationException,
    ErrorSeverity
)
from app.infrastructure.monitoring.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerConfig,
    CircuitBreakerException
)


class ServerHealthStatus(Enum):
    """Server health status levels"""
    EXCELLENT = "excellent"    # 0-5% failure rate
    GOOD = "good"             # 5-15% failure rate
    DEGRADED = "degraded"     # 15-35% failure rate
    POOR = "poor"             # 35-60% failure rate
    CRITICAL = "critical"     # 60%+ failure rate
    OFFLINE = "offline"       # Circuit breaker open


class FallbackStrategy(Enum):
    """Fallback strategies for failed operations"""
    ALTERNATIVE_SERVER = "alternative_server"
    CACHED_RESPONSE = "cached_response"
    DEGRADED_SERVICE = "degraded_service"
    MANUAL_INTERVENTION = "manual_intervention"
    FAIL_FAST = "fail_fast"


@dataclass
class ServerMetrics:
    """Health and performance metrics for a server"""
    server_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_success_time: Optional[float] = None
    last_failure_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    health_score: float = 100.0
    
    # Performance tracking
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    recent_failures: deque = field(default_factory=lambda: deque(maxlen=50))
    
    @property
    def failure_rate(self) -> float:
        """Calculate current failure rate"""
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100
    
    @property
    def success_rate(self) -> float:
        """Calculate current success rate"""
        return 100.0 - self.failure_rate
    
    @property
    def health_status(self) -> ServerHealthStatus:
        """Determine health status based on metrics"""
        failure_rate = self.failure_rate
        
        if failure_rate == 0 and self.total_requests > 0:
            return ServerHealthStatus.EXCELLENT
        elif failure_rate <= 5:
            return ServerHealthStatus.EXCELLENT
        elif failure_rate <= 15:
            return ServerHealthStatus.GOOD
        elif failure_rate <= 35:
            return ServerHealthStatus.DEGRADED
        elif failure_rate <= 60:
            return ServerHealthStatus.POOR
        else:
            return ServerHealthStatus.CRITICAL
    
    def update_success(self, response_time: float) -> None:
        """Update metrics for successful operation"""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = time.time()
        
        # Update response time tracking
        self.response_times.append(response_time)
        if self.response_times:
            self.avg_response_time = mean(self.response_times)
        
        # Update health score (improve on success)
        self.health_score = min(100.0, self.health_score + 1.0)
    
    def update_failure(self, error_info: Optional[Dict[str, Any]] = None) -> None:
        """Update metrics for failed operation"""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()
        
        # Track recent failures
        failure_entry = {
            "timestamp": time.time(),
            "error_info": error_info or {}
        }
        self.recent_failures.append(failure_entry)
        
        # Update health score (degrade on failure)
        penalty = min(10.0, self.consecutive_failures * 2.0)
        self.health_score = max(0.0, self.health_score - penalty)


@dataclass
class AlternativeToolSuggestion:
    """Suggestion for alternative tool when primary fails"""
    original_tool: str
    alternative_server: str
    alternative_tool: str
    confidence_score: float
    reason: str
    compatibility_notes: Optional[str] = None


@dataclass
class FallbackResult:
    """Result of fallback operation"""
    strategy: FallbackStrategy
    success: bool
    data: Optional[Dict[str, Any]] = None
    alternative_used: Optional[str] = None
    execution_time: float = 0.0
    notes: Optional[str] = None


class EnhancedMultiServerCircuitBreaker:
    """
    Enhanced circuit breaker system for multi-server MCP environments
    
    This system provides intelligent circuit breaker management across multiple
    MCP servers with advanced features like health scoring, fallback mechanisms,
    alternative tool suggestions, and adaptive threshold management.
    
    Features:
    - Per-server circuit breaker isolation
    - Real-time health scoring and monitoring
    - Intelligent fallback strategies
    - Alternative tool discovery and suggestion
    - Adaptive threshold management
    - Performance analytics and reporting
    """
    
    def __init__(
        self,
        default_config: Optional[CircuitBreakerConfig] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Initialize the Enhanced Multi-Server Circuit Breaker
        
        Args:
            default_config: Default circuit breaker configuration
            correlation_id: Request correlation ID
        """
        self.default_config = default_config or CircuitBreakerConfig()
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.logger = logging.getLogger(__name__)
        
        # Circuit breaker management
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.server_configs: Dict[str, CircuitBreakerConfig] = {}
        
        # Health and performance tracking
        self.server_metrics: Dict[str, ServerMetrics] = {}
        self.tool_capabilities: Dict[str, Set[str]] = defaultdict(set)  # server -> tools
        self.tool_alternatives: Dict[str, List[AlternativeToolSuggestion]] = defaultdict(list)
        
        # Fallback mechanisms
        self.fallback_cache: Dict[str, Dict[str, Any]] = {}
        self.fallback_strategies: Dict[str, FallbackStrategy] = {}
        
        # Analytics
        self.operation_history: deque = deque(maxlen=1000)
        self.fallback_history: deque = deque(maxlen=500)
        
        # Configuration
        self.health_check_interval = 30.0  # seconds
        self.cache_ttl = 300.0  # 5 minutes
        self.adaptive_thresholds_enabled = True
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._start_background_tasks()
    
    def _start_background_tasks(self) -> None:
        """Start background monitoring tasks"""
        # Health monitoring task
        health_task = asyncio.create_task(self._health_monitoring_loop())
        self._background_tasks.add(health_task)
        health_task.add_done_callback(self._background_tasks.discard)
        
        # Adaptive threshold adjustment task
        adaptive_task = asyncio.create_task(self._adaptive_threshold_loop())
        self._background_tasks.add(adaptive_task)
        adaptive_task.add_done_callback(self._background_tasks.discard)
    
    def register_server(
        self,
        server_name: str,
        tools: List[str],
        config: Optional[CircuitBreakerConfig] = None,
        fallback_strategy: FallbackStrategy = FallbackStrategy.ALTERNATIVE_SERVER
    ) -> None:
        """
        Register a new MCP server
        
        Args:
            server_name: Name of the server
            tools: List of tools provided by the server
            config: Optional custom circuit breaker configuration
            fallback_strategy: Fallback strategy for this server
        """
        try:
            # Create circuit breaker for server
            server_config = config or self.default_config
            self.circuit_breakers[server_name] = CircuitBreaker(server_config)
            self.server_configs[server_name] = server_config
            
            # Initialize server metrics
            self.server_metrics[server_name] = ServerMetrics(server_name=server_name)
            
            # Register tool capabilities
            self.tool_capabilities[server_name] = set(tools)
            
            # Set fallback strategy
            self.fallback_strategies[server_name] = fallback_strategy
            
            # Discover alternative tools
            self._discover_tool_alternatives()
            
            self.logger.info(
                f"Registered server '{server_name}' with {len(tools)} tools "
                f"and {fallback_strategy.value} fallback strategy"
            )
            
        except Exception as e:
            raise ConfigurationException(
                f"Failed to register server '{server_name}': {str(e)}",
                correlation_id=self.correlation_id,
                details={"server_name": server_name, "tools": tools}
            )
    
    async def execute_with_fallback(
        self,
        server_name: str,
        tool_name: str,
        operation: Callable,
        *args,
        **kwargs
    ) -> Tuple[Any, Optional[FallbackResult]]:
        """
        Execute operation with intelligent fallback mechanisms
        
        Args:
            server_name: Target server name
            tool_name: Tool to execute
            operation: Operation function to execute
            *args: Operation arguments
            **kwargs: Operation keyword arguments
            
        Returns:
            Tuple of (result, fallback_result)
        """
        start_time = time.time()
        fallback_result = None
        
        try:
            # Check if server is registered
            if server_name not in self.circuit_breakers:
                raise ConfigurationException(
                    f"Server '{server_name}' not registered",
                    correlation_id=self.correlation_id
                )
            
            circuit_breaker = self.circuit_breakers[server_name]
            server_metrics = self.server_metrics[server_name]
            
            # Try primary operation
            try:
                result = await circuit_breaker.call(operation, *args, **kwargs)
                
                # Update success metrics
                execution_time = time.time() - start_time
                server_metrics.update_success(execution_time)
                
                # Cache successful result
                cache_key = f"{server_name}:{tool_name}:{hash(str(args) + str(kwargs))}"
                self.fallback_cache[cache_key] = {
                    "result": result,
                    "timestamp": time.time(),
                    "server": server_name,
                    "tool": tool_name
                }
                
                self._record_operation(server_name, tool_name, True, execution_time)
                return result, fallback_result
                
            except CircuitBreakerException as e:
                # Circuit breaker is open, try fallback
                self.logger.warning(f"Circuit breaker open for '{server_name}', attempting fallback")
                
                server_metrics.update_failure({"error": str(e), "type": "circuit_breaker"})
                fallback_result = await self._execute_fallback(server_name, tool_name, operation, *args, **kwargs)
                
                if fallback_result.success:
                    self._record_operation(server_name, tool_name, True, fallback_result.execution_time, True)
                    return fallback_result.data, fallback_result
                else:
                    self._record_operation(server_name, tool_name, False, time.time() - start_time, True)
                    raise ExternalServiceException(
                        f"Primary and fallback operations failed for '{server_name}:{tool_name}'",
                        correlation_id=self.correlation_id,
                        details={"fallback_result": fallback_result.__dict__}
                    )
            
        except Exception as e:
            # Update failure metrics
            execution_time = time.time() - start_time
            if server_name in self.server_metrics:
                self.server_metrics[server_name].update_failure({"error": str(e), "type": type(e).__name__})
            
            self._record_operation(server_name, tool_name, False, execution_time)
            raise
    
    async def _execute_fallback(
        self,
        server_name: str,
        tool_name: str,
        operation: Callable,
        *args,
        **kwargs
    ) -> FallbackResult:
        """
        Execute fallback strategy for failed operation
        
        Args:
            server_name: Failed server name
            tool_name: Failed tool name
            operation: Original operation
            *args: Operation arguments
            **kwargs: Operation keyword arguments
            
        Returns:
            Fallback result
        """
        start_time = time.time()
        strategy = self.fallback_strategies.get(server_name, FallbackStrategy.FAIL_FAST)
        
        try:
            if strategy == FallbackStrategy.ALTERNATIVE_SERVER:
                return await self._try_alternative_server(tool_name, operation, *args, **kwargs)
            
            elif strategy == FallbackStrategy.CACHED_RESPONSE:
                return await self._try_cached_response(server_name, tool_name, *args, **kwargs)
            
            elif strategy == FallbackStrategy.DEGRADED_SERVICE:
                return await self._try_degraded_service(server_name, tool_name, *args, **kwargs)
            
            elif strategy == FallbackStrategy.MANUAL_INTERVENTION:
                return FallbackResult(
                    strategy=strategy,
                    success=False,
                    notes="Manual intervention required"
                )
            
            else:  # FAIL_FAST
                return FallbackResult(
                    strategy=strategy,
                    success=False,
                    notes="Fail fast strategy - no fallback attempted"
                )
                
        except Exception as e:
            return FallbackResult(
                strategy=strategy,
                success=False,
                execution_time=time.time() - start_time,
                notes=f"Fallback failed: {str(e)}"
            )
    
    async def _try_alternative_server(
        self,
        tool_name: str,
        operation: Callable,
        *args,
        **kwargs
    ) -> FallbackResult:
        """Try executing tool on alternative server"""
        start_time = time.time()
        
        # Find alternative servers for this tool
        alternative_servers = []
        for server, tools in self.tool_capabilities.items():
            if tool_name in tools and self._is_server_healthy(server):
                alternative_servers.append(server)
        
        if not alternative_servers:
            return FallbackResult(
                strategy=FallbackStrategy.ALTERNATIVE_SERVER,
                success=False,
                notes=f"No healthy alternative servers found for tool '{tool_name}'"
            )
        
        # Sort by health score
        alternative_servers.sort(
            key=lambda s: self.server_metrics[s].health_score,
            reverse=True
        )
        
        # Try each alternative server
        for alt_server in alternative_servers:
            try:
                alt_circuit_breaker = self.circuit_breakers[alt_server]
                result = await alt_circuit_breaker.call(operation, *args, **kwargs)
                
                # Update success metrics for alternative server
                execution_time = time.time() - start_time
                self.server_metrics[alt_server].update_success(execution_time)
                
                return FallbackResult(
                    strategy=FallbackStrategy.ALTERNATIVE_SERVER,
                    success=True,
                    data=result,
                    alternative_used=alt_server,
                    execution_time=execution_time,
                    notes=f"Successfully executed on alternative server '{alt_server}'"
                )
                
            except Exception as e:
                self.server_metrics[alt_server].update_failure({"error": str(e)})
                continue
        
        return FallbackResult(
            strategy=FallbackStrategy.ALTERNATIVE_SERVER,
            success=False,
            execution_time=time.time() - start_time,
            notes="All alternative servers failed"
        )
    
    async def _try_cached_response(
        self,
        server_name: str,
        tool_name: str,
        *args,
        **kwargs
    ) -> FallbackResult:
        """Try returning cached response"""
        cache_key = f"{server_name}:{tool_name}:{hash(str(args) + str(kwargs))}"
        
        if cache_key in self.fallback_cache:
            cached_entry = self.fallback_cache[cache_key]
            cache_age = time.time() - cached_entry["timestamp"]
            
            if cache_age <= self.cache_ttl:
                return FallbackResult(
                    strategy=FallbackStrategy.CACHED_RESPONSE,
                    success=True,
                    data=cached_entry["result"],
                    notes=f"Returned cached response (age: {cache_age:.1f}s)"
                )
        
        return FallbackResult(
            strategy=FallbackStrategy.CACHED_RESPONSE,
            success=False,
            notes="No valid cached response found"
        )
    
    async def _try_degraded_service(
        self,
        server_name: str,
        tool_name: str,
        *args,
        **kwargs
    ) -> FallbackResult:
        """Try providing degraded service response"""
        # This is a placeholder for degraded service logic
        # In practice, this would provide simplified/reduced functionality
        
        degraded_response = {
            "status": "degraded",
            "message": f"Service '{tool_name}' on '{server_name}' is temporarily unavailable",
            "available_alternatives": self._get_tool_alternatives(tool_name),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return FallbackResult(
            strategy=FallbackStrategy.DEGRADED_SERVICE,
            success=True,
            data=degraded_response,
            notes="Provided degraded service response"
        )
    
    def _is_server_healthy(self, server_name: str) -> bool:
        """Check if server is healthy enough for fallback"""
        if server_name not in self.server_metrics:
            return False
        
        metrics = self.server_metrics[server_name]
        circuit_breaker = self.circuit_breakers[server_name]
        
        # Check circuit breaker state
        if circuit_breaker.state == CircuitBreakerState.OPEN:
            return False
        
        # Check health score and failure rate
        return (metrics.health_score > 50.0 and 
                metrics.failure_rate < 30.0 and
                metrics.consecutive_failures < 5)
    
    def _discover_tool_alternatives(self) -> None:
        """Discover and map tool alternatives across servers"""
        # Clear existing alternatives
        self.tool_alternatives.clear()
        
        # Build tool->servers mapping
        tool_servers = defaultdict(list)
        for server, tools in self.tool_capabilities.items():
            for tool in tools:
                tool_servers[tool].append(server)
        
        # Create alternative suggestions
        for tool, servers in tool_servers.items():
            if len(servers) > 1:  # Multiple servers provide this tool
                # Sort servers by health score
                sorted_servers = sorted(
                    servers,
                    key=lambda s: self.server_metrics.get(s, ServerMetrics(s)).health_score,
                    reverse=True
                )
                
                # Create suggestions for each server
                for i, primary_server in enumerate(sorted_servers):
                    alternatives = []
                    for j, alt_server in enumerate(sorted_servers):
                        if alt_server != primary_server:
                            confidence = max(0.1, 1.0 - (j * 0.2))  # Decrease confidence for lower-ranked servers
                            suggestion = AlternativeToolSuggestion(
                                original_tool=tool,
                                alternative_server=alt_server,
                                alternative_tool=tool,  # Same tool, different server
                                confidence_score=confidence,
                                reason=f"Alternative server for {tool}",
                                compatibility_notes="Identical tool on different server"
                            )
                            alternatives.append(suggestion)
                    
                    key = f"{primary_server}:{tool}"
                    self.tool_alternatives[key] = alternatives
    
    def _get_tool_alternatives(self, tool_name: str) -> List[Dict[str, Any]]:
        """Get alternative suggestions for a tool"""
        alternatives = []
        
        for key, suggestions in self.tool_alternatives.items():
            if key.endswith(f":{tool_name}"):
                for suggestion in suggestions:
                    alternatives.append({
                        "server": suggestion.alternative_server,
                        "tool": suggestion.alternative_tool,
                        "confidence": suggestion.confidence_score,
                        "reason": suggestion.reason
                    })
        
        return alternatives
    
    def _record_operation(
        self,
        server_name: str,
        tool_name: str,
        success: bool,
        execution_time: float,
        used_fallback: bool = False
    ) -> None:
        """Record operation for analytics"""
        operation_record = {
            "timestamp": time.time(),
            "server_name": server_name,
            "tool_name": tool_name,
            "success": success,
            "execution_time": execution_time,
            "used_fallback": used_fallback,
            "correlation_id": self.correlation_id
        }
        
        self.operation_history.append(operation_record)
        
        if used_fallback:
            self.fallback_history.append(operation_record)
    
    async def _health_monitoring_loop(self) -> None:
        """Background health monitoring loop"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._update_server_health_scores()
                await self._cleanup_expired_cache()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitoring error: {str(e)}")
    
    async def _adaptive_threshold_loop(self) -> None:
        """Background adaptive threshold adjustment loop"""
        while True:
            try:
                await asyncio.sleep(60.0)  # Run every minute
                
                if self.adaptive_thresholds_enabled:
                    await self._adjust_adaptive_thresholds()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Adaptive threshold adjustment error: {str(e)}")
    
    async def _update_server_health_scores(self) -> None:
        """Update health scores for all servers"""
        for server_name, metrics in self.server_metrics.items():
            # Decay health score over time if no recent activity
            if metrics.last_success_time:
                time_since_success = time.time() - metrics.last_success_time
                if time_since_success > 300:  # 5 minutes
                    decay_factor = min(0.99, 1.0 - (time_since_success / 3600))  # Decay over 1 hour
                    metrics.health_score *= decay_factor
    
    async def _adjust_adaptive_thresholds(self) -> None:
        """Adjust circuit breaker thresholds based on server performance"""
        for server_name, metrics in self.server_metrics.items():
            if metrics.total_requests < 10:  # Not enough data
                continue
            
            circuit_breaker = self.circuit_breakers[server_name]
            config = self.server_configs[server_name]
            
            # Adjust failure threshold based on server performance
            if metrics.failure_rate < 5:  # Very reliable server
                new_threshold = min(config.failure_threshold + 1, 10)
            elif metrics.failure_rate > 30:  # Unreliable server
                new_threshold = max(config.failure_threshold - 1, 3)
            else:
                continue  # No adjustment needed
            
            # Update configuration
            config.failure_threshold = new_threshold
            circuit_breaker.config = config
            
            self.logger.debug(
                f"Adjusted failure threshold for '{server_name}' to {new_threshold} "
                f"(failure rate: {metrics.failure_rate:.1f}%)"
            )
    
    async def _cleanup_expired_cache(self) -> None:
        """Cleanup expired cache entries"""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.fallback_cache.items():
            if current_time - entry["timestamp"] > self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.fallback_cache[key]
        
        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_server_health_report(self) -> Dict[str, Any]:
        """Get comprehensive server health report"""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_servers": len(self.server_metrics),
            "servers": {}
        }
        
        for server_name, metrics in self.server_metrics.items():
            circuit_breaker = self.circuit_breakers[server_name]
            
            server_report = {
                "health_status": metrics.health_status.value,
                "health_score": metrics.health_score,
                "circuit_breaker_state": circuit_breaker.state.value,
                "total_requests": metrics.total_requests,
                "failure_rate": metrics.failure_rate,
                "success_rate": metrics.success_rate,
                "avg_response_time": metrics.avg_response_time,
                "consecutive_failures": metrics.consecutive_failures,
                "consecutive_successes": metrics.consecutive_successes,
                "tools": list(self.tool_capabilities.get(server_name, [])),
                "fallback_strategy": self.fallback_strategies.get(server_name, FallbackStrategy.FAIL_FAST).value
            }
            
            report["servers"][server_name] = server_report
        
        return report
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get analytics summary"""
        total_operations = len(self.operation_history)
        fallback_operations = len(self.fallback_history)
        
        if total_operations == 0:
            return {
                "total_operations": 0,
                "fallback_rate": 0.0,
                "success_rate": 0.0,
                "avg_execution_time": 0.0
            }
        
        successful_operations = sum(1 for op in self.operation_history if op["success"])
        total_execution_time = sum(op["execution_time"] for op in self.operation_history)
        
        return {
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "failed_operations": total_operations - successful_operations,
            "success_rate": (successful_operations / total_operations) * 100,
            "fallback_operations": fallback_operations,
            "fallback_rate": (fallback_operations / total_operations) * 100,
            "avg_execution_time": total_execution_time / total_operations,
            "operations_last_hour": len([
                op for op in self.operation_history
                if time.time() - op["timestamp"] <= 3600
            ])
        }
    
    async def cleanup(self) -> None:
        """Cleanup resources and stop background tasks"""
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        self.logger.info("Enhanced Multi-Server Circuit Breaker cleaned up") 