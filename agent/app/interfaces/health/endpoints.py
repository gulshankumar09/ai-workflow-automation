"""
Health Check Endpoints for ai-workflow-automation Core Microservice.

This module provides HTTP endpoints for health, readiness, and liveness checks
that can be used by orchestrators and monitoring systems.
"""

import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Response, status, Query
from fastapi.responses import JSONResponse

from .health_service import HealthService

logger = logging.getLogger(__name__)


def create_health_endpoints() -> APIRouter:
    """
    Create FastAPI router with health check endpoints.
    
    Returns:
        APIRouter configured with health endpoints
    """
    router = APIRouter(prefix="/health", tags=["health"])
    health_service = HealthService()

    @router.get("/", summary="Overall Health Check")
    async def health_check(
        detailed: bool = Query(False, description="Include detailed component information"),
        response: Response = None
    ) -> Dict[str, Any]:
        """
        Get overall system health status.
        
        This endpoint checks all system components and returns their health status.
        Use this for general monitoring and alerting.
        
        Parameters:
        - detailed: Whether to include detailed metrics and information
        
        Returns:
        - 200: System is healthy
        - 503: System is unhealthy or degraded
        """
        try:
            health_status = await health_service.get_health_status(detailed=detailed)
            
            # Set appropriate HTTP status code
            if health_status["status"] == "healthy":
                response.status_code = status.HTTP_200_OK
            else:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}", exc_info=True)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "unhealthy",
                "error": "Health check failed",
                "details": str(e)
            }

    @router.get("/ready", summary="Readiness Check")
    async def readiness_check(response: Response = None) -> Dict[str, Any]:
        """
        Check if the service is ready to accept requests.
        
        This endpoint is used by orchestrators (like Kubernetes) to determine
        if the service should receive traffic. It checks critical dependencies
        that must be available for the service to function.
        
        Returns:
        - 200: Service is ready
        - 503: Service is not ready
        """
        try:
            readiness_status = await health_service.get_readiness_status()
            
            # Set appropriate HTTP status code
            if readiness_status["ready"]:
                response.status_code = status.HTTP_200_OK
            else:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            
            return readiness_status
            
        except Exception as e:
            logger.error(f"Readiness check failed: {str(e)}", exc_info=True)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "ready": False,
                "error": "Readiness check failed",
                "details": str(e)
            }

    @router.get("/live", summary="Liveness Check")
    async def liveness_check(response: Response = None) -> Dict[str, Any]:
        """
        Check if the service is alive and responsive.
        
        This endpoint is used by orchestrators (like Kubernetes) to determine
        if the service should be restarted. It performs a minimal check to
        verify that the service is responsive and not deadlocked.
        
        Returns:
        - 200: Service is alive
        - 503: Service is not responsive
        """
        try:
            liveness_status = await health_service.get_liveness_status()
            
            # Set appropriate HTTP status code
            if liveness_status["alive"]:
                response.status_code = status.HTTP_200_OK
            else:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            
            return liveness_status
            
        except Exception as e:
            logger.error(f"Liveness check failed: {str(e)}", exc_info=True)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "alive": False,
                "error": "Liveness check failed",
                "details": str(e)
            }

    @router.get("/status", summary="Detailed Service Status")
    async def service_status() -> Dict[str, Any]:
        """
        Get detailed service status and metrics.
        
        This endpoint provides comprehensive information about the service
        including component health, metrics, and configuration. Use this
        for debugging and detailed monitoring.
        
        Returns:
        - 200: Status information (always returns 200)
        """
        try:
            # Get detailed health status
            health_status = await health_service.get_health_status(detailed=True)
            
            # Add additional service information
            service_info = {
                "service": "ai-workflow-automation-core",
                "version": "1.0.0",
                "environment": "development",  # TODO: Get from settings
                "health": health_status,
                "features": {
                    "workflow_generation": True,
                    "workflow_execution": True,
                    "mcp_tools": True,
                    "chat_interface": True,
                    "user_management": True,
                    "real_time_streaming": True
                },
                "endpoints": {
                    "grpc_port": 50051,  # TODO: Get from settings
                    "health_checks": True,
                    "metrics": True
                }
            }
            
            return service_info
            
        except Exception as e:
            logger.error(f"Service status check failed: {str(e)}", exc_info=True)
            return {
                "service": "ai-workflow-automation-core",
                "version": "1.0.0",
                "status": "error",
                "error": str(e)
            }

    @router.get("/components", summary="Component Health Status")
    async def components_health() -> Dict[str, Any]:
        """
        Get health status of individual components.
        
        This endpoint returns the health status of each system component
        separately, useful for component-specific monitoring and alerting.
        
        Returns:
        - 200: Component status information
        """
        try:
            health_status = await health_service.get_health_status(detailed=True)
            
            # Extract just the components
            components = health_status.get("components", {})
            
            return {
                "timestamp": health_status.get("timestamp"),
                "overall_status": health_status.get("status"),
                "components": components
            }
            
        except Exception as e:
            logger.error(f"Components health check failed: {str(e)}", exc_info=True)
            return {
                "error": "Components health check failed",
                "details": str(e)
            }

    @router.get("/metrics", summary="Service Metrics")
    async def service_metrics() -> Dict[str, Any]:
        """
        Get service performance metrics.
        
        This endpoint provides metrics that can be consumed by monitoring
        systems like Prometheus for alerting and dashboards.
        
        Returns:
        - 200: Service metrics
        """
        try:
            health_status = await health_service.get_health_status(detailed=True)
            
            # Extract metrics from health status
            metrics = {}
            for component_name, component in health_status.get("components", {}).items():
                if "metrics" in component:
                    metrics[component_name] = component["metrics"]
            
            # Add service-level metrics
            metrics["service"] = {
                "uptime_seconds": 0,  # TODO: Calculate actual uptime
                "requests_total": 0,  # TODO: Add request counter
                "requests_per_second": 0,  # TODO: Calculate RPS
                "errors_total": 0,  # TODO: Add error counter
                "error_rate": 0.0  # TODO: Calculate error rate
            }
            
            return {
                "timestamp": health_status.get("timestamp"),
                "metrics": metrics
            }
            
        except Exception as e:
            logger.error(f"Service metrics check failed: {str(e)}", exc_info=True)
            return {
                "error": "Service metrics check failed",
                "details": str(e)
            }

    return router


def create_health_app() -> "FastAPI":
    """
    Create a standalone FastAPI app for health checks.
    
    This can be used to run health checks on a separate port
    or as a lightweight health check service.
    
    Returns:
        FastAPI application with health endpoints
    """
    from fastapi import FastAPI
    
    app = FastAPI(
        title="ai-workflow-automation Core Health Checks",
        description="Health check endpoints for ai-workflow-automation Core Microservice",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Include health endpoints
    health_router = create_health_endpoints()
    app.include_router(health_router)
    
    @app.get("/", summary="Health Check Root")
    async def root():
        """Root endpoint that redirects to health check."""
        return {"message": "ai-workflow-automation Core Health Check Service", "health_endpoint": "/health/"}
    
    return app


if __name__ == "__main__":
    # Run standalone health check service
    import uvicorn
    
    app = create_health_app()
    uvicorn.run(app, host="0.0.0.0", port=8080) 