from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class UserStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    USER_STATUS_UNSPECIFIED: _ClassVar[UserStatus]
    USER_STATUS_ACTIVE: _ClassVar[UserStatus]
    USER_STATUS_INACTIVE: _ClassVar[UserStatus]
    USER_STATUS_SUSPENDED: _ClassVar[UserStatus]
    USER_STATUS_PENDING: _ClassVar[UserStatus]

class ToolCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TOOL_CATEGORY_UNSPECIFIED: _ClassVar[ToolCategory]
    TOOL_CATEGORY_GENERAL: _ClassVar[ToolCategory]
    TOOL_CATEGORY_DEVELOPMENT: _ClassVar[ToolCategory]
    TOOL_CATEGORY_DATA_ANALYSIS: _ClassVar[ToolCategory]
    TOOL_CATEGORY_COMMUNICATION: _ClassVar[ToolCategory]
    TOOL_CATEGORY_PRODUCTIVITY: _ClassVar[ToolCategory]
    TOOL_CATEGORY_CUSTOM: _ClassVar[ToolCategory]

class ActivityType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACTIVITY_TYPE_UNSPECIFIED: _ClassVar[ActivityType]
    ACTIVITY_TYPE_LOGIN: _ClassVar[ActivityType]
    ACTIVITY_TYPE_LOGOUT: _ClassVar[ActivityType]
    ACTIVITY_TYPE_WORKFLOW_CREATED: _ClassVar[ActivityType]
    ACTIVITY_TYPE_WORKFLOW_EXECUTED: _ClassVar[ActivityType]
    ACTIVITY_TYPE_TOOL_REGISTERED: _ClassVar[ActivityType]
    ACTIVITY_TYPE_TOOL_USED: _ClassVar[ActivityType]
    ACTIVITY_TYPE_PREFERENCES_UPDATED: _ClassVar[ActivityType]
    ACTIVITY_TYPE_ERROR_OCCURRED: _ClassVar[ActivityType]
USER_STATUS_UNSPECIFIED: UserStatus
USER_STATUS_ACTIVE: UserStatus
USER_STATUS_INACTIVE: UserStatus
USER_STATUS_SUSPENDED: UserStatus
USER_STATUS_PENDING: UserStatus
TOOL_CATEGORY_UNSPECIFIED: ToolCategory
TOOL_CATEGORY_GENERAL: ToolCategory
TOOL_CATEGORY_DEVELOPMENT: ToolCategory
TOOL_CATEGORY_DATA_ANALYSIS: ToolCategory
TOOL_CATEGORY_COMMUNICATION: ToolCategory
TOOL_CATEGORY_PRODUCTIVITY: ToolCategory
TOOL_CATEGORY_CUSTOM: ToolCategory
ACTIVITY_TYPE_UNSPECIFIED: ActivityType
ACTIVITY_TYPE_LOGIN: ActivityType
ACTIVITY_TYPE_LOGOUT: ActivityType
ACTIVITY_TYPE_WORKFLOW_CREATED: ActivityType
ACTIVITY_TYPE_WORKFLOW_EXECUTED: ActivityType
ACTIVITY_TYPE_TOOL_REGISTERED: ActivityType
ACTIVITY_TYPE_TOOL_USED: ActivityType
ACTIVITY_TYPE_PREFERENCES_UPDATED: ActivityType
ACTIVITY_TYPE_ERROR_OCCURRED: ActivityType

class GetUserProfileRequest(_message.Message):
    __slots__ = ("user_id", "include_preferences", "include_tools")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_TOOLS_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    include_preferences: bool
    include_tools: bool
    def __init__(self, user_id: _Optional[str] = ..., include_preferences: bool = ..., include_tools: bool = ...) -> None: ...

class UpdateUserPreferencesRequest(_message.Message):
    __slots__ = ("user_id", "preferences", "merge_mode")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    MERGE_MODE_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    preferences: UserPreferences
    merge_mode: bool
    def __init__(self, user_id: _Optional[str] = ..., preferences: _Optional[_Union[UserPreferences, _Mapping]] = ..., merge_mode: bool = ...) -> None: ...

class GetUserContextRequest(_message.Message):
    __slots__ = ("user_id", "session_id", "context_keys")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_KEYS_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    session_id: str
    context_keys: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, user_id: _Optional[str] = ..., session_id: _Optional[str] = ..., context_keys: _Optional[_Iterable[str]] = ...) -> None: ...

class UpdateUserContextRequest(_message.Message):
    __slots__ = ("user_id", "session_id", "context_updates", "merge_mode")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_UPDATES_FIELD_NUMBER: _ClassVar[int]
    MERGE_MODE_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    session_id: str
    context_updates: _struct_pb2.Struct
    merge_mode: bool
    def __init__(self, user_id: _Optional[str] = ..., session_id: _Optional[str] = ..., context_updates: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., merge_mode: bool = ...) -> None: ...

class GetUserToolsRequest(_message.Message):
    __slots__ = ("user_id", "category", "include_disabled")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_DISABLED_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    category: ToolCategory
    include_disabled: bool
    def __init__(self, user_id: _Optional[str] = ..., category: _Optional[_Union[ToolCategory, str]] = ..., include_disabled: bool = ...) -> None: ...

class RegisterUserToolRequest(_message.Message):
    __slots__ = ("user_id", "tool", "auto_enable")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    TOOL_FIELD_NUMBER: _ClassVar[int]
    AUTO_ENABLE_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    tool: UserTool
    auto_enable: bool
    def __init__(self, user_id: _Optional[str] = ..., tool: _Optional[_Union[UserTool, _Mapping]] = ..., auto_enable: bool = ...) -> None: ...

class GetUserActivityRequest(_message.Message):
    __slots__ = ("user_id", "start_time", "end_time", "activity_type", "limit")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_TYPE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    activity_type: ActivityType
    limit: int
    def __init__(self, user_id: _Optional[str] = ..., start_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., activity_type: _Optional[_Union[ActivityType, str]] = ..., limit: _Optional[int] = ...) -> None: ...

class GetUserProfileResponse(_message.Message):
    __slots__ = ("profile", "preferences", "tools", "status")
    PROFILE_FIELD_NUMBER: _ClassVar[int]
    PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    TOOLS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    profile: UserProfile
    preferences: UserPreferences
    tools: _containers.RepeatedCompositeFieldContainer[UserTool]
    status: UserStatus
    def __init__(self, profile: _Optional[_Union[UserProfile, _Mapping]] = ..., preferences: _Optional[_Union[UserPreferences, _Mapping]] = ..., tools: _Optional[_Iterable[_Union[UserTool, _Mapping]]] = ..., status: _Optional[_Union[UserStatus, str]] = ...) -> None: ...

class UpdateUserPreferencesResponse(_message.Message):
    __slots__ = ("updated_preferences", "success", "message")
    UPDATED_PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    updated_preferences: UserPreferences
    success: bool
    message: str
    def __init__(self, updated_preferences: _Optional[_Union[UserPreferences, _Mapping]] = ..., success: bool = ..., message: _Optional[str] = ...) -> None: ...

class GetUserContextResponse(_message.Message):
    __slots__ = ("context", "session_id", "last_updated")
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATED_FIELD_NUMBER: _ClassVar[int]
    context: _struct_pb2.Struct
    session_id: str
    last_updated: _timestamp_pb2.Timestamp
    def __init__(self, context: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., session_id: _Optional[str] = ..., last_updated: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class UpdateUserContextResponse(_message.Message):
    __slots__ = ("updated_context", "success", "message")
    UPDATED_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    updated_context: _struct_pb2.Struct
    success: bool
    message: str
    def __init__(self, updated_context: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., success: bool = ..., message: _Optional[str] = ...) -> None: ...

class GetUserToolsResponse(_message.Message):
    __slots__ = ("tools", "total_count", "available_categories")
    TOOLS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COUNT_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_CATEGORIES_FIELD_NUMBER: _ClassVar[int]
    tools: _containers.RepeatedCompositeFieldContainer[UserTool]
    total_count: int
    available_categories: _containers.RepeatedScalarFieldContainer[ToolCategory]
    def __init__(self, tools: _Optional[_Iterable[_Union[UserTool, _Mapping]]] = ..., total_count: _Optional[int] = ..., available_categories: _Optional[_Iterable[_Union[ToolCategory, str]]] = ...) -> None: ...

class RegisterUserToolResponse(_message.Message):
    __slots__ = ("registered_tool", "success", "message", "tool_id")
    REGISTERED_TOOL_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TOOL_ID_FIELD_NUMBER: _ClassVar[int]
    registered_tool: UserTool
    success: bool
    message: str
    tool_id: str
    def __init__(self, registered_tool: _Optional[_Union[UserTool, _Mapping]] = ..., success: bool = ..., message: _Optional[str] = ..., tool_id: _Optional[str] = ...) -> None: ...

class GetUserActivityResponse(_message.Message):
    __slots__ = ("activities", "metrics", "has_more", "next_cursor")
    ACTIVITIES_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    HAS_MORE_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    activities: _containers.RepeatedCompositeFieldContainer[UserActivity]
    metrics: UserMetrics
    has_more: bool
    next_cursor: str
    def __init__(self, activities: _Optional[_Iterable[_Union[UserActivity, _Mapping]]] = ..., metrics: _Optional[_Union[UserMetrics, _Mapping]] = ..., has_more: bool = ..., next_cursor: _Optional[str] = ...) -> None: ...

class UserProfile(_message.Message):
    __slots__ = ("user_id", "email", "display_name", "avatar_url", "created_at", "last_active", "status", "metadata")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    AVATAR_URL_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    LAST_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    email: str
    display_name: str
    avatar_url: str
    created_at: _timestamp_pb2.Timestamp
    last_active: _timestamp_pb2.Timestamp
    status: UserStatus
    metadata: _struct_pb2.Struct
    def __init__(self, user_id: _Optional[str] = ..., email: _Optional[str] = ..., display_name: _Optional[str] = ..., avatar_url: _Optional[str] = ..., created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., last_active: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., status: _Optional[_Union[UserStatus, str]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class UserPreferences(_message.Message):
    __slots__ = ("language", "ui_preferences", "workflow_preferences", "notification_preferences", "security_preferences", "custom_preferences")
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    UI_PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    NOTIFICATION_PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    SECURITY_PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    CUSTOM_PREFERENCES_FIELD_NUMBER: _ClassVar[int]
    language: LanguagePreference
    ui_preferences: UIPreferences
    workflow_preferences: WorkflowPreferences
    notification_preferences: NotificationPreferences
    security_preferences: SecurityPreferences
    custom_preferences: _struct_pb2.Struct
    def __init__(self, language: _Optional[_Union[LanguagePreference, _Mapping]] = ..., ui_preferences: _Optional[_Union[UIPreferences, _Mapping]] = ..., workflow_preferences: _Optional[_Union[WorkflowPreferences, _Mapping]] = ..., notification_preferences: _Optional[_Union[NotificationPreferences, _Mapping]] = ..., security_preferences: _Optional[_Union[SecurityPreferences, _Mapping]] = ..., custom_preferences: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class UIPreferences(_message.Message):
    __slots__ = ("theme", "layout", "enable_animations", "items_per_page", "favorite_tools")
    THEME_FIELD_NUMBER: _ClassVar[int]
    LAYOUT_FIELD_NUMBER: _ClassVar[int]
    ENABLE_ANIMATIONS_FIELD_NUMBER: _ClassVar[int]
    ITEMS_PER_PAGE_FIELD_NUMBER: _ClassVar[int]
    FAVORITE_TOOLS_FIELD_NUMBER: _ClassVar[int]
    theme: str
    layout: str
    enable_animations: bool
    items_per_page: int
    favorite_tools: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, theme: _Optional[str] = ..., layout: _Optional[str] = ..., enable_animations: bool = ..., items_per_page: _Optional[int] = ..., favorite_tools: _Optional[_Iterable[str]] = ...) -> None: ...

class WorkflowPreferences(_message.Message):
    __slots__ = ("auto_save_workflows", "default_timeout_seconds", "enable_streaming", "default_model", "preferred_tools")
    AUTO_SAVE_WORKFLOWS_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_TIMEOUT_SECONDS_FIELD_NUMBER: _ClassVar[int]
    ENABLE_STREAMING_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_MODEL_FIELD_NUMBER: _ClassVar[int]
    PREFERRED_TOOLS_FIELD_NUMBER: _ClassVar[int]
    auto_save_workflows: bool
    default_timeout_seconds: int
    enable_streaming: bool
    default_model: str
    preferred_tools: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, auto_save_workflows: bool = ..., default_timeout_seconds: _Optional[int] = ..., enable_streaming: bool = ..., default_model: _Optional[str] = ..., preferred_tools: _Optional[_Iterable[str]] = ...) -> None: ...

class NotificationPreferences(_message.Message):
    __slots__ = ("email_notifications", "push_notifications", "workflow_completion", "error_alerts", "notification_channels")
    EMAIL_NOTIFICATIONS_FIELD_NUMBER: _ClassVar[int]
    PUSH_NOTIFICATIONS_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_COMPLETION_FIELD_NUMBER: _ClassVar[int]
    ERROR_ALERTS_FIELD_NUMBER: _ClassVar[int]
    NOTIFICATION_CHANNELS_FIELD_NUMBER: _ClassVar[int]
    email_notifications: bool
    push_notifications: bool
    workflow_completion: bool
    error_alerts: bool
    notification_channels: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, email_notifications: bool = ..., push_notifications: bool = ..., workflow_completion: bool = ..., error_alerts: bool = ..., notification_channels: _Optional[_Iterable[str]] = ...) -> None: ...

class SecurityPreferences(_message.Message):
    __slots__ = ("require_mfa", "session_timeout_minutes", "allow_tool_registration", "trusted_domains")
    REQUIRE_MFA_FIELD_NUMBER: _ClassVar[int]
    SESSION_TIMEOUT_MINUTES_FIELD_NUMBER: _ClassVar[int]
    ALLOW_TOOL_REGISTRATION_FIELD_NUMBER: _ClassVar[int]
    TRUSTED_DOMAINS_FIELD_NUMBER: _ClassVar[int]
    require_mfa: bool
    session_timeout_minutes: int
    allow_tool_registration: bool
    trusted_domains: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, require_mfa: bool = ..., session_timeout_minutes: _Optional[int] = ..., allow_tool_registration: bool = ..., trusted_domains: _Optional[_Iterable[str]] = ...) -> None: ...

class UserTool(_message.Message):
    __slots__ = ("tool_id", "name", "description", "category", "configuration", "enabled", "registered_at", "last_used", "usage_count")
    TOOL_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    CONFIGURATION_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    REGISTERED_AT_FIELD_NUMBER: _ClassVar[int]
    LAST_USED_FIELD_NUMBER: _ClassVar[int]
    USAGE_COUNT_FIELD_NUMBER: _ClassVar[int]
    tool_id: str
    name: str
    description: str
    category: ToolCategory
    configuration: _struct_pb2.Struct
    enabled: bool
    registered_at: _timestamp_pb2.Timestamp
    last_used: _timestamp_pb2.Timestamp
    usage_count: int
    def __init__(self, tool_id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., category: _Optional[_Union[ToolCategory, str]] = ..., configuration: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., enabled: bool = ..., registered_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., last_used: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., usage_count: _Optional[int] = ...) -> None: ...

class UserActivity(_message.Message):
    __slots__ = ("activity_id", "user_id", "activity_type", "description", "details", "timestamp", "session_id")
    ACTIVITY_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_TYPE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    activity_id: str
    user_id: str
    activity_type: ActivityType
    description: str
    details: _struct_pb2.Struct
    timestamp: _timestamp_pb2.Timestamp
    session_id: str
    def __init__(self, activity_id: _Optional[str] = ..., user_id: _Optional[str] = ..., activity_type: _Optional[_Union[ActivityType, str]] = ..., description: _Optional[str] = ..., details: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., session_id: _Optional[str] = ...) -> None: ...

class UserMetrics(_message.Message):
    __slots__ = ("total_workflows", "total_executions", "total_tool_calls", "first_activity", "last_activity", "active_sessions", "tool_usage")
    TOTAL_WORKFLOWS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_EXECUTIONS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_TOOL_CALLS_FIELD_NUMBER: _ClassVar[int]
    FIRST_ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    LAST_ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_SESSIONS_FIELD_NUMBER: _ClassVar[int]
    TOOL_USAGE_FIELD_NUMBER: _ClassVar[int]
    total_workflows: int
    total_executions: int
    total_tool_calls: int
    first_activity: _timestamp_pb2.Timestamp
    last_activity: _timestamp_pb2.Timestamp
    active_sessions: int
    tool_usage: _containers.RepeatedCompositeFieldContainer[ToolUsage]
    def __init__(self, total_workflows: _Optional[int] = ..., total_executions: _Optional[int] = ..., total_tool_calls: _Optional[int] = ..., first_activity: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., last_activity: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., active_sessions: _Optional[int] = ..., tool_usage: _Optional[_Iterable[_Union[ToolUsage, _Mapping]]] = ...) -> None: ...

class ToolUsage(_message.Message):
    __slots__ = ("tool_name", "usage_count", "last_used", "success_rate")
    TOOL_NAME_FIELD_NUMBER: _ClassVar[int]
    USAGE_COUNT_FIELD_NUMBER: _ClassVar[int]
    LAST_USED_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_RATE_FIELD_NUMBER: _ClassVar[int]
    tool_name: str
    usage_count: int
    last_used: _timestamp_pb2.Timestamp
    success_rate: float
    def __init__(self, tool_name: _Optional[str] = ..., usage_count: _Optional[int] = ..., last_used: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., success_rate: _Optional[float] = ...) -> None: ...

class LanguagePreference(_message.Message):
    __slots__ = ("code", "display_name", "is_default")
    CODE_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    IS_DEFAULT_FIELD_NUMBER: _ClassVar[int]
    code: str
    display_name: str
    is_default: bool
    def __init__(self, code: _Optional[str] = ..., display_name: _Optional[str] = ..., is_default: bool = ...) -> None: ...
