"""
REST API endpoints package.

This package contains all REST endpoint modules for the ai-workflow-automation Core microservice.
"""

from .chat_endpoints import create_chat_router

__all__ = [
    "create_chat_router"
]
