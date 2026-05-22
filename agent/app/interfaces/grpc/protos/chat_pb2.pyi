from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SessionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SESSION_TYPE_UNSPECIFIED: _ClassVar[SessionType]
    SESSION_TYPE_WORKFLOW: _ClassVar[SessionType]
    SESSION_TYPE_CHAT: _ClassVar[SessionType]
    SESSION_TYPE_TOOL_DISCOVERY: _ClassVar[SessionType]
    SESSION_TYPE_ASSISTANCE: _ClassVar[SessionType]

class MessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MESSAGE_TYPE_UNSPECIFIED: _ClassVar[MessageType]
    MESSAGE_TYPE_USER: _ClassVar[MessageType]
    MESSAGE_TYPE_ASSISTANT: _ClassVar[MessageType]
    MESSAGE_TYPE_SYSTEM: _ClassVar[MessageType]
    MESSAGE_TYPE_TOOL_CALL: _ClassVar[MessageType]
    MESSAGE_TYPE_TOOL_RESULT: _ClassVar[MessageType]

class SessionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SESSION_STATUS_UNSPECIFIED: _ClassVar[SessionStatus]
    SESSION_STATUS_ACTIVE: _ClassVar[SessionStatus]
    SESSION_STATUS_ENDED: _ClassVar[SessionStatus]
    SESSION_STATUS_ERROR: _ClassVar[SessionStatus]
    SESSION_STATUS_TIMEOUT: _ClassVar[SessionStatus]

class ResponseStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RESPONSE_STATUS_UNSPECIFIED: _ClassVar[ResponseStatus]
    RESPONSE_STATUS_SUCCESS: _ClassVar[ResponseStatus]
    RESPONSE_STATUS_PROCESSING: _ClassVar[ResponseStatus]
    RESPONSE_STATUS_ERROR: _ClassVar[ResponseStatus]
    RESPONSE_STATUS_PARTIAL: _ClassVar[ResponseStatus]

class ToolCallStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TOOL_CALL_STATUS_UNSPECIFIED: _ClassVar[ToolCallStatus]
    TOOL_CALL_STATUS_PENDING: _ClassVar[ToolCallStatus]
    TOOL_CALL_STATUS_SUCCESS: _ClassVar[ToolCallStatus]
    TOOL_CALL_STATUS_ERROR: _ClassVar[ToolCallStatus]
    TOOL_CALL_STATUS_TIMEOUT: _ClassVar[ToolCallStatus]
SESSION_TYPE_UNSPECIFIED: SessionType
SESSION_TYPE_WORKFLOW: SessionType
SESSION_TYPE_CHAT: SessionType
SESSION_TYPE_TOOL_DISCOVERY: SessionType
SESSION_TYPE_ASSISTANCE: SessionType
MESSAGE_TYPE_UNSPECIFIED: MessageType
MESSAGE_TYPE_USER: MessageType
MESSAGE_TYPE_ASSISTANT: MessageType
MESSAGE_TYPE_SYSTEM: MessageType
MESSAGE_TYPE_TOOL_CALL: MessageType
MESSAGE_TYPE_TOOL_RESULT: MessageType
SESSION_STATUS_UNSPECIFIED: SessionStatus
SESSION_STATUS_ACTIVE: SessionStatus
SESSION_STATUS_ENDED: SessionStatus
SESSION_STATUS_ERROR: SessionStatus
SESSION_STATUS_TIMEOUT: SessionStatus
RESPONSE_STATUS_UNSPECIFIED: ResponseStatus
RESPONSE_STATUS_SUCCESS: ResponseStatus
RESPONSE_STATUS_PROCESSING: ResponseStatus
RESPONSE_STATUS_ERROR: ResponseStatus
RESPONSE_STATUS_PARTIAL: ResponseStatus
TOOL_CALL_STATUS_UNSPECIFIED: ToolCallStatus
TOOL_CALL_STATUS_PENDING: ToolCallStatus
TOOL_CALL_STATUS_SUCCESS: ToolCallStatus
TOOL_CALL_STATUS_ERROR: ToolCallStatus
TOOL_CALL_STATUS_TIMEOUT: ToolCallStatus

class StartChatSessionRequest(_message.Message):
    __slots__ = ("user_id", "session_type", "context", "capabilities")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_TYPE_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    session_type: SessionType
    context: _struct_pb2.Struct
    capabilities: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, user_id: _Optional[str] = ..., session_type: _Optional[_Union[SessionType, str]] = ..., context: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., capabilities: _Optional[_Iterable[str]] = ...) -> None: ...

class SendMessageRequest(_message.Message):
    __slots__ = ("session_id", "message", "message_type", "metadata", "stream_response")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    STREAM_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    message: str
    message_type: MessageType
    metadata: _struct_pb2.Struct
    stream_response: bool
    def __init__(self, session_id: _Optional[str] = ..., message: _Optional[str] = ..., message_type: _Optional[_Union[MessageType, str]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., stream_response: bool = ...) -> None: ...

class GetChatHistoryRequest(_message.Message):
    __slots__ = ("session_id", "limit", "cursor", "start_time", "end_time")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    CURSOR_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    limit: int
    cursor: str
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    def __init__(self, session_id: _Optional[str] = ..., limit: _Optional[int] = ..., cursor: _Optional[str] = ..., start_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class EndChatSessionRequest(_message.Message):
    __slots__ = ("session_id", "reason")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    reason: str
    def __init__(self, session_id: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class GetSessionContextRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class StartChatSessionResponse(_message.Message):
    __slots__ = ("session_id", "status", "context", "available_tools", "message")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_TOOLS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    status: SessionStatus
    context: _struct_pb2.Struct
    available_tools: _containers.RepeatedScalarFieldContainer[str]
    message: str
    def __init__(self, session_id: _Optional[str] = ..., status: _Optional[_Union[SessionStatus, str]] = ..., context: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., available_tools: _Optional[_Iterable[str]] = ..., message: _Optional[str] = ...) -> None: ...

class ChatMessageResponse(_message.Message):
    __slots__ = ("session_id", "message_id", "content", "message_type", "status", "timestamp", "metadata", "is_final", "tool_calls")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    IS_FINAL_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALLS_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    message_id: str
    content: str
    message_type: MessageType
    status: ResponseStatus
    timestamp: _timestamp_pb2.Timestamp
    metadata: _struct_pb2.Struct
    is_final: bool
    tool_calls: _containers.RepeatedCompositeFieldContainer[ToolCall]
    def __init__(self, session_id: _Optional[str] = ..., message_id: _Optional[str] = ..., content: _Optional[str] = ..., message_type: _Optional[_Union[MessageType, str]] = ..., status: _Optional[_Union[ResponseStatus, str]] = ..., timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., is_final: bool = ..., tool_calls: _Optional[_Iterable[_Union[ToolCall, _Mapping]]] = ...) -> None: ...

class GetChatHistoryResponse(_message.Message):
    __slots__ = ("messages", "next_cursor", "has_more", "total_count")
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    NEXT_CURSOR_FIELD_NUMBER: _ClassVar[int]
    HAS_MORE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COUNT_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[ChatMessage]
    next_cursor: str
    has_more: bool
    total_count: int
    def __init__(self, messages: _Optional[_Iterable[_Union[ChatMessage, _Mapping]]] = ..., next_cursor: _Optional[str] = ..., has_more: bool = ..., total_count: _Optional[int] = ...) -> None: ...

class EndChatSessionResponse(_message.Message):
    __slots__ = ("session_id", "status", "message", "ended_at")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ENDED_AT_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    status: SessionStatus
    message: str
    ended_at: _timestamp_pb2.Timestamp
    def __init__(self, session_id: _Optional[str] = ..., status: _Optional[_Union[SessionStatus, str]] = ..., message: _Optional[str] = ..., ended_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetSessionContextResponse(_message.Message):
    __slots__ = ("session_id", "status", "context", "active_tools", "metrics")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_TOOLS_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    status: SessionStatus
    context: _struct_pb2.Struct
    active_tools: _containers.RepeatedScalarFieldContainer[str]
    metrics: SessionMetrics
    def __init__(self, session_id: _Optional[str] = ..., status: _Optional[_Union[SessionStatus, str]] = ..., context: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., active_tools: _Optional[_Iterable[str]] = ..., metrics: _Optional[_Union[SessionMetrics, _Mapping]] = ...) -> None: ...

class ChatMessage(_message.Message):
    __slots__ = ("message_id", "session_id", "content", "message_type", "timestamp", "metadata", "tool_calls")
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_TYPE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALLS_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    session_id: str
    content: str
    message_type: MessageType
    timestamp: _timestamp_pb2.Timestamp
    metadata: _struct_pb2.Struct
    tool_calls: _containers.RepeatedCompositeFieldContainer[ToolCall]
    def __init__(self, message_id: _Optional[str] = ..., session_id: _Optional[str] = ..., content: _Optional[str] = ..., message_type: _Optional[_Union[MessageType, str]] = ..., timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., tool_calls: _Optional[_Iterable[_Union[ToolCall, _Mapping]]] = ...) -> None: ...

class ToolCall(_message.Message):
    __slots__ = ("tool_id", "tool_name", "arguments", "result", "status", "timestamp")
    TOOL_ID_FIELD_NUMBER: _ClassVar[int]
    TOOL_NAME_FIELD_NUMBER: _ClassVar[int]
    ARGUMENTS_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    tool_id: str
    tool_name: str
    arguments: _struct_pb2.Struct
    result: str
    status: ToolCallStatus
    timestamp: _timestamp_pb2.Timestamp
    def __init__(self, tool_id: _Optional[str] = ..., tool_name: _Optional[str] = ..., arguments: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., result: _Optional[str] = ..., status: _Optional[_Union[ToolCallStatus, str]] = ..., timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SessionMetrics(_message.Message):
    __slots__ = ("message_count", "tool_calls_count", "session_duration", "tokens_used")
    MESSAGE_COUNT_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALLS_COUNT_FIELD_NUMBER: _ClassVar[int]
    SESSION_DURATION_FIELD_NUMBER: _ClassVar[int]
    TOKENS_USED_FIELD_NUMBER: _ClassVar[int]
    message_count: int
    tool_calls_count: int
    session_duration: _timestamp_pb2.Timestamp
    tokens_used: int
    def __init__(self, message_count: _Optional[int] = ..., tool_calls_count: _Optional[int] = ..., session_duration: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., tokens_used: _Optional[int] = ...) -> None: ...
