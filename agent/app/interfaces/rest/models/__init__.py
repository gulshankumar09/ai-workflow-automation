"""
Common models for REST API endpoints.

This module provides shared models used across different REST endpoints.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    correlation_id: str = Field(..., description="Request correlation ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class SuccessResponse(BaseModel):
    """Standard success response model."""
    success: bool = Field(True, description="Success status")
    message: str = Field(..., description="Success message")
    correlation_id: str = Field(..., description="Request correlation ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


class PaginationInfo(BaseModel):
    """Pagination information model."""
    total_count: int = Field(..., description="Total number of items")
    page_size: int = Field(..., description="Number of items per page")
    current_page: int = Field(..., description="Current page number")
    has_more: bool = Field(..., description="Whether there are more pages")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")


class MetadataInfo(BaseModel):
    """Metadata information model."""
    correlation_id: str = Field(default_factory=lambda: str(uuid4()), description="Correlation ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")
    version: str = Field(default="1.0.0", description="API version")
    source: str = Field(default="core-api", description="Source service")


class HealthStatus(BaseModel):
    """Health status model."""
    status: str = Field(..., description="Overall health status")
    checks: Dict[str, Any] = Field(..., description="Individual health checks")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    uptime: Optional[float] = Field(None, description="Service uptime in seconds")
    version: str = Field(..., description="Service version")


# Session and Context Models

class SessionInfo(BaseModel):
    """Session information model."""
    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="User identifier")
    session_type: str = Field(..., description="Session type")
    status: str = Field(..., description="Session status")
    created_at: datetime = Field(..., description="Session creation time")
    last_activity: datetime = Field(..., description="Last activity time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Session metadata")


class ContextData(BaseModel):
    """Context data model."""
    context: Dict[str, Any] = Field(..., description="Context data")
    session_id: Optional[str] = Field(None, description="Associated session ID")
    last_updated: datetime = Field(..., description="Last update timestamp")
    version: int = Field(default=1, description="Context version")


# Tool and Capability Models

class ToolInfo(BaseModel):
    """Tool information model."""
    tool_id: str = Field(..., description="Tool identifier")
    tool_name: str = Field(..., description="Tool name")
    category: str = Field(..., description="Tool category")
    description: Optional[str] = Field(None, description="Tool description")
    version: str = Field(..., description="Tool version")
    is_enabled: bool = Field(default=True, description="Whether tool is enabled")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Tool configuration")
    permissions: List[str] = Field(default_factory=list, description="Required permissions")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")


class CapabilityInfo(BaseModel):
    """Capability information model."""
    capability_id: str = Field(..., description="Capability identifier")
    capability_name: str = Field(..., description="Capability name")
    description: Optional[str] = Field(None, description="Capability description")
    is_available: bool = Field(default=True, description="Whether capability is available")
    requirements: List[str] = Field(default_factory=list, description="Capability requirements")


# Message and Communication Models

class MessageInfo(BaseModel):
    """Message information model."""
    message_id: str = Field(..., description="Message identifier")
    session_id: str = Field(..., description="Session identifier")
    content: str = Field(..., description="Message content")
    message_type: str = Field(..., description="Message type")
    timestamp: datetime = Field(..., description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Message metadata")
    is_final: bool = Field(default=False, description="Whether this is the final message")


class ToolCall(BaseModel):
    """Tool call model."""
    tool_call_id: str = Field(..., description="Tool call identifier")
    tool_name: str = Field(..., description="Tool name")
    function_name: str = Field(..., description="Function name")
    arguments: Dict[str, Any] = Field(..., description="Function arguments")
    result: Optional[Dict[str, Any]] = Field(None, description="Tool call result")
    status: str = Field(..., description="Tool call status")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")


# Activity and Metrics Models

class ActivityInfo(BaseModel):
    """Activity information model."""
    activity_id: str = Field(..., description="Activity identifier")
    user_id: str = Field(..., description="User identifier")
    activity_type: str = Field(..., description="Activity type")
    description: str = Field(..., description="Activity description")
    timestamp: datetime = Field(..., description="Activity timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Activity metadata")
    session_id: Optional[str] = Field(None, description="Associated session ID")


class MetricsInfo(BaseModel):
    """Metrics information model."""
    metric_name: str = Field(..., description="Metric name")
    metric_value: float = Field(..., description="Metric value")
    metric_type: str = Field(..., description="Metric type (counter, gauge, histogram)")
    timestamp: datetime = Field(..., description="Metric timestamp")
    labels: Dict[str, str] = Field(default_factory=dict, description="Metric labels")
    unit: Optional[str] = Field(None, description="Metric unit")


# Request/Response Base Models

class BaseRequest(BaseModel):
    """Base request model with common fields."""
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Request metadata")


class BaseResponse(BaseModel):
    """Base response model with common fields."""
    correlation_id: str = Field(..., description="Response correlation ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
