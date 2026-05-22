"""
REST API Interface for ai-workflow-automation Core Microservice.

This module provides REST API endpoints that expose the same functionality
as the gRPC endpoints, allowing direct HTTP access to core services.
"""

from .router import create_rest_router
from .endpoints import chat_endpoints

__all__ = [
    "create_rest_router",
    "chat_endpoints"
]
