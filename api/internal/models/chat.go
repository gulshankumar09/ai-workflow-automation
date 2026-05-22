package models

import (
	"time"
)

// Chat session requests
type StartChatSessionRequest struct {
	SessionType  string                 `json:"session_type" binding:"required" validate:"required,oneof=workflow chat tool_discovery assistance"`
	Context      map[string]interface{} `json:"context,omitempty"`
	Capabilities []string               `json:"capabilities,omitempty"`
}

type SendMessageRequest struct {
	Message     string                 `json:"message" binding:"required" validate:"required,min=1,max=10000"`
	MessageType string                 `json:"message_type,omitempty" validate:"omitempty,oneof=user assistant system tool_call tool_result"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	Stream      bool                   `json:"stream,omitempty"`
}

type GetChatHistoryRequest struct {
	Limit     int32     `form:"limit,omitempty" validate:"omitempty,min=1,max=100"`
	Cursor    string    `form:"cursor,omitempty"`
	StartTime time.Time `form:"start_time,omitempty"`
	EndTime   time.Time `form:"end_time,omitempty"`
}

type EndChatSessionRequest struct {
	Reason string `json:"reason,omitempty" validate:"omitempty,max=500"`
}

// Chat session responses
type StartChatSessionResponse struct {
	SessionID      string                 `json:"session_id"`
	Status         string                 `json:"status"`
	Context        map[string]interface{} `json:"context,omitempty"`
	AvailableTools []string               `json:"available_tools,omitempty"`
	Message        string                 `json:"message,omitempty"`
}

type GetChatHistoryResponse struct {
	Messages   []*ChatMessage `json:"messages"`
	NextCursor string         `json:"next_cursor,omitempty"`
	HasMore    bool           `json:"has_more"`
	TotalCount int32          `json:"total_count"`
}

type GetSessionContextResponse struct {
	SessionID    string                 `json:"session_id"`
	Status       string                 `json:"status"`
	Context      map[string]interface{} `json:"context,omitempty"`
	ActiveTools  []string               `json:"active_tools,omitempty"`
	Metrics      *SessionMetrics        `json:"metrics,omitempty"`
}

type EndChatSessionResponse struct {
	SessionID string    `json:"session_id"`
	Status    string    `json:"status"`
	Message   string    `json:"message,omitempty"`
	EndedAt   time.Time `json:"ended_at"`
}

// Chat data models
type ChatMessage struct {
	MessageID   string                 `json:"message_id"`
	SessionID   string                 `json:"session_id"`
	Content     string                 `json:"content"`
	MessageType string                 `json:"message_type"`
	Timestamp   time.Time              `json:"timestamp"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	ToolCalls   []*ToolCall            `json:"tool_calls,omitempty"`
}

type ToolCall struct {
	ToolID    string                 `json:"tool_id"`
	ToolName  string                 `json:"tool_name"`
	Arguments map[string]interface{} `json:"arguments,omitempty"`
	Result    string                 `json:"result,omitempty"`
	Status    string                 `json:"status"`
	Timestamp time.Time              `json:"timestamp"`
}

type SessionMetrics struct {
	MessageCount    int32     `json:"message_count"`
	ToolCallsCount  int32     `json:"tool_calls_count"`
	SessionDuration time.Time `json:"session_duration"`
	TokensUsed      int32     `json:"tokens_used"`
}

// Streaming models
type ChatMessageResponse struct {
	SessionID   string                 `json:"session_id"`
	MessageID   string                 `json:"message_id"`
	Content     string                 `json:"content"`
	MessageType string                 `json:"message_type"`
	Status      string                 `json:"status"`
	Timestamp   time.Time              `json:"timestamp"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	IsFinal     bool                   `json:"is_final"`
	ToolCalls   []*ToolCall            `json:"tool_calls,omitempty"`
}

// WebSocket message types
type WebSocketMessage struct {
	Type    string      `json:"type"`
	Payload interface{} `json:"payload"`
}

type WebSocketChatMessage struct {
	Action  string                 `json:"action"` // "send_message", "typing", "stop_typing"
	Message string                 `json:"message,omitempty"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// Constants for session types
const (
	SessionTypeWorkflow       = "workflow"
	SessionTypeChat          = "chat"
	SessionTypeToolDiscovery = "tool_discovery"
	SessionTypeAssistance    = "assistance"
)

// Constants for session statuses
const (
	SessionStatusActive  = "active"
	SessionStatusEnded   = "ended"
	SessionStatusError   = "error"
	SessionStatusTimeout = "timeout"
)

// Constants for message types
const (
	MessageTypeUser       = "user"
	MessageTypeAssistant  = "assistant"
	MessageTypeSystem     = "system"
	MessageTypeToolCall   = "tool_call"
	MessageTypeToolResult = "tool_result"
)

// Constants for response statuses
const (
	ResponseStatusSuccess    = "success"
	ResponseStatusProcessing = "processing"
	ResponseStatusError      = "error"
	ResponseStatusPartial    = "partial"
)

// Constants for tool call statuses
const (
	ToolCallStatusPending = "pending"
	ToolCallStatusSuccess = "success"
	ToolCallStatusError   = "error"
	ToolCallStatusTimeout = "timeout"
)

// Constants for WebSocket message types
const (
	WSMessageTypeChat     = "chat"
	WSMessageTypeStatus   = "status"
	WSMessageTypeError    = "error"
	WSMessageTypeTyping   = "typing"
	WSMessageTypePing     = "ping"
	WSMessageTypePong     = "pong"
) 