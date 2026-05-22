"""
Main Application Entry Point for ai-workflow-automation Core Microservice.

This module provides the main application setup and startup logic,
including gRPC server, health checks, and service coordination.
"""

import asyncio
import signal
import sys

import uvicorn
from fastapi import FastAPI

from app.shared.config import get_settings
from app.shared.dependency_injection import get_dependency_container
from app.shared.logger import setup_logging
from app.interfaces.grpc.server import create_grpc_server
from app.interfaces.health import create_health_endpoints
from app.interfaces.rest import create_rest_router

# Logger will be initialized after logging setup
logger = None


class VerbilioApplication:
    """
    Main application class for ai-workflow-automation Core Microservice.
    
    Manages the lifecycle of all services including gRPC server,
    health check endpoints, and graceful shutdown.
    """

    def __init__(self):
        self.settings = get_settings()
        self.grpc_server = None
        self.health_app = None
        self.shutdown_event = asyncio.Event()
        
        # Setup logging first, then get logger
        global logger
        logger = setup_logging(log_level="DEBUG", development_mode=self.settings.debug)

    async def start_grpc_server(self):
        """Start the gRPC server."""
        try:
            logger.info("Starting gRPC server...")
            self.grpc_server = await create_grpc_server(self.settings)
            
            # Start the server without blocking
            await self.grpc_server.start_non_blocking()
            logger.info(f"gRPC server started on port {self.settings.grpc_port}")
            
            # Create a task to wait for termination
            grpc_task = asyncio.create_task(self.grpc_server.server.wait_for_termination())
            
            return grpc_task
            
        except Exception as e:
            logger.error(f"Failed to start gRPC server: {str(e)}", exc_info=True)
            raise

    def create_rest_app(self) -> FastAPI:
        """Create the health check FastAPI application."""
        app = FastAPI(
            title="ai-workflow-automation Core API",
            description="REST API and Health endpoints for ai-workflow-automation Core Microservice",
            version="1.0.0",
            # docs_url="/docs" if self.settings.debug else None
            # redoc_url="/redoc" if self.settings.debug else None
            docs_url="/docs"
        )
        
        # Add health endpoints
        health_router = create_health_endpoints()
        app.include_router(health_router)
        
        # Add REST API endpoints
        rest_router = create_rest_router()
        app.include_router(rest_router)
        
        @app.get("/", summary="Service Info")
        async def root():
            """Root endpoint with service information."""
            return {
                "service": self.settings.app_name,
                "version": self.settings.app_version,
                "status": "running",
                "endpoints": {
                    "grpc": f"localhost:{self.settings.grpc_port}",
                    "health": "/health/",
                    "api": "/api/v1/",
                    "docs": "/docs" if self.settings.debug else None
                }
            }
        
        return app

    async def start_health_server(self):
        """Start the REST API and health check HTTP server."""
        try:
            logger.info("Starting REST API and health check server...")
            
            self.health_app = self.create_rest_app()
            
            # Configure uvicorn
            config = uvicorn.Config(
                app=self.health_app,
                host="0.0.0.0",
                port=self.settings.health_port,
                log_level=self.settings.log_level.lower(),
                access_log=self.settings.debug
            )
            
            server = uvicorn.Server(config)
            
            # Start the server in the background
            health_task = asyncio.create_task(server.serve())
            logger.info(f"REST API and health check server started on port {self.settings.health_port}")
            
            return health_task
            
        except Exception as e:
            logger.error(f"Failed to start health check server: {str(e)}", exc_info=True)
            raise

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run(self):
        """Run the complete application."""
        try:
            logger.info("🚀 Starting ai-workflow-automation Core Microservice...")
            
            # Initialize dependency injection container
            logger.info("🔧 Initializing dependency injection container...")
            container = get_dependency_container()
            await container.initialize()
            logger.info("✅ Dependency injection container initialized")
            
            # Setup signal handlers
            self.setup_signal_handlers()
            
            # Start all services
            tasks = []
            
            # Start gRPC server
            grpc_task = await self.start_grpc_server()
            tasks.append(grpc_task)
            
            # Start health check server
            health_task = await self.start_health_server()
            tasks.append(health_task)
            
            logger.info("All services started successfully!")
            logger.info(f"gRPC server: localhost:{self.settings.grpc_port}")
            logger.info(f"REST API: http://localhost:{self.settings.health_port}/api/v1/")
            logger.info(f"Health checks: http://localhost:{self.settings.health_port}/health/")
            
            if self.settings.debug:
                logger.info(f"API docs: http://localhost:{self.settings.health_port}/docs")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            # Graceful shutdown
            await self.shutdown(tasks)
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
            await self.shutdown(tasks)
        except Exception as e:
            logger.error(f"Application error: {str(e)}", exc_info=True)
            await self.shutdown(tasks)
            raise

    async def shutdown(self, tasks: list):
        """Gracefully shutdown all services."""
        logger.info("🛑 Shutting down services...")
        
        try:
            # Stop gRPC server
            if self.grpc_server:
                await self.grpc_server.stop(grace_period=5.0)
                logger.info("✅ gRPC server stopped")
            
            # Cancel all tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            logger.info("✅ All services stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}", exc_info=True)


async def main():
    """Main entry point."""
    try:
        app = VerbilioApplication()
        await app.run()
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        return 1
    
    return 0


def run_app():
    """Synchronous entry point for running the application."""
    try:
        return asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Application failed: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(run_app()) 