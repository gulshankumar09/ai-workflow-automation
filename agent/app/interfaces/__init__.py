"""
Interface Layer for ai-workflow-automation Core Microservice.

This module provides external interfaces for the core microservice including:
- gRPC services for workflow and execution operations
- Health check endpoints for monitoring and orchestration
- Real-time streaming capabilities
- Error handling and service discovery
"""

# gRPC interfaces - temporarily disabled for testing
from .grpc.server import VerbilioGRPCServer, create_grpc_server, run_grpc_server
from .grpc.handlers import (
    ChatHandler,
    UserHandler
)

# Health check interfaces
from .health import HealthService, create_health_endpoints

__all__ = [
    # gRPC Server - temporarily disabled
    "VerbilioGRPCServer",
    "create_grpc_server", 
    "run_grpc_server",
    
    "ChatHandler", 
    "UserHandler",
    
    # Health Services
    "HealthService",
    "create_health_endpoints"
] 