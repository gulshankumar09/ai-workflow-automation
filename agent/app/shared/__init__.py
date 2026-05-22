"""
Shared components for ai-workflow-automation Core Microservice

This module provides shared utilities, configurations, and exceptions
that are used across the entire application.

Core Components:
- Custom Exception Hierarchy: Structured error handling with correlation tracking
- Configuration Management: Environment-based configuration with validation
- Utility Functions: Common helper functions and patterns

Usage:
    from app.shared import (
        ValidationException, DatabaseException,
        create_error_context
    )
"""

# Import custom exception hierarchy
from .exceptions import (
    # Base exceptions
    BaseAppException,
    ErrorSeverity,
    
    # Specific exception types
    NotFoundException,
    ValidationException,
    DatabaseException,
    CacheProviderException,
    AuthenticationException,
    AuthorizationException,
    ConfigurationException,
    ExternalServiceException,
    
    # Backwards compatibility
    VerbilioError,
    WorkflowGenerationError,
    MCPToolError,
    UserToolAccessError,
    
    # Utility functions
    get_exception_by_code,
    create_error_context,
)

from .CustomBaseModel import CustomBaseModel
from .logger import get_logger

# Conditional config import to avoid initialization issues
def get_settings():
    """Get application settings (imported on-demand to avoid initialization issues)"""
    from .config import get_settings as _get_settings
    return _get_settings()

# Version info
__version__ = "1.0.0"

# Main exports
__all__ = [
    # Configuration
    "get_settings",
    
    # Base exceptions
    "BaseAppException",
    "ErrorSeverity",
    
    # Specific exception types
    "NotFoundException",
    "ValidationException",
    "DatabaseException",
    "CacheProviderException",
    "AuthenticationException",
    "AuthorizationException",
    "ConfigurationException",
    "ExternalServiceException",
    
    # Backwards compatibility
    "VerbilioError",
    "WorkflowGenerationError",
    "MCPToolError",
    "UserToolAccessError",
    
    # Utility functions
    "get_exception_by_code",
    "create_error_context",
    
    # Version
    "__version__",

    # Custom Base Model
    "CustomBaseModel",

    # Logging
    "get_logger"
] 