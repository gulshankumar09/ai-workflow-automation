"""
Custom Exception Hierarchy for ai-workflow-automation Core Microservice

This module provides a structured exception hierarchy for consistent error handling
across the entire microservice. It includes correlation tracking, structured error
details, and specific exception types for different error scenarios.

Design Principles:
1. Structured Error Information: All exceptions include message, code, status_code, and details
2. Correlation Tracking: Every exception includes a correlation_id for request tracing
3. Backwards Compatibility: Existing VerbilioError hierarchy is preserved
4. Type Safety: Specific exception types for different error categories
5. Logging Support: to_dict() method for structured logging

Usage Guidelines:
- Use specific exception types (NotFoundException, ValidationException, etc.) when possible
- Always include correlation_id for request tracing
- Provide meaningful error messages and details for debugging
- Use try-catch blocks for recoverable errors, raise for unrecoverable ones
"""

import time
import uuid
from typing import Optional, Dict, Any, Union
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels for monitoring and alerting"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BaseAppException(Exception):
    """
    Base exception for all custom application exceptions with correlation tracking
    
    This is the foundation exception class that provides:
    - Structured error information (message, code, status_code)
    - Correlation tracking for request tracing
    - Timestamp for error occurrence tracking
    - Details dictionary for additional context
    - Severity level for monitoring
    
    Args:
        message: Human-readable error message
        code: Machine-readable error code (uppercase with underscores)
        status_code: HTTP status code equivalent
        correlation_id: Unique identifier for request tracing
        details: Additional error context and debugging information
        severity: Error severity level for monitoring
    """
    
    def __init__(
        self, 
        message: str,
        code: str = "GENERIC_ERROR",
        status_code: int = 500,
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.details = details or {}
        self.severity = severity
        self.timestamp = int(time.time())
        self.exception_type = self.__class__.__name__
        
        # Add system context to details
        self.details.update({
            "exception_type": self.exception_type,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for logging and API responses
        
        Returns:
            Dictionary with structured error information
        """
        return {
            "message": self.message,
            "code": self.code,
            "status_code": self.status_code,
            "correlation_id": self.correlation_id,
            "details": self.details,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "exception_type": self.exception_type
        }
    
    def to_response_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary suitable for API responses (excludes sensitive details)
        
        Returns:
            Dictionary with user-safe error information
        """
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "correlation_id": self.correlation_id,
                "timestamp": self.timestamp
            }
        }
    
    def __str__(self) -> str:
        return f"{self.exception_type}: {self.message} (Code: {self.code}, ID: {self.correlation_id})"
    
    def __repr__(self) -> str:
        return (f"{self.exception_type}(message='{self.message}', code='{self.code}', "
                f"status_code={self.status_code}, correlation_id='{self.correlation_id}')")


class NotFoundException(BaseAppException):
    """
    Exception for resource not found errors (404)
    
    Use when:
    - Requested resource doesn't exist
    - User doesn't have access to resource
    - Resource has been deleted or moved
    
    Example:
        raise NotFoundException(
            "Cache provider 'invalid_provider' not found",
            correlation_id=request_id,
            details={"available_providers": ["redis", "memory", "supabase"]}
        )
    """
    
    def __init__(
        self,
        message: str = "Resource not found",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.LOW
    ):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
            correlation_id=correlation_id,
            details=details,
            severity=severity
        )


class ValidationException(BaseAppException):
    """
    Exception for validation errors (400)
    
    Use when:
    - Request parameters are invalid
    - Configuration validation fails
    - Input format is incorrect
    - Required fields are missing
    
    Example:
        raise ValidationException(
            "Missing required parameter 'host' for Redis provider",
            correlation_id=request_id,
            details={
                "missing_parameters": ["host"],
                "provided_parameters": ["port", "db"]
            }
        )
    """
    
    def __init__(
        self,
        message: str = "Validation failed",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.LOW
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            correlation_id=correlation_id,
            details=details,
            severity=severity
        )


class DatabaseException(BaseAppException):
    """
    Exception for database-related errors (500)
    
    Use when:
    - Database connection fails
    - Query execution fails
    - Transaction rollback occurs
    - Database constraint violations
    
    Example:
        raise DatabaseException(
            "Failed to connect to PostgreSQL database",
            correlation_id=request_id,
            details={
                "database_host": "localhost",
                "database_name": "ai-workflow-automation",
                "error_type": "ConnectionTimeout"
            },
            severity=ErrorSeverity.HIGH
        )
    """
    
    def __init__(
        self,
        message: str = "Database operation failed",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.HIGH
    ):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=500,
            correlation_id=correlation_id,
            details=details,
            severity=severity
        )


class CacheProviderException(BaseAppException):
    """
    Exception for cache provider errors (500)
    
    Use when:
    - Cache connection fails
    - Cache operation timeouts
    - Cache configuration is invalid
    - Cache memory limits exceeded
    
    Example:
        raise CacheProviderException(
            "Redis connection timeout",
            correlation_id=request_id,
            details={
                "provider_type": "redis",
                "operation": "SET",
                "timeout_seconds": 5
            }
        )
    """
    
    def __init__(
        self,
        message: str = "Cache provider operation failed",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ):
        super().__init__(
            message=message,
            code="CACHE_PROVIDER_ERROR",
            status_code=500,
            correlation_id=correlation_id,
            details=details,
            severity=severity
        )


class StorageProviderException(BaseAppException):
    """
    Exception for storage provider errors (500/502)
    
    Use when:
    - File upload/download failures
    - Storage service unavailable
    - Authentication to storage service fails
    - File encryption/decryption errors
    - Storage quota exceeded
    
    Example:
        raise StorageProviderException(
            "Failed to upload file to S3 bucket",
            correlation_id=request_id,
            details={
                "file_path": "uploads/user123/document.pdf",
                "bucket": "ai-workflow-automation-storage",
                "error_code": "AccessDenied"
            }
        )
    """
    
    def __init__(
        self,
        message: str = "Storage provider operation failed",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        status_code: int = 500
    ):
        super().__init__(
            message=message,
            code="STORAGE_PROVIDER_ERROR",
            status_code=status_code,
            correlation_id=correlation_id,
            details=details,
            severity=severity
        )


class AuthenticationException(BaseAppException):
    """
    Exception for authentication errors (401)
    
    Use when:
    - Invalid credentials
    - Token expired or invalid
    - Missing authentication
    """
    
    def __init__(
        self,
        message: str = "Authentication failed",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
            correlation_id=correlation_id,
            details=details,
            severity=severity
        )


class AuthorizationException(BaseAppException):
    """
    Exception for authorization errors (403)
    
    Use when:
    - User lacks required permissions
    - Resource access denied
    - Role-based access control failures
    """
    
    def __init__(
        self,
        message: str = "Access denied",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
            correlation_id=correlation_id,
            details=details,
            severity=severity
        )


class ConfigurationException(BaseAppException):
    """
    Exception for configuration errors (500)
    
    Use when:
    - Invalid configuration values
    - Missing required configuration
    - Configuration file parsing errors
    """
    
    def __init__(
        self,
        message: str = "Configuration error",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.HIGH
    ):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            status_code=500,
            correlation_id=correlation_id,
            details=details,
            severity=severity
        )


class DependencyException(BaseAppException):
    """
    Exception for dependency injection and management errors (500)
    
    Use when:
    - Dependency container initialization fails
    - Required dependencies are not available
    - Dependency lifecycle management errors
    - Circular dependency detection
    """
    
    def __init__(
        self,
        message: str = "Dependency error",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.HIGH
    ):
        super().__init__(
            message=message,
            code="DEPENDENCY_ERROR",
            status_code=500,
            correlation_id=correlation_id,
            details=details,
            severity=severity
        )


class ExternalServiceException(BaseAppException):
    """
    Exception for external service errors (502/503)
    
    Use when:
    - External API calls fail
    - Third-party service unavailable
    - Network timeouts
    """
    
    def __init__(
        self,
        message: str = "External service error",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        status_code: int = 502
    ):
        super().__init__(
            message=message,
            code="EXTERNAL_SERVICE_ERROR",
            status_code=status_code,
            correlation_id=correlation_id,
            details=details,
            severity=severity
        )


# =============================================================================
# BACKWARDS COMPATIBILITY - Existing VerbilioError Hierarchy
# =============================================================================

class VerbilioError(BaseAppException):
    """
    Base exception for ai-workflow-automation system - extends BaseAppException for backwards compatibility
    
    This class maintains the existing interface while providing new structured error features.
    Use the new specific exception types (ValidationException, etc.) for new code.
    """
    
    def __init__(
        self, 
        message: str, 
        error_code: str, 
        user_message: str = None, 
        details: dict = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            code=error_code,
            correlation_id=correlation_id,
            details=details or {}
        )
        self.error_code = error_code  # For backwards compatibility
        self.user_message = user_message or message


class WorkflowGenerationError(VerbilioError):
    """Workflow generation specific errors"""
    
    def __init__(
        self,
        message: str,
        user_message: str = None,
        details: dict = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="WORKFLOW_GENERATION_ERROR",
            user_message=user_message,
            details=details,
            correlation_id=correlation_id
        )
        self.status_code = 400  # Override for workflow errors


class MCPToolError(VerbilioError):
    """MCP tool execution errors"""
    
    def __init__(
        self,
        message: str,
        user_message: str = None,
        details: dict = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="MCP_TOOL_ERROR",
            user_message=user_message,
            details=details,
            correlation_id=correlation_id
        )
        self.status_code = 502  # External service error


class UserToolAccessError(VerbilioError):
    """User tool access errors"""
    
    def __init__(
        self,
        message: str,
        user_message: str = None,
        details: dict = None,
        correlation_id: Optional[str] = None
    ):
        super().__init__(
            message=message,
            error_code="USER_TOOL_ACCESS_ERROR",
            user_message=user_message,
            details=details,
            correlation_id=correlation_id
        )
        self.status_code = 403  # Forbidden


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_exception_by_code(error_code: str) -> type:
    """
    Get exception class by error code
    
    Args:
        error_code: Error code string
        
    Returns:
        Exception class type
    """
    exception_mapping = {
        "NOT_FOUND": NotFoundException,
        "VALIDATION_ERROR": ValidationException,
        "DATABASE_ERROR": DatabaseException,
        "CACHE_PROVIDER_ERROR": CacheProviderException,
        "AUTHENTICATION_ERROR": AuthenticationException,
        "AUTHORIZATION_ERROR": AuthorizationException,
        "CONFIGURATION_ERROR": ConfigurationException,
        "DEPENDENCY_ERROR": DependencyException,
        "EXTERNAL_SERVICE_ERROR": ExternalServiceException,
        "WORKFLOW_GENERATION_ERROR": WorkflowGenerationError,
        "MCP_TOOL_ERROR": MCPToolError,
        "USER_TOOL_ACCESS_ERROR": UserToolAccessError,
    }
    
    return exception_mapping.get(error_code, BaseAppException)


def create_error_context(
    operation: str,
    component: str,
    correlation_id: Optional[str] = None,
    **additional_context
) -> Dict[str, Any]:
    """
    Create standardized error context for consistent error details
    
    Args:
        operation: The operation that failed
        component: The component where error occurred
        correlation_id: Request correlation ID
        **additional_context: Additional context information
        
    Returns:
        Standardized error context dictionary
    """
    context = {
        "operation": operation,
        "component": component,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        **additional_context
    }
    
    return context 