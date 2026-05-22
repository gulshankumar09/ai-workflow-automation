"""
gRPC Server setup for ai-workflow-automation Core Microservice.

This module provides the main gRPC server configuration and setup,
including service registration, middleware, and error handling.
"""

import asyncio
from app.shared.logger import get_logger
from typing import Optional
from contextlib import asynccontextmanager

import grpc
from grpc import aio
from grpc_reflection.v1alpha import reflection

from app.shared.exceptions import BaseAppException
from app.shared.config import Settings
from app.shared.dependency_injection import get_dependency_container
from .handlers.chat_handler import ChatHandler
from .handlers.user_handler import UserHandler

try:
    from .protos import chat_pb2_grpc
    from .protos import user_pb2_grpc
except ImportError:
    # Fallback for development - these will be generated during build
    chat_pb2_grpc = None
    user_pb2_grpc = None


logger = get_logger(__name__)


class VerbilioGRPCServer:
    """
    Main gRPC server for ai-workflow-automation Core Microservice.
    
    Handles service registration, middleware setup, and server lifecycle.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.server: Optional[aio.Server] = None


    async def _create_server(self) -> aio.Server:
        """Create and configure the gRPC server."""
        # Create server with custom options
        options = [
            ('grpc.keepalive_time_ms', 30000),
            ('grpc.keepalive_timeout_ms', 5000),
            ('grpc.keepalive_permit_without_calls', True),
            ('grpc.http2.max_pings_without_data', 0),
            ('grpc.http2.min_time_between_pings_ms', 10000),
            ('grpc.http2.min_ping_interval_without_data_ms', 300000),
            ('grpc.default_max_receive_message_length', -1),
            ('grpc.default_max_send_message_length', 4 * 1024 * 1024),
        ]
        
        server = aio.server(options=options)

        # Register error interceptor (temporarily disabled due to API compatibility)
        # server = self._add_error_interceptor(server)

        # Register all service handlers
        await self._register_services(server)

        # Add reflection service for development
        # if self.settings.debug:
        #     # Get all service names for reflection
        #     service_names = [
        #         'ai-workflow-automation.execution.v1.ExecutionService',
        #         'ai-workflow-automation.chat.ChatService',
        #         'ai-workflow-automation.workflow.v1.WorkflowService',
        #         'ai-workflow-automation.user.UserService',
        #         reflection.SERVICE_NAME,
        #     ]
        #     reflection.enable_server_reflection(service_names, server)
        #     logger.info("gRPC reflection enabled for development", service_names=service_names)

        # Configure server address
        listen_addr = f"[::]:{self.settings.grpc_port}"
        
        # For development, use only insecure port
        # TODO: Configure proper TLS credentials for production
        server.add_insecure_port(listen_addr)
        
        # Secure port configuration (commented out for development)
        # server_creds = grpc.ssl_server_credentials()
        # server.add_secure_port(listen_addr, server_creds)
        
        logger.info("gRPC server configured", listen_addr=listen_addr, port=self.settings.grpc_port)

        return server

    async def _register_services(self, server: aio.Server):
        """Register all gRPC service handlers."""
        if not all([chat_pb2_grpc, user_pb2_grpc]):
            logger.warning("Required protobuf modules not available - services not registered")
            logger.info("Run 'python scripts/generate_protos.py' to generate protobuf modules")
            return

        try:
            # Initialize dependency container
            container = get_dependency_container()
            await container.initialize()

            chat_handler = ChatHandler(dependency_container=container)
            user_handler = UserHandler(dependency_container=container)

            # Register all services
            chat_pb2_grpc.add_ChatServiceServicer_to_server(chat_handler, server)
            user_pb2_grpc.add_UserServiceServicer_to_server(user_handler, server)

            logger.info("All gRPC service handlers registered", services=["ChatService", "UserService"])
        except Exception as e:
            logger.error("Failed to register gRPC services", error=str(e), exc_info=True)
            raise

    def _add_error_interceptor(self, server: aio.Server) -> aio.Server:
        """Add custom error handling interceptor."""
        
        class ErrorInterceptor(aio.ServerInterceptor):
            async def intercept_service(self, continuation, handler_call_details):
                try:
                    return await continuation(handler_call_details)
                except BaseAppException as e:
                    logger.error("Application error in gRPC call", 
                               error_type=type(e).__name__,
                               error_dict=e.to_dict(),
                               method=handler_call_details.method)
                    await handler_call_details.abort(
                        grpc.StatusCode.INTERNAL, 
                        str(e)
                    )
                except Exception as e:
                    logger.error("Unexpected error in gRPC call", 
                               error=str(e),
                               method=handler_call_details.method,
                               exc_info=True)
                    await handler_call_details.abort(
                        grpc.StatusCode.INTERNAL,
                        "An unexpected error occurred"
                    )

        return aio.intercept_server(server, ErrorInterceptor())

    async def start(self):
        """Start the gRPC server."""
        try:
            self.server = await self._create_server()
            await self.server.start()
            logger.info("gRPC server started", port=self.settings.grpc_port)
            
            # Wait for termination
            await self.server.wait_for_termination()
            
        except Exception as e:
            logger.error("Failed to start gRPC server", error=str(e), exc_info=True)
            raise
    
    async def start_non_blocking(self):
        """Start the gRPC server without blocking."""
        try:
            self.server = await self._create_server()
            await self.server.start()
            logger.info("gRPC server started (non-blocking)", port=self.settings.grpc_port)
            
        except Exception as e:
            logger.error("Failed to start gRPC server", error=str(e), exc_info=True)
            raise

    async def stop(self, grace_period: float = 5.0):
        """Stop the gRPC server gracefully."""
        if self.server:
            logger.info("Stopping gRPC server", grace_period=grace_period)
            await self.server.stop(grace_period)
            logger.info("gRPC server stopped")

    @asynccontextmanager
    async def lifespan(self):
        """Context manager for server lifespan."""
        try:
            self.server = await self._create_server()
            await self.server.start()
            logger.info("gRPC server started", port=self.settings.grpc_port)
            yield self
        finally:
            if self.server:
                await self.stop()


async def create_grpc_server(settings: Settings) -> VerbilioGRPCServer:
    """Factory function to create a gRPC server instance."""
    return VerbilioGRPCServer(settings)


async def run_grpc_server(settings: Settings):
    """Run the gRPC server with proper lifecycle management."""
    server = await create_grpc_server(settings)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await server.stop()
