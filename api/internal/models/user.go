package models

import (
	"time"
)

// User profile requests
type UpdateUserPreferencesRequest struct {
	Preferences *UserPreferences `json:"preferences" binding:"required" validate:"required"`
	MergeMode   bool             `json:"merge_mode,omitempty"`
}

type UpdateUserContextRequest struct {
	ContextUpdates map[string]interface{} `json:"context_updates" binding:"required" validate:"required"`
	MergeMode      bool                   `json:"merge_mode,omitempty"`
}

type RegisterUserToolRequest struct {
	Tool       *UserTool `json:"tool" binding:"required" validate:"required"`
	AutoEnable bool      `json:"auto_enable,omitempty"`
}

type GetUserToolsRequest struct {
	Category        string `form:"category,omitempty" validate:"omitempty,oneof=productivity automation communication data_processing ai_tools custom"`
	IncludeDisabled bool   `form:"include_disabled,omitempty"`
}

type GetUserActivityRequest struct {
	StartTime    time.Time `form:"start_time,omitempty"`
	EndTime      time.Time `form:"end_time,omitempty"`
	ActivityType string    `form:"activity_type,omitempty" validate:"omitempty,oneof=workflow_generation execution chat tool_usage login logout"`
	Limit        int32     `form:"limit,omitempty" validate:"omitempty,min=1,max=100"`
}

// User profile responses
type GetUserProfileResponse struct {
	Profile     *UserProfile     `json:"profile"`
	Preferences *UserPreferences `json:"preferences,omitempty"`
	Tools       []*UserTool      `json:"tools,omitempty"`
	Status      string           `json:"status"`
}

type UpdateUserPreferencesResponse struct {
	UpdatedPreferences *UserPreferences `json:"updated_preferences"`
	Success            bool             `json:"success"`
	Message            string           `json:"message,omitempty"`
}

type GetUserContextResponse struct {
	Context     map[string]interface{} `json:"context"`
	SessionID   string                 `json:"session_id,omitempty"`
	LastUpdated time.Time              `json:"last_updated"`
}

type UpdateUserContextResponse struct {
	UpdatedContext map[string]interface{} `json:"updated_context"`
	Success        bool                   `json:"success"`
	Message        string                 `json:"message,omitempty"`
}

type GetUserToolsResponse struct {
	Tools               []*UserTool     `json:"tools"`
	TotalCount          int32           `json:"total_count"`
	AvailableCategories []string        `json:"available_categories"`
}

type RegisterUserToolResponse struct {
	RegisteredTool *UserTool `json:"registered_tool"`
	Success        bool      `json:"success"`
	Message        string    `json:"message,omitempty"`
	ToolID         string    `json:"tool_id,omitempty"`
}

type GetUserActivityResponse struct {
	Activities []*UserActivity `json:"activities"`
	Metrics    *UserMetrics    `json:"metrics"`
	HasMore    bool            `json:"has_more"`
	NextCursor string          `json:"next_cursor,omitempty"`
}

// User data models
type UserProfile struct {
	UserID      string                 `json:"user_id"`
	Email       string                 `json:"email"`
	DisplayName string                 `json:"display_name"`
	AvatarURL   string                 `json:"avatar_url,omitempty"`
	CreatedAt   time.Time              `json:"created_at"`
	LastActive  time.Time              `json:"last_active"`
	Status      string                 `json:"status"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

type UserPreferences struct {
	Language               *LanguagePreference     `json:"language,omitempty"`
	UIPreferences          *UIPreferences          `json:"ui_preferences,omitempty"`
	WorkflowPreferences    *WorkflowPreferences    `json:"workflow_preferences,omitempty"`
	NotificationPrefs      *NotificationPreferences `json:"notification_preferences,omitempty"`
	SecurityPreferences    *SecurityPreferences    `json:"security_preferences,omitempty"`
	CustomPreferences      map[string]interface{}  `json:"custom_preferences,omitempty"`
}

type LanguagePreference struct {
	Code        string `json:"code" validate:"required,len=2"`
	Region      string `json:"region,omitempty" validate:"omitempty,len=2"`
	DisplayName string `json:"display_name"`
}

type UIPreferences struct {
	Theme            string   `json:"theme" validate:"omitempty,oneof=light dark auto"`
	Layout           string   `json:"layout" validate:"omitempty,oneof=compact normal spacious"`
	EnableAnimations bool     `json:"enable_animations"`
	ItemsPerPage     int32    `json:"items_per_page" validate:"omitempty,min=10,max=100"`
	FavoriteTools    []string `json:"favorite_tools,omitempty"`
}

type WorkflowPreferences struct {
	AutoSaveWorkflows     bool     `json:"auto_save_workflows"`
	DefaultTimeoutSeconds int32    `json:"default_timeout_seconds" validate:"omitempty,min=30,max=3600"`
	EnableStreaming       bool     `json:"enable_streaming"`
	DefaultModel          string   `json:"default_model,omitempty"`
	PreferredTools        []string `json:"preferred_tools,omitempty"`
}

type NotificationPreferences struct {
	EmailNotifications    bool     `json:"email_notifications"`
	PushNotifications     bool     `json:"push_notifications"`
	WorkflowCompletion    bool     `json:"workflow_completion"`
	ErrorAlerts           bool     `json:"error_alerts"`
	NotificationChannels  []string `json:"notification_channels,omitempty"`
}

type SecurityPreferences struct {
	RequireMFA        bool     `json:"require_mfa"`
	SessionTimeoutMin int32    `json:"session_timeout_minutes" validate:"omitempty,min=15,max=480"`
	AllowToolReg      bool     `json:"allow_tool_registration"`
	TrustedDomains    []string `json:"trusted_domains,omitempty"`
}

type UserTool struct {
	ToolID       string                 `json:"tool_id"`
	Name         string                 `json:"name" validate:"required,min=1,max=100"`
	Description  string                 `json:"description" validate:"omitempty,max=500"`
	Category     string                 `json:"category" validate:"required,oneof=productivity automation communication data_processing ai_tools custom"`
	Configuration map[string]interface{} `json:"configuration,omitempty"`
	Enabled      bool                   `json:"enabled"`
	RegisteredAt time.Time              `json:"registered_at"`
	LastUsed     *time.Time             `json:"last_used,omitempty"`
	UsageCount   int32                  `json:"usage_count"`
}

type UserActivity struct {
	ActivityID   string                 `json:"activity_id"`
	UserID       string                 `json:"user_id"`
	ActivityType string                 `json:"activity_type"`
	Description  string                 `json:"description"`
	Details      map[string]interface{} `json:"details,omitempty"`
	Timestamp    time.Time              `json:"timestamp"`
	SessionID    string                 `json:"session_id,omitempty"`
}

type UserMetrics struct {
	TotalWorkflows      int32        `json:"total_workflows"`
	TotalExecutions     int32        `json:"total_executions"`
	TotalChatSessions   int32        `json:"total_chat_sessions"`
	ToolUsage           []*ToolUsage `json:"tool_usage,omitempty"`
	LastLoginAt         time.Time    `json:"last_login_at"`
	AverageSessionTime  int64        `json:"average_session_time_minutes"`
}

type ToolUsage struct {
	ToolName   string `json:"tool_name"`
	UsageCount int32  `json:"usage_count"`
	LastUsed   time.Time `json:"last_used"`
}

// Constants for user statuses
const (
	UserStatusActive    = "active"
	UserStatusInactive  = "inactive"
	UserStatusSuspended = "suspended"
	UserStatusPending   = "pending"
)

// Constants for tool categories
const (
	ToolCategoryProductivity   = "productivity"
	ToolCategoryAutomation     = "automation"
	ToolCategoryCommunication  = "communication"
	ToolCategoryDataProcessing = "data_processing"
	ToolCategoryAITools        = "ai_tools"
	ToolCategoryCustom         = "custom"
)

// Constants for activity types
const (
	ActivityTypeWorkflowGeneration = "workflow_generation"
	ActivityTypeExecution          = "execution"
	ActivityTypeChat               = "chat"
	ActivityTypeToolUsage          = "tool_usage"
	ActivityTypeLogin              = "login"
	ActivityTypeLogout             = "logout"
) 