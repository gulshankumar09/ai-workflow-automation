# Error Handling Guidelines for ai-workflow-automation Core Microservice

## Overview

This document provides comprehensive guidelines for error handling in the ai-workflow-automation Core Microservice using our custom exception hierarchy. It covers when to use try-catch blocks vs raising exceptions, best practices, and real-world examples.

## Design Philosophy

### Balanced Error Handling Approach

Our error handling strategy follows a **balanced approach** combining:

1. **Local Error Handling**: Use try-catch blocks for recoverable errors
2. **Error Propagation**: Raise exceptions for unrecoverable errors
3. **Structured Error Information**: Use custom exception hierarchy with correlation tracking
4. **Centralized Error Processing**: Global error handlers for consistency

## Core Principles

### 1. Use Specific Exception Types

Always use the most specific exception type available:

```python
# ✅ Good - Specific exception type
raise ValidationException(
    "Missing required parameter 'host'",
    correlation_id=request_id,
    details={"missing_params": ["host"]}
)

# ❌ Bad - Generic exception
raise Exception("Parameter missing")
```

### 2. Include Correlation IDs

Always include correlation IDs for request tracing:

```python
# ✅ Good - With correlation ID
def process_request(request_id: str, data: dict):
    try:
        validate_data(data)
    except ValidationError as e:
        raise ValidationException(
            "Data validation failed",
            correlation_id=request_id,
            details={"validation_errors": str(e)}
        )

# ❌ Bad - No correlation tracking
def process_request(data: dict):
    raise ValidationException("Data validation failed")
```

### 3. Provide Meaningful Error Context

Include detailed context for debugging:

```python
# ✅ Good - Rich context
raise DatabaseException(
    "Failed to connect to database",
    correlation_id=request_id,
    details={
        "database_host": "localhost",
        "database_name": "ai-workflow-automation",
        "timeout_seconds": 30,
        "error_type": "ConnectionTimeout",
        "retry_count": 3
    }
)
```

## When to Use Try-Catch vs Raise

### Use Try-Catch Blocks When:

#### 1. You Can Recover from the Error

```python
def get_cached_data(cache_provider, key: str, correlation_id: str):
    """Try cache first, fallback to database"""
    try:
        return cache_provider.get(key)
    except CacheProviderException as e:
        logger.warning(f"Cache miss, falling back to database: {e}", extra=e.to_dict())
        # Recovery: fallback to database
        return database.get(key)
```

#### 2. You Can Provide Alternative Solutions

```python
def create_cache_provider(provider_type: str, correlation_id: str, **config):
    """Try requested provider, fallback to memory cache"""
    try:
        return CacheProviderFactory.create_provider(provider_type, correlation_id, **config)
    except NotFoundException:
        logger.warning(f"Provider {provider_type} not found, using memory cache")
        # Recovery: use fallback provider
        return CacheProviderFactory.create_provider("memory", correlation_id)
    except ValidationException as e:
        logger.error(f"Configuration invalid: {e}", extra=e.to_dict())
        # Recovery: use default configuration
        return CacheProviderFactory.create_provider("memory", correlation_id)
```

#### 3. You Need to Add Context or Transform Errors

```python
def execute_workflow_step(step_config: dict, correlation_id: str):
    """Execute a workflow step with enhanced error context"""
    try:
        return mcp_manager.execute_tool(
            step_config["tool_name"],
            step_config["parameters"],
            correlation_id
        )
    except MCPToolError as e:
        # Transform to workflow-specific error with more context
        raise WorkflowGenerationError(
            f"Step '{step_config['name']}' failed: {e.message}",
            correlation_id=correlation_id,
            details={
                "step_name": step_config["name"],
                "tool_name": step_config["tool_name"],
                "original_error": e.to_dict()
            }
        )
```

#### 4. You Need to Clean Up Resources

```python
async def process_with_connection(correlation_id: str):
    """Process with proper resource cleanup"""
    connection = None
    try:
        connection = await database.get_connection()
        result = await connection.execute_query("SELECT * FROM workflows")
        return result
    except DatabaseException as e:
        logger.error(f"Database operation failed: {e}", extra=e.to_dict())
        # Handle the error but still clean up
        raise  # Re-raise after logging
    finally:
        # Always clean up resources
        if connection:
            await connection.close()
```

### Raise Exceptions When:

#### 1. The Error Cannot Be Recovered At This Level

```python
def validate_user_permissions(user_id: str, resource_id: str, correlation_id: str):
    """Validate user has access to resource"""
    user = user_repository.get_user(user_id)
    if not user:
        # Cannot recover - user doesn't exist
        raise AuthenticationException(
            f"User {user_id} not found",
            correlation_id=correlation_id,
            details={"user_id": user_id}
        )

    if not user.has_permission(resource_id):
        # Cannot recover - access denied
        raise AuthorizationException(
            f"User {user_id} lacks permission for resource {resource_id}",
            correlation_id=correlation_id,
            details={"user_id": user_id, "resource_id": resource_id}
        )
```

#### 2. Invalid Input That Requires Client Action

```python
def create_workflow(workflow_data: dict, correlation_id: str):
    """Create a new workflow"""
    required_fields = ["name", "description", "steps"]
    missing_fields = [field for field in required_fields if field not in workflow_data]

    if missing_fields:
        # Client must fix the request
        raise ValidationException(
            f"Missing required fields: {', '.join(missing_fields)}",
            correlation_id=correlation_id,
            details={
                "missing_fields": missing_fields,
                "required_fields": required_fields,
                "provided_fields": list(workflow_data.keys())
            }
        )
```

#### 3. Critical System Failures

```python
def initialize_database_connection():
    """Initialize critical database connection"""
    try:
        connection = create_connection(database_url)
        connection.test_connection()
        return connection
    except Exception as e:
        # Critical failure - system cannot function
        raise ConfigurationException(
            f"Failed to initialize database connection: {str(e)}",
            details={
                "database_url": database_url,
                "error_type": type(e).__name__,
                "system_critical": True
            },
            severity=ErrorSeverity.CRITICAL
        )
```

## Error Handling Patterns

### Pattern 1: Repository Pattern with Error Handling

```python
class WorkflowRepository:
    def __init__(self, db_provider, correlation_id: str):
        self.db = db_provider
        self.correlation_id = correlation_id

    async def get_workflow(self, workflow_id: str) -> dict:
        """Get workflow by ID with proper error handling"""
        try:
            result = await self.db.fetch_one(
                "SELECT * FROM workflows WHERE id = $1",
                workflow_id
            )
            if not result:
                raise NotFoundException(
                    f"Workflow {workflow_id} not found",
                    correlation_id=self.correlation_id,
                    details={"workflow_id": workflow_id}
                )
            return dict(result)

        except DatabaseException:
            # Re-raise database exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise DatabaseException(
                f"Failed to retrieve workflow {workflow_id}: {str(e)}",
                correlation_id=self.correlation_id,
                details={
                    "workflow_id": workflow_id,
                    "operation": "get_workflow",
                    "error_type": type(e).__name__
                }
            )
```

### Pattern 2: Service Layer with Business Logic Error Handling

```python
class WorkflowService:
    def __init__(self, workflow_repo, mcp_manager):
        self.workflow_repo = workflow_repo
        self.mcp_manager = mcp_manager

    async def execute_workflow(self, workflow_id: str, user_id: str, correlation_id: str):
        """Execute workflow with comprehensive error handling"""

        # Get workflow (may raise NotFoundException)
        workflow = await self.workflow_repo.get_workflow(workflow_id)

        # Validate user access
        if workflow["owner_id"] != user_id:
            raise AuthorizationException(
                f"User {user_id} cannot execute workflow {workflow_id}",
                correlation_id=correlation_id,
                details={
                    "user_id": user_id,
                    "workflow_id": workflow_id,
                    "owner_id": workflow["owner_id"]
                }
            )

        results = []
        for step in workflow["steps"]:
            try:
                # Attempt step execution
                result = await self.mcp_manager.execute_tool(
                    step["tool_name"],
                    step["parameters"],
                    correlation_id
                )
                results.append({"step": step["name"], "result": result, "status": "success"})

            except MCPToolError as e:
                # Handle tool failure - decide if workflow should continue
                if step.get("critical", False):
                    # Critical step failed - abort workflow
                    raise WorkflowGenerationError(
                        f"Critical step '{step['name']}' failed: {e.message}",
                        correlation_id=correlation_id,
                        details={
                            "failed_step": step["name"],
                            "workflow_id": workflow_id,
                            "completed_steps": len(results),
                            "original_error": e.to_dict()
                        }
                    )
                else:
                    # Non-critical step - log and continue
                    logger.warning(f"Step '{step['name']}' failed but continuing", extra=e.to_dict())
                    results.append({"step": step["name"], "error": e.message, "status": "failed"})

        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "results": results,
            "correlation_id": correlation_id
        }
```

### Pattern 3: Factory Pattern with Comprehensive Error Handling

```python
class ProviderFactory:
    @classmethod
    def create_provider(cls, provider_type: str, correlation_id: str, **config):
        """Create provider with comprehensive error handling"""

        # Input validation
        if not provider_type:
            raise ValidationException(
                "Provider type cannot be empty",
                correlation_id=correlation_id,
                details={"available_providers": list(cls._providers.keys())}
            )

        # Provider existence check
        if provider_type not in cls._providers:
            raise NotFoundException(
                f"Provider '{provider_type}' not found",
                correlation_id=correlation_id,
                details={
                    "requested_provider": provider_type,
                    "available_providers": list(cls._providers.keys())
                }
            )

        provider_class = cls._providers[provider_type]

        try:
            # Validate configuration
            cls._validate_config(provider_type, config, correlation_id)

            # Create provider instance
            provider = provider_class(**config)

            # Test connectivity if supported
            if hasattr(provider, 'test_connection'):
                try:
                    provider.test_connection()
                except Exception as e:
                    raise ExternalServiceException(
                        f"Connection test failed for {provider_type}: {str(e)}",
                        correlation_id=correlation_id,
                        details={
                            "provider_type": provider_type,
                            "test_error": str(e)
                        }
                    )

            return provider

        except (ValidationException, NotFoundException, ExternalServiceException):
            # Re-raise known exceptions
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ConfigurationException(
                f"Failed to create {provider_type} provider: {str(e)}",
                correlation_id=correlation_id,
                details={
                    "provider_type": provider_type,
                    "config_keys": list(config.keys()),
                    "error_type": type(e).__name__
                }
            )
```

## Logging Best Practices

### 1. Use Structured Logging with Exception Context

```python
import structlog
from app.shared.exceptions import BaseAppException

logger = structlog.getLogger(__name__)

# ✅ Good - Structured logging with exception context
try:
    result = process_data(data)
except ValidationException as e:
    logger.error(
        "Data validation failed",
        extra={
            **e.to_dict(),
            "function": "process_data",
            "input_data_keys": list(data.keys())
        }
    )
    raise

# ✅ Good - Success logging with correlation ID
logger.info(
    "Workflow executed successfully",
    extra={
        "correlation_id": correlation_id,
        "workflow_id": workflow_id,
        "execution_time_ms": execution_time,
        "steps_completed": len(results)
    }
)
```

### 2. Use Different Log Levels Based on Exception Severity

```python
def handle_exception(e: BaseAppException):
    """Log exception based on severity"""
    log_data = e.to_dict()

    if e.severity == ErrorSeverity.LOW:
        logger.info("Low severity error occurred", extra=log_data)
    elif e.severity == ErrorSeverity.MEDIUM:
        logger.warning("Medium severity error occurred", extra=log_data)
    elif e.severity == ErrorSeverity.HIGH:
        logger.error("High severity error occurred", extra=log_data)
    elif e.severity == ErrorSeverity.CRITICAL:
        logger.critical("Critical error occurred", extra=log_data)
```

## Testing Error Handling

### 1. Test Exception Creation and Serialization

```python
def test_base_app_exception():
    """Test BaseAppException functionality"""
    correlation_id = "test-123"
    details = {"test_key": "test_value"}

    exception = ValidationException(
        "Test validation error",
        correlation_id=correlation_id,
        details=details
    )

    assert exception.message == "Test validation error"
    assert exception.code == "VALIDATION_ERROR"
    assert exception.status_code == 400
    assert exception.correlation_id == correlation_id
    assert exception.details["test_key"] == "test_value"

    # Test serialization
    error_dict = exception.to_dict()
    assert error_dict["message"] == "Test validation error"
    assert error_dict["correlation_id"] == correlation_id
```

### 2. Test Error Handling Patterns

```python
def test_provider_factory_error_handling():
    """Test provider factory error scenarios"""
    correlation_id = "test-456"

    # Test NotFoundException
    with pytest.raises(NotFoundException) as exc_info:
        ProviderFactory.create_provider("invalid_provider", correlation_id)

    assert exc_info.value.correlation_id == correlation_id
    assert "invalid_provider" in exc_info.value.message

    # Test ValidationException
    with pytest.raises(ValidationException) as exc_info:
        ProviderFactory.create_provider("redis", correlation_id)  # Missing required config

    assert exc_info.value.correlation_id == correlation_id
```

## Performance Considerations

### 1. Avoid Overusing Try-Catch in Hot Paths

```python
# ❌ Bad - Try-catch in tight loop
def process_large_dataset(items):
    results = []
    for item in items:  # Could be millions of items
        try:
            result = expensive_operation(item)
            results.append(result)
        except Exception:
            results.append(None)
    return results

# ✅ Good - Validate once, process efficiently
def process_large_dataset(items):
    # Validate input once
    if not items:
        raise ValidationException("Items list cannot be empty")

    results = []
    for item in items:
        # Use validation function instead of try-catch
        if is_valid_item(item):
            results.append(expensive_operation(item))
        else:
            results.append(None)
    return results
```

### 2. Cache Exception Creation in Factories

```python
class CachedExceptionFactory:
    """Cache common exception instances to reduce object creation overhead"""

    _cached_exceptions = {}

    @classmethod
    def get_validation_exception(cls, message: str, correlation_id: str):
        cache_key = f"validation_{hash(message)}"
        if cache_key not in cls._cached_exceptions:
            cls._cached_exceptions[cache_key] = ValidationException(message)

        # Clone with new correlation_id
        cached = cls._cached_exceptions[cache_key]
        return ValidationException(
            cached.message,
            correlation_id=correlation_id,
            details=cached.details.copy()
        )
```

## Summary

### Key Takeaways

1. **Be Specific**: Use the most specific exception type available
2. **Include Context**: Always provide correlation IDs and detailed error context
3. **Handle Gracefully**: Use try-catch for recoverable errors, raise for unrecoverable ones
4. **Log Appropriately**: Use structured logging with exception context
5. **Test Thoroughly**: Test both success and failure scenarios
6. **Consider Performance**: Avoid exception handling in hot paths

### Quick Reference

| Scenario                  | Pattern                          | Exception Type             |
| ------------------------- | -------------------------------- | -------------------------- |
| Resource not found        | Raise                            | `NotFoundException`        |
| Invalid input             | Raise                            | `ValidationException`      |
| Database failures         | Try-catch with fallback or raise | `DatabaseException`        |
| External service failures | Try-catch with retry or raise    | `ExternalServiceException` |
| Configuration errors      | Raise                            | `ConfigurationException`   |
| Authentication failures   | Raise                            | `AuthenticationException`  |
| Authorization failures    | Raise                            | `AuthorizationException`   |
| Cache failures            | Try-catch with fallback          | `CacheProviderException`   |

This balanced approach ensures robust error handling while maintaining good performance and developer experience.
