"""
Protocol Buffer schemas for ai-workflow-automation gRPC services.

This module provides access to all gRPC service definitions and message types
used for communication between the core microservice and clients.

Generated modules are automatically imported and available for use.
"""

# Generated protobuf modules
from . import chat_pb2
from . import chat_pb2_grpc
from . import user_pb2
from . import user_pb2_grpc

__all__ = [
    "chat_pb2",
    "chat_pb2_grpc",
    "user_pb2",
    "user_pb2_grpc"
]
