"""
Logging Configuration for ai-workflow-automation Core Microservice.

This module provides comprehensive logging setup using structlog with
proper configuration for both development and production environments.

# Usages
1. Direct method usage (recommended for simplicity):

from app.shared.logging_config import info, error, debug
info("User authenticated", user_id=123, session="abc")
error("Database connection failed", error="timeout", retry_count=3, exc_info=True)
debug("Processing workflow step", step_id=456, workflow_id=789)

2. Logger instance usage:

from app.shared.logging_config import log
log.info("User authenticated", user_id=123, session="abc")
log.error("Database connection failed", error="timeout", retry_count=3)

3. Custom logger with specific name:

from app.shared.logging_config import get_logger
logger = get_logger("workflow.executor")
logger.debug("Processing step", step_id=456, workflow_id=789)

4. Environment-specific setup:

from app.shared.logging_config import setup_logging
# For production
logger = setup_logging(log_level="WARNING", development_mode=False)
# For development  
logger = setup_logging(log_level="DEBUG", development_mode=True)

5. another way to use the logger

from app.shared.logging_config import get_logger

logger = get_logger("workflow.executor")

# Now your IDE will show all these methods with autocomplete!
logger.info("Processing step", step_id=456, workflow_id=789)
logger.error("Database connection failed", error="timeout", retry_count=3, exc_info=True)
logger.debug("Cache hit", key="user:123", ttl=300)
logger.exception("Unexpected error occurred")  # Automatically includes traceback

# Context binding also works
user_logger = logger.bind(user_id=123, session="abc")
user_logger.info("User action completed", action="login")

"""

import sys
import logging
import structlog
from typing import Optional, Dict, Any, Union


class Logger:
    """
    Enhanced logger wrapper that provides better IDE support and autocomplete.
    
    This wrapper ensures that IDEs can properly show available logging methods
    like .info(), .debug(), .error(), etc. with proper type hints.
    """
    
    def __init__(self, logger: structlog.BoundLogger):
        self._logger = logger
    
    def debug(self, message: str, **kwargs) -> None:
        """Log a debug message with optional context."""
        self._logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log an info message with optional context."""
        self._logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log a warning message with optional context."""
        self._logger.warning(message, **kwargs)
    
    def warn(self, message: str, **kwargs) -> None:
        """Log a warning message with optional context (alias for warning)."""
        self._logger.warning(message, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log an error message with optional context and exception info."""
        self._logger.error(message, exc_info=exc_info, **kwargs)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log a critical message with optional context and exception info."""
        self._logger.critical(message, exc_info=exc_info, **kwargs)
    
    def exception(self, message: str, **kwargs) -> None:
        """Log an exception with traceback (equivalent to error with exc_info=True)."""
        self._logger.error(message, exc_info=True, **kwargs)
    
    def bind(self, **kwargs) -> 'Logger':
        """Bind context to logger and return a new logger instance."""
        return Logger(self._logger.bind(**kwargs))


def configure_structlog(
    log_level: str = "INFO",
    use_colors: bool = True,
    include_timestamp: bool = True,
    json_logs: bool = False
) -> None:
    """
    Configure structlog with appropriate processors and formatters.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_colors: Whether to use colored output (useful for development)
        include_timestamp: Whether to include timestamps in logs
        json_logs: Whether to output logs in JSON format (useful for production)
    """
    # Set the log level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper())
    )
    
    # Define processors
    processors = [
        # Add the log level and a timestamp to the event_dict if the log entry
        # is not from structlog.
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
    ]
    
    if include_timestamp:
        processors.append(structlog.processors.TimeStamper(fmt="iso"))
    
    # Add processors for better development experience
    if not json_logs:
        processors.extend([
            # If some value is in bytes, decode it to a unicode str
            structlog.processors.UnicodeDecoder(),
            # Render the final event dict as JSON
            structlog.dev.ConsoleRenderer(colors=use_colors)
        ])
    else:
        processors.extend([
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ])
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> Logger:
    """
    Get a configured logger instance with enhanced IDE support.
    
    Args:
        name: Optional logger name. If not provided, uses the calling module's name.
        
    Returns:
        Enhanced Logger instance with proper autocomplete support
    """
    if name is None:
        # Get the caller's module name
        import inspect
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back
            name = caller_frame.f_globals.get('__name__', 'unknown')
        finally:
            del frame
    
    structlog_logger = structlog.get_logger(name)
    return Logger(structlog_logger)


def setup_logging(
    log_level: str = "INFO",
    development_mode: bool = True,
    **kwargs
) -> Logger:
    """
    Setup logging configuration and return a logger instance.
    
    Args:
        log_level: Logging level
        development_mode: Whether running in development mode
        **kwargs: Additional configuration options
        
    Returns:
        Configured logger instance with enhanced IDE support
    """
    configure_structlog(
        log_level=log_level,
        use_colors=development_mode,
        include_timestamp=True,
        json_logs=not development_mode,
        **kwargs
    )
    
    return get_logger("ai-workflow-automation.core")


# Initialize logging with default configuration
# This allows immediate usage: from app.shared.logging_config import log
configure_structlog("DEBUG")
log = get_logger("ai-workflow-automation.core")


# Convenient logging methods that can be invoked directly
def debug(message: str, **kwargs) -> None:
    """Log a debug message with optional context."""
    log.debug(message, **kwargs)


def info(message: str, **kwargs) -> None:
    """Log an info message with optional context."""
    log.info(message, **kwargs)


def warning(message: str, **kwargs) -> None:
    """Log a warning message with optional context."""
    log.warning(message, **kwargs)


def error(message: str, exc_info: bool = False, **kwargs) -> None:
    """Log an error message with optional context and exception info."""
    log.error(message, exc_info=exc_info, **kwargs)


def critical(message: str, exc_info: bool = False, **kwargs) -> None:
    """Log a critical message with optional context and exception info."""
    log.critical(message, exc_info=exc_info, **kwargs)


def exception(message: str, **kwargs) -> None:
    """Log an exception with traceback (equivalent to error with exc_info=True)."""
    log.exception(message, **kwargs)


# Export commonly used items
__all__ = [
    "configure_structlog",
    "get_logger", 
    "setup_logging",
    "log",
    "Logger",
    "debug",
    "info", 
    "warning",
    "error",
    "critical",
    "exception",
]

# Usages

# 1. Simple usage (anywhere in your project):
# from app.shared.logging_config import log

# log.info("User authenticated", user_id=123, session="abc")
# log.error("Database connection failed", error="timeout", retry_count=3)

# 2. Custom logger with specific name:
# from app.shared.logging_config import get_logger

# logger = get_logger("workflow.executor")
# logger.debug("Processing step", step_id=456, workflow_id=789)

# 3. Environment-specific setup:
# from app.shared.logging_config import setup_logging

# # For production
# logger = setup_logging(log_level="WARNING", development_mode=False)

# # For development  
# logger = setup_logging(log_level="DEBUG", development_mode=True)
