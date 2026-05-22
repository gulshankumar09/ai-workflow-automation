"""
Circuit Breaker Pattern Implementation for MCP Servers

This module provides circuit breaker functionality to prevent cascading failures
when MCP servers are unavailable or experiencing issues. It implements the classic
circuit breaker pattern with three states: CLOSED, OPEN, and HALF_OPEN.

Key Features:
- Automatic failure detection and recovery
- Configurable failure thresholds and timeouts
- Fallback mechanism support
- Comprehensive monitoring and logging
- Custom exception handling integration
"""

import asyncio
from builtins import ValueError
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union
from dataclasses import dataclass
from contextlib import asynccontextmanager

from app.shared.exceptions import (
    BaseAppException,
    ExternalServiceException,
    ErrorSeverity
)


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: float = 60.0  # Seconds before attempting recovery
    success_threshold: int = 3  # Successful calls needed to close from half-open
    timeout: float = 30.0  # Operation timeout in seconds
    reset_timeout: float = 300.0  # Time to reset failure count
    
    def __post_init__(self):
        if self.failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if self.recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive")
        if self.success_threshold <= 0:
            raise ValueError("success_threshold must be positive")


class CircuitBreakerException(ExternalServiceException):
    """Exception raised when circuit breaker is open"""
    
    def __init__(
        self,
        message: str = "Circuit breaker is open",
        service_name: Optional[str] = None,
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        enhanced_details = details or {}
        if service_name:
            enhanced_details["service_name"] = service_name
        enhanced_details["circuit_breaker_state"] = "open"
        
        super().__init__(
            message=message,
            correlation_id=correlation_id,
            details=enhanced_details,
            severity=ErrorSeverity.HIGH,
            status_code=503  # Service Unavailable
        )


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting external service calls
    
    The circuit breaker monitors service calls and automatically switches between
    three states based on success/failure patterns:
    
    - CLOSED: Normal operation, all calls pass through
    - OPEN: Service is failing, all calls are blocked and fail fast
    - HALF_OPEN: Testing recovery, limited calls allowed to test service health
    
    Features:
    - Automatic failure detection and recovery
    - Configurable thresholds and timeouts
    - Async/await support
    - Comprehensive logging and monitoring
    - Fallback mechanism integration
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Initialize circuit breaker
        
        Args:
            name: Unique name for this circuit breaker
            config: Circuit breaker configuration
            correlation_id: Request correlation ID
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.correlation_id = correlation_id
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
        # State management
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_success_time: Optional[float] = None
        self._last_reset_time = time.time()
        
        # Monitoring
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0
        self._state_changes: Dict[str, int] = {
            state.value: 0 for state in CircuitBreakerState
        }
        
        self.logger.info(f"Circuit breaker '{name}' initialized in CLOSED state")
    
    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state"""
        return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is in CLOSED state"""
        return self._state == CircuitBreakerState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is in OPEN state"""
        return self._state == CircuitBreakerState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is in HALF_OPEN state"""
        return self._state == CircuitBreakerState.HALF_OPEN
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get circuit breaker statistics
        
        Returns:
            Dictionary with circuit breaker statistics
        """
        current_time = time.time()
        uptime = current_time - self._last_reset_time
        
        success_rate = 0.0
        if self._total_calls > 0:
            success_rate = self._total_successes / self._total_calls
        
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
            "success_rate": success_rate,
            "last_failure_time": self._last_failure_time,
            "last_success_time": self._last_success_time,
            "uptime_seconds": uptime,
            "state_changes": self._state_changes.copy(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout
            }
        }
    
    def reset(self) -> None:
        """
        Reset circuit breaker to CLOSED state and clear counters
        """
        old_state = self._state
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_reset_time = time.time()
        
        if old_state != CircuitBreakerState.CLOSED:
            self._state_changes[CircuitBreakerState.CLOSED.value] += 1
            self.logger.info(f"Circuit breaker '{self.name}' reset to CLOSED state")
    
    def _transition_to_open(self) -> None:
        """Transition circuit breaker to OPEN state"""
        if self._state != CircuitBreakerState.OPEN:
            self._state = CircuitBreakerState.OPEN
            self._state_changes[CircuitBreakerState.OPEN.value] += 1
            self.logger.warning(
                f"Circuit breaker '{self.name}' opened after {self._failure_count} failures"
            )
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit breaker to HALF_OPEN state"""
        if self._state != CircuitBreakerState.HALF_OPEN:
            self._state = CircuitBreakerState.HALF_OPEN
            self._success_count = 0  # Reset success count for half-open testing
            self._state_changes[CircuitBreakerState.HALF_OPEN.value] += 1
            self.logger.info(f"Circuit breaker '{self.name}' entered HALF_OPEN state for testing")
    
    def _transition_to_closed(self) -> None:
        """Transition circuit breaker to CLOSED state"""
        if self._state != CircuitBreakerState.CLOSED:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0  # Reset failure count
            self._state_changes[CircuitBreakerState.CLOSED.value] += 1
            self.logger.info(
                f"Circuit breaker '{self.name}' closed after {self._success_count} successful calls"
            )
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset from OPEN to HALF_OPEN"""
        if self._state != CircuitBreakerState.OPEN:
            return False
        
        if not self._last_failure_time:
            return False
        
        time_since_failure = time.time() - self._last_failure_time
        return time_since_failure >= self.config.recovery_timeout
    
    def _record_success(self) -> None:
        """Record a successful operation"""
        current_time = time.time()
        self._last_success_time = current_time
        self._total_successes += 1
        
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self._state == CircuitBreakerState.CLOSED:
            # Reset failure count after successful operation
            if current_time - self._last_reset_time > self.config.reset_timeout:
                self._failure_count = 0
    
    def _record_failure(self) -> None:
        """Record a failed operation"""
        current_time = time.time()
        self._last_failure_time = current_time
        self._failure_count += 1
        self._total_failures += 1
        
        if self._state == CircuitBreakerState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                self._transition_to_open()
        elif self._state == CircuitBreakerState.HALF_OPEN:
            # Any failure in half-open state immediately opens the circuit
            self._transition_to_open()
    
    def _can_execute(self) -> bool:
        """Check if operation can be executed based on circuit breaker state"""
        if self._state == CircuitBreakerState.CLOSED:
            return True
        elif self._state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function call with circuit breaker protection
        
        Args:
            func: Function to call (can be sync or async)
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerException: If circuit breaker is open
            TimeoutError: If operation times out
            Any exception raised by the function
        """
        self._total_calls += 1
        
        # Check if we can execute
        if not self._can_execute():
            raise CircuitBreakerException(
                f"Circuit breaker '{self.name}' is open",
                service_name=self.name,
                correlation_id=self.correlation_id,
                details={
                    "failure_count": self._failure_count,
                    "last_failure_time": self._last_failure_time,
                    "recovery_timeout": self.config.recovery_timeout
                }
            )
        
        # Execute the function with timeout
        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.timeout
                )
            else:
                result = func(*args, **kwargs)
            
            self._record_success()
            return result
            
        except asyncio.TimeoutError:
            self._record_failure()
            self.logger.error(f"Operation timed out in circuit breaker '{self.name}'")
            raise TimeoutError(f"Operation timed out after {self.config.timeout} seconds")
            
        except Exception as e:
            self._record_failure()
            self.logger.error(f"Operation failed in circuit breaker '{self.name}': {str(e)}")
            raise
    
    @asynccontextmanager
    async def protect(self):
        """
        Context manager for circuit breaker protection
        
        Usage:
            async with circuit_breaker.protect():
                # Protected operation
                result = await some_external_call()
        """
        self._total_calls += 1
        
        # Check if we can execute
        if not self._can_execute():
            raise CircuitBreakerException(
                f"Circuit breaker '{self.name}' is open",
                service_name=self.name,
                correlation_id=self.correlation_id
            )
        
        try:
            yield
            self._record_success()
        except Exception as e:
            self._record_failure()
            raise


class MultiServerCircuitBreaker:
    """
    Manages multiple circuit breakers for different MCP servers
    
    This class provides a centralized way to manage circuit breakers for
    multiple MCP servers, allowing for per-server failure isolation and
    comprehensive monitoring across all services.
    """
    
    def __init__(self, correlation_id: Optional[str] = None):
        """
        Initialize multi-server circuit breaker manager
        
        Args:
            correlation_id: Request correlation ID
        """
        self.correlation_id = correlation_id
        self.logger = logging.getLogger(__name__)
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def add_server(
        self, 
        server_name: str, 
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        Add a circuit breaker for a specific server
        
        Args:
            server_name: Name of the MCP server
            config: Circuit breaker configuration
            
        Returns:
            Created circuit breaker instance
        """
        if server_name in self._breakers:
            self.logger.warning(f"Circuit breaker for '{server_name}' already exists")
            return self._breakers[server_name]
        
        breaker = CircuitBreaker(
            name=server_name,
            config=config,
            correlation_id=self.correlation_id
        )
        self._breakers[server_name] = breaker
        
        self.logger.info(f"Added circuit breaker for server: {server_name}")
        return breaker
    
    def get_breaker(self, server_name: str) -> Optional[CircuitBreaker]:
        """
        Get circuit breaker for a specific server
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            Circuit breaker instance or None if not found
        """
        return self._breakers.get(server_name)
    
    def remove_server(self, server_name: str) -> bool:
        """
        Remove circuit breaker for a specific server
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            True if removed, False if not found
        """
        if server_name in self._breakers:
            del self._breakers[server_name]
            self.logger.info(f"Removed circuit breaker for server: {server_name}")
            return True
        return False
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all circuit breakers
        
        Returns:
            Dictionary with stats for each server
        """
        return {
            server_name: breaker.get_stats()
            for server_name, breaker in self._breakers.items()
        }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get overall health summary for all servers
        
        Returns:
            Health summary with aggregate statistics
        """
        total_servers = len(self._breakers)
        healthy_servers = sum(
            1 for breaker in self._breakers.values() 
            if breaker.is_closed
        )
        degraded_servers = sum(
            1 for breaker in self._breakers.values() 
            if breaker.is_half_open
        )
        unhealthy_servers = sum(
            1 for breaker in self._breakers.values() 
            if breaker.is_open
        )
        
        overall_status = "healthy"
        if unhealthy_servers > 0:
            if unhealthy_servers == total_servers:
                overall_status = "critical"
            else:
                overall_status = "degraded"
        elif degraded_servers > 0:
            overall_status = "degraded"
        
        return {
            "overall_status": overall_status,
            "total_servers": total_servers,
            "healthy_servers": healthy_servers,
            "degraded_servers": degraded_servers,
            "unhealthy_servers": unhealthy_servers,
            "server_details": {
                name: {
                    "status": breaker.state.value,
                    "failure_count": breaker._failure_count,
                    "success_rate": (
                        breaker._total_successes / breaker._total_calls 
                        if breaker._total_calls > 0 else 0.0
                    )
                }
                for name, breaker in self._breakers.items()
            }
        }
    
    def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED state"""
        for breaker in self._breakers.values():
            breaker.reset()
        self.logger.info("Reset all circuit breakers")
    
    async def execute_with_fallback(
        self,
        server_name: str,
        func: Callable,
        fallback_func: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with circuit breaker protection and optional fallback
        
        Args:
            server_name: Name of the MCP server
            func: Function to execute
            fallback_func: Optional fallback function if main function fails
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result or fallback result
        """
        breaker = self.get_breaker(server_name)
        if not breaker:
            # Create circuit breaker if it doesn't exist
            breaker = self.add_server(server_name)
        
        try:
            return await breaker.call(func, *args, **kwargs)
        except (CircuitBreakerException, Exception) as e:
            if fallback_func:
                self.logger.warning(
                    f"Using fallback for server '{server_name}' due to: {str(e)}"
                )
                try:
                    if asyncio.iscoroutinefunction(fallback_func):
                        return await fallback_func(*args, **kwargs)
                    else:
                        return fallback_func(*args, **kwargs)
                except Exception as fallback_error:
                    self.logger.error(
                        f"Fallback also failed for server '{server_name}': {str(fallback_error)}"
                    )
                    raise fallback_error
            else:
                raise 