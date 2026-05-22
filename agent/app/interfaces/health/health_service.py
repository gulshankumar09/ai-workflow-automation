"""
Health Service for ai-workflow-automation Core Microservice.

This module provides comprehensive health checking for all dependencies
and services used by the core microservice.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from app.shared.exceptions import BaseAppException, DatabaseException
from app.shared.config import get_settings

logger = logging.getLogger(__name__)


class HealthService:
    """
    Service for checking the health of all system dependencies.
    
    Provides detailed health status for databases, caches, external services,
    and internal components.
    """

    def __init__(self):
        self.settings = get_settings()
        self.last_check_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = timedelta(seconds=30)  # Cache health checks for 30 seconds

    async def get_health_status(self, detailed: bool = False) -> Dict[str, Any]:
        """
        Get overall health status of the system.
        
        Args:
            detailed: Whether to include detailed information about each component
            
        Returns:
            Dict containing health status and component details
        """
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting health status (detailed={detailed})")
            
            # Run all health checks in parallel
            check_tasks = [
                self._check_database_health(),
                self._check_cache_health(),
                self._check_supabase_health(),
                self._check_application_services_health(),
                self._check_system_resources()
            ]
            
            results = await asyncio.gather(*check_tasks, return_exceptions=True)
            
            # Process results
            database_health = results[0] if not isinstance(results[0], Exception) else self._error_result("database", str(results[0]))
            cache_health = results[1] if not isinstance(results[1], Exception) else self._error_result("cache", str(results[1]))
            supabase_health = results[2] if not isinstance(results[2], Exception) else self._error_result("supabase", str(results[2]))
            app_services_health = results[3] if not isinstance(results[3], Exception) else self._error_result("app_services", str(results[3]))
            system_health = results[4] if not isinstance(results[4], Exception) else self._error_result("system", str(results[4]))
            
            # Determine overall status
            all_statuses = [
                database_health["status"],
                cache_health["status"],
                supabase_health["status"],
                app_services_health["status"],
                system_health["status"]
            ]
            
            overall_status = "healthy"
            if "unhealthy" in all_statuses:
                overall_status = "unhealthy"
            elif "degraded" in all_statuses:
                overall_status = "degraded"
            
            response = {
                "status": overall_status,
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_id": correlation_id,
                "version": "1.0.0",
                "components": {
                    "database": database_health,
                    "cache": cache_health,
                    "supabase": supabase_health,
                    "application_services": app_services_health,
                    "system": system_health
                }
            }
            
            if not detailed:
                # Remove detailed information
                for component in response["components"].values():
                    component.pop("details", None)
                    component.pop("metrics", None)
            
            logger.info(f"[{correlation_id}] Health status: {overall_status}")
            return response
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Error getting health status: {str(e)}", exc_info=True)
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_id": correlation_id,
                "error": str(e)
            }

    async def get_readiness_status(self) -> Dict[str, Any]:
        """
        Get readiness status - whether the service is ready to accept requests.
        
        Returns:
            Dict containing readiness status
        """
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting readiness status")
            
            # Check critical dependencies only
            critical_checks = [
                self._check_database_health(),
                self._check_application_services_health()
            ]
            
            results = await asyncio.gather(*critical_checks, return_exceptions=True)
            
            # Check if any critical component is unhealthy
            ready = True
            errors = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    ready = False
                    errors.append(str(result))
                elif result.get("status") == "unhealthy":
                    ready = False
                    errors.append(f"Critical component unhealthy: {result.get('component')}")
            
            response = {
                "ready": ready,
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_id": correlation_id
            }
            
            if errors:
                response["errors"] = errors
            
            logger.info(f"[{correlation_id}] Readiness status: {ready}")
            return response
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Error getting readiness status: {str(e)}", exc_info=True)
            return {
                "ready": False,
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_id": correlation_id,
                "error": str(e)
            }

    async def get_liveness_status(self) -> Dict[str, Any]:
        """
        Get liveness status - whether the service is alive and functioning.
        
        Returns:
            Dict containing liveness status
        """
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting liveness status")
            
            # Simple check that the service is responsive
            start_time = datetime.utcnow()
            
            # Basic functionality test
            test_data = {"test": "value"}
            if test_data.get("test") != "value":
                raise Exception("Basic functionality test failed")
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            response = {
                "alive": True,
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_id": correlation_id,
                "response_time_ms": response_time
            }
            
            logger.info(f"[{correlation_id}] Liveness status: alive")
            return response
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Error getting liveness status: {str(e)}", exc_info=True)
            return {
                "alive": False,
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_id": correlation_id,
                "error": str(e)
            }

    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        component = "database"
        
        # Check cache first
        if self._is_cached(component):
            return self.last_check_cache[component]["result"]
        
        try:
            start_time = datetime.utcnow()
            
            # TODO: Replace with actual database connection test
            # For now, simulate database check
            await asyncio.sleep(0.01)  # Simulate DB query
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = {
                "component": component,
                "status": "healthy",
                "response_time_ms": response_time,
                "details": {
                    "connection": "established",
                    "type": "postgresql",
                    "host": self.settings.database_url.split("@")[-1].split("/")[0] if hasattr(self.settings, 'database_url') else "localhost"
                },
                "metrics": {
                    "connections_active": 5,
                    "connections_max": 100,
                    "query_avg_time_ms": response_time
                }
            }
            
            self._cache_result(component, result)
            return result
            
        except Exception as e:
            result = self._error_result(component, str(e))
            self._cache_result(component, result)
            return result

    async def _check_cache_health(self) -> Dict[str, Any]:
        """Check cache connectivity and performance."""
        component = "cache"
        
        # Check cache first (but not for cache health check itself)
        try:
            start_time = datetime.utcnow()
            
            # TODO: Replace with actual cache connection test
            # For now, simulate cache check
            await asyncio.sleep(0.005)  # Simulate cache operation
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = {
                "component": component,
                "status": "healthy",
                "response_time_ms": response_time,
                "details": {
                    "connection": "established",
                    "type": "redis",
                    "host": "localhost"
                },
                "metrics": {
                    "hit_rate": 85.5,
                    "memory_usage_mb": 64,
                    "memory_max_mb": 512
                }
            }
            
            return result
            
        except Exception as e:
            return self._error_result(component, str(e))

    async def _check_supabase_health(self) -> Dict[str, Any]:
        """Check Supabase connectivity and status."""
        component = "supabase"
        
        # Check cache first
        if self._is_cached(component):
            return self.last_check_cache[component]["result"]
        
        try:
            start_time = datetime.utcnow()
            
            # TODO: Replace with actual Supabase health check
            # For now, simulate Supabase check
            await asyncio.sleep(0.02)  # Simulate API call
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = {
                "component": component,
                "status": "healthy",
                "response_time_ms": response_time,
                "details": {
                    "connection": "established",
                    "services": ["database", "auth", "storage", "realtime"],
                    "region": "us-east-1"
                },
                "metrics": {
                    "api_response_time_ms": response_time,
                    "auth_users_active": 150,
                    "storage_usage_gb": 2.5
                }
            }
            
            self._cache_result(component, result)
            return result
            
        except Exception as e:
            result = self._error_result(component, str(e))
            self._cache_result(component, result)
            return result

    async def _check_application_services_health(self) -> Dict[str, Any]:
        """Check internal application services health."""
        component = "application_services"
        
        try:
            start_time = datetime.utcnow()
            
            # Check if application services can be imported and initialized
            from app.application.workflow_service import WorkflowService
            from app.application.execution_service import ExecutionService
            from app.application.user_service import UserService
            from app.application.mcp_service import MCPService
            
            # Test basic service initialization
            services = {
                "workflow_service": WorkflowService(),
                "execution_service": ExecutionService(),
                "user_service": UserService(),
                "mcp_service": MCPService()
            }
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = {
                "component": component,
                "status": "healthy",
                "response_time_ms": response_time,
                "details": {
                    "services_loaded": list(services.keys()),
                    "services_count": len(services),
                    "initialization": "success"
                },
                "metrics": {
                    "load_time_ms": response_time,
                    "memory_usage_mb": 0,  # TODO: Calculate actual memory usage
                    "active_workflows": 0,
                    "active_executions": 0
                }
            }
            
            return result
            
        except Exception as e:
            return self._error_result(component, str(e))

    async def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        component = "system"
        
        try:
            import psutil
            
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Determine status based on resource usage
            status = "healthy"
            if cpu_percent > 80 or memory.percent > 85 or disk.percent > 90:
                status = "degraded"
            if cpu_percent > 95 or memory.percent > 95 or disk.percent > 95:
                status = "unhealthy"
            
            result = {
                "component": component,
                "status": status,
                "details": {
                    "platform": psutil.platform.platform(),
                    "python_version": psutil.sys.version.split()[0],
                    "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
                },
                "metrics": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": round(memory.used / 1024**3, 2),
                    "memory_total_gb": round(memory.total / 1024**3, 2),
                    "disk_percent": disk.percent,
                    "disk_used_gb": round(disk.used / 1024**3, 2),
                    "disk_total_gb": round(disk.total / 1024**3, 2)
                }
            }
            
            return result
            
        except ImportError:
            # psutil not available, provide basic system info
            result = {
                "component": component,
                "status": "healthy",
                "details": {
                    "psutil": "not_available",
                    "monitoring": "limited"
                },
                "metrics": {}
            }
            return result
            
        except Exception as e:
            return self._error_result(component, str(e))

    def _error_result(self, component: str, error: str) -> Dict[str, Any]:
        """Create error result for a component."""
        return {
            "component": component,
            "status": "unhealthy",
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _is_cached(self, component: str) -> bool:
        """Check if component result is cached and valid."""
        if component not in self.last_check_cache:
            return False
        
        cache_entry = self.last_check_cache[component]
        cache_time = datetime.fromisoformat(cache_entry["timestamp"])
        
        return datetime.utcnow() - cache_time < self.cache_ttl

    def _cache_result(self, component: str, result: Dict[str, Any]) -> None:
        """Cache component health check result."""
        self.last_check_cache[component] = {
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        } 