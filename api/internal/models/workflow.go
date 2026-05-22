package models

import (
	"time"

	"google.golang.org/protobuf/types/known/structpb"
)

// Workflow generation requests
type GenerateWorkflowRequest struct {
	UserRequest string                 `json:"user_request" binding:"required,min=10,max=1000" validate:"required"`
	Context     map[string]interface{} `json:"context,omitempty"`
	TestMode    bool                   `json:"test_mode,omitempty"`
}

type GenerateWorkflowResponse struct {
	WorkflowID string             `json:"workflow_id"`
	Definition *WorkflowDefinition `json:"definition"`
	Steps      []*WorkflowStep     `json:"steps"`
	Status     string              `json:"status"`
	Metadata   *GenerationMetadata `json:"metadata,omitempty"`
}

// Workflow management requests
type UpdateWorkflowRequest struct {
	Status  string                 `json:"status,omitempty" validate:"omitempty,oneof=draft active paused archived"`
	Updates map[string]interface{} `json:"updates,omitempty"`
}

type ValidateWorkflowRequest struct {
	Workflow *WorkflowDefinition `json:"workflow" binding:"required" validate:"required"`
}

// Workflow data models
type WorkflowDefinition struct {
	ID          string                 `json:"id"`
	UserID      string                 `json:"user_id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Steps       []*WorkflowStep        `json:"steps"`
	Status      string                 `json:"status"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
}

type WorkflowStep struct {
	ID               string                 `json:"id"`
	Name             string                 `json:"name"`
	ToolName         string                 `json:"tool_name"`
	Parameters       map[string]interface{} `json:"parameters,omitempty"`
	Dependencies     []string               `json:"dependencies,omitempty"`
	ParallelEligible bool                   `json:"parallel_eligible"`
	RetryCount       int32                  `json:"retry_count"`
	MaxRetries       int32                  `json:"max_retries"`
	RetryDelay       int32                  `json:"retry_delay"`
	Metadata         map[string]interface{} `json:"metadata,omitempty"`
}

type GenerationMetadata struct {
	TotalSteps       int32                  `json:"total_steps"`
	ToolCount        int32                  `json:"tool_count"`
	GenerationTime   float32                `json:"generation_time_seconds"`
	UsedEntities     []string               `json:"used_entities,omitempty"`
	ParsedIntent     map[string]interface{} `json:"parsed_intent,omitempty"`
}



// List workflows request/response
type ListWorkflowsRequest struct {
	Status string `form:"status,omitempty" validate:"omitempty,oneof=draft active paused archived"`
	Limit  int32  `form:"limit,omitempty" validate:"omitempty,min=1,max=100"`
	Offset int32  `form:"offset,omitempty" validate:"omitempty,min=0"`
}

type ListWorkflowsResponse struct {
	Workflows  []*WorkflowDefinition `json:"workflows"`
	TotalCount int32                 `json:"total_count"`
	Limit      int32                 `json:"limit"`
	Offset     int32                 `json:"offset"`
}

// Streaming models
type WorkflowGenerationProgress struct {
	Stage                   string               `json:"stage"`
	ProgressPercentage      float32              `json:"progress_percentage"`
	Message                 string               `json:"message"`
	Details                 string               `json:"details,omitempty"`
	EstimatedTimeRemaining  int64                `json:"estimated_time_remaining_ms,omitempty"`
	PartialWorkflow         *WorkflowDefinition  `json:"partial_workflow,omitempty"`
	IsComplete              bool                 `json:"is_complete"`
	ErrorMessage            string               `json:"error_message,omitempty"`
}

// Helper functions to convert between API models and protobuf

func (w *WorkflowDefinition) ToProtobufStruct() *structpb.Struct {
	if w.Metadata == nil {
		return nil
	}
	
	pbStruct, err := structpb.NewStruct(w.Metadata)
	if err != nil {
		return nil
	}
	return pbStruct
}

func (w *WorkflowStep) ToProtobufStruct() *structpb.Struct {
	if w.Parameters == nil {
		return nil
	}
	
	pbStruct, err := structpb.NewStruct(w.Parameters)
	if err != nil {
		return nil
	}
	return pbStruct
}

func StructToMap(s *structpb.Struct) map[string]interface{} {
	if s == nil {
		return nil
	}
	return s.AsMap()
} 