package models

import (
	"time"
)

// Execution requests
type ExecuteWorkflowRequest struct {
	WorkflowID string                 `json:"workflow_id" binding:"required" validate:"required,uuid"`
	Parameters map[string]interface{} `json:"parameters,omitempty"`
	TestMode   bool                   `json:"test_mode,omitempty"`
}

type CancelExecutionRequest struct {
	Reason string `json:"reason,omitempty" validate:"omitempty,max=500"`
}

type ListExecutionsRequest struct {
	WorkflowID string `form:"workflow_id,omitempty" validate:"omitempty,uuid"`
	Status     string `form:"status,omitempty" validate:"omitempty,oneof=pending running completed failed cancelled"`
	Limit      int32  `form:"limit,omitempty" validate:"omitempty,min=1,max=100"`
	Offset     int32  `form:"offset,omitempty" validate:"omitempty,min=0"`
}

type GetExecutionLogsRequest struct {
	Limit  int32 `form:"limit,omitempty" validate:"omitempty,min=1,max=1000"`
	Offset int32 `form:"offset,omitempty" validate:"omitempty,min=0"`
}

// Execution responses
type ExecuteWorkflowResponse struct {
	ExecutionID string             `json:"execution_id"`
	Status      string             `json:"status"`
	Metadata    *ExecutionMetadata `json:"metadata,omitempty"`
}

type GetExecutionStatusResponse struct {
	Execution *ExecutionResult `json:"execution"`
}

type ListExecutionsResponse struct {
	Executions []*ExecutionResult `json:"executions"`
	TotalCount int32              `json:"total_count"`
	Limit      int32              `json:"limit"`
	Offset     int32              `json:"offset"`
}

type GetExecutionLogsResponse struct {
	Logs       []*ExecutionLog `json:"logs"`
	TotalCount int32           `json:"total_count"`
}

type CancelExecutionResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message,omitempty"`
}

// Execution data models
type ExecutionResult struct {
	ExecutionID      string                 `json:"execution_id"`
	WorkflowID       string                 `json:"workflow_id"`
	UserID           string                 `json:"user_id"`
	Status           string                 `json:"status"`
	StepResults      []*StepResult          `json:"step_results,omitempty"`
	Errors           []*ExecutionError      `json:"errors,omitempty"`
	ExecutionTime    float32                `json:"execution_time_seconds"`
	StartedAt        time.Time              `json:"started_at"`
	CompletedAt      *time.Time             `json:"completed_at,omitempty"`
	TestMode         bool                   `json:"test_mode"`
	Metadata         *ExecutionMetadata     `json:"metadata,omitempty"`
}

type StepResult struct {
	StepID        string                 `json:"step_id"`
	StepName      string                 `json:"step_name"`
	ToolName      string                 `json:"tool_name"`
	Status        string                 `json:"status"`
	Result        map[string]interface{} `json:"result,omitempty"`
	ExecutionTime float32                `json:"execution_time"`
	Timestamp     time.Time              `json:"timestamp"`
	RetryCount    int32                  `json:"retry_count"`
	ErrorMessage  string                 `json:"error_message,omitempty"`
}

type ExecutionError struct {
	StepID     string                 `json:"step_id"`
	Type       string                 `json:"type"`
	Message    string                 `json:"message"`
	Details    map[string]interface{} `json:"details,omitempty"`
	Timestamp  time.Time              `json:"timestamp"`
	RetryCount int32                  `json:"retry_count"`
}

type ExecutionLog struct {
	ID          string                 `json:"id"`
	ExecutionID string                 `json:"execution_id"`
	StepID      string                 `json:"step_id,omitempty"`
	Level       string                 `json:"level"`
	Message     string                 `json:"message"`
	LogData     map[string]interface{} `json:"log_data,omitempty"`
	Timestamp   time.Time              `json:"timestamp"`
}

type ExecutionMetadata struct {
	TotalSteps      int32                  `json:"total_steps"`
	CompletedSteps  int32                  `json:"completed_steps"`
	FailedSteps     int32                  `json:"failed_steps"`
	SuccessRate     float32                `json:"success_rate"`
	WorkflowMeta    map[string]interface{} `json:"workflow_metadata,omitempty"`
	ParallelGroups  []string               `json:"parallel_groups,omitempty"`
}

// Streaming models
type ExecutionUpdate struct {
	ExecutionID        string                 `json:"execution_id"`
	StepID             string                 `json:"step_id,omitempty"`
	StepName           string                 `json:"step_name,omitempty"`
	Type               string                 `json:"type"` // "step_start", "step_complete", "step_error", "execution_complete"
	Status             string                 `json:"status"`
	Message            string                 `json:"message"`
	ProgressPercentage float32                `json:"progress_percentage"`
	Timestamp          time.Time              `json:"timestamp"`
	Data               map[string]interface{} `json:"data,omitempty"`
	Error              string                 `json:"error,omitempty"`
}

// Constants for execution statuses
const (
	ExecutionStatusPending   = "pending"
	ExecutionStatusRunning   = "running"
	ExecutionStatusCompleted = "completed"
	ExecutionStatusFailed    = "failed"
	ExecutionStatusCancelled = "cancelled"
)

// Constants for step statuses
const (
	StepStatusWaiting   = "waiting"
	StepStatusRunning   = "running"
	StepStatusCompleted = "completed"
	StepStatusFailed    = "failed"
	StepStatusSkipped   = "skipped"
	StepStatusRetrying  = "retrying"
)

// Constants for execution update types
const (
	UpdateTypeStepStart         = "step_start"
	UpdateTypeStepComplete      = "step_complete"
	UpdateTypeStepError         = "step_error"
	UpdateTypeExecutionComplete = "execution_complete"
	UpdateTypeExecutionError    = "execution_error"
) 