"""
Workflow Domain Value Objects

Immutable value objects that represent concepts in the workflow domain.
Following Domain-Driven Design principles for value objects.
"""

from builtins import ValueError
from enum import Enum, auto
from dataclasses import dataclass
from typing import Any, Dict


class WorkflowStatus(Enum):
    """Enumeration of workflow statuses"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    FAILED = "failed"


class StepType(Enum):
    """Enumeration of workflow step types"""
    TOOL_EXECUTION = "tool_execution"
    CONDITIONAL = "conditional"
    LOOP = "loop"
    PARALLEL = "parallel"
    DELAY = "delay"
    WEBHOOK = "webhook"
    TRANSFORMATION = "transformation"


class ExecutionStatus(Enum):
    """Enumeration of execution statuses"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass(frozen=True)
class WorkflowTemplate:
    """Value object representing a workflow template"""
    name: str
    description: str
    category: str
    tags: tuple
    template_steps: tuple
    
    def __post_init__(self):
        """Validate template data"""
        if not self.name or not self.name.strip():
            raise ValueError("Template name cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("Template description cannot be empty")


@dataclass(frozen=True)
class StepResult:
    """Value object representing the result of a workflow step execution"""
    step_id: str
    status: ExecutionStatus
    output_data: Dict[str, Any]
    error_message: str = ""
    execution_time_seconds: float = 0.0
    retry_count: int = 0
    
    def is_successful(self) -> bool:
        """Check if the step execution was successful"""
        return self.status == ExecutionStatus.COMPLETED
    
    def is_failed(self) -> bool:
        """Check if the step execution failed"""
        return self.status == ExecutionStatus.FAILED
    
    def is_retryable(self) -> bool:
        """Check if the step can be retried"""
        return self.status in [ExecutionStatus.FAILED, ExecutionStatus.RETRYING]


@dataclass(frozen=True)
class WorkflowMetrics:
    """Value object for workflow execution metrics"""
    total_steps: int
    completed_steps: int
    failed_steps: int
    skipped_steps: int
    total_execution_time_seconds: float
    average_step_time_seconds: float
    success_rate: float
    
    def __post_init__(self):
        """Validate metrics"""
        if self.total_steps < 0:
            raise ValueError("Total steps cannot be negative")
        if self.success_rate < 0 or self.success_rate > 1:
            raise ValueError("Success rate must be between 0 and 1")
    
    @classmethod
    def calculate_from_results(cls, step_results: list) -> 'WorkflowMetrics':
        """Calculate metrics from a list of step results"""
        if not step_results:
            return cls(0, 0, 0, 0, 0.0, 0.0, 0.0)
        
        total_steps = len(step_results)
        completed_steps = sum(1 for r in step_results if r.is_successful())
        failed_steps = sum(1 for r in step_results if r.is_failed())
        skipped_steps = total_steps - completed_steps - failed_steps
        
        total_execution_time = sum(r.execution_time_seconds for r in step_results)
        average_step_time = total_execution_time / total_steps if total_steps > 0 else 0.0
        success_rate = completed_steps / total_steps if total_steps > 0 else 0.0
        
        return cls(
            total_steps=total_steps,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            skipped_steps=skipped_steps,
            total_execution_time_seconds=total_execution_time,
            average_step_time_seconds=average_step_time,
            success_rate=success_rate
        )


@dataclass(frozen=True)
class ToolCapability:
    """Value object representing a tool's capability"""
    tool_name: str
    capability_name: str
    description: str
    parameters_schema: Dict[str, Any]
    is_available: bool = True
    
    def __post_init__(self):
        """Validate tool capability"""
        if not self.tool_name or not self.tool_name.strip():
            raise ValueError("Tool name cannot be empty")
        if not self.capability_name or not self.capability_name.strip():
            raise ValueError("Capability name cannot be empty")


@dataclass(frozen=True)
class UserIntent:
    """Value object representing parsed user intent for workflow generation"""
    raw_request: str
    entities: tuple
    action: str
    source_tool: str
    target_tool: str
    parameters: Dict[str, Any]
    confidence_score: float
    
    def __post_init__(self):
        """Validate user intent"""
        if not self.raw_request or not self.raw_request.strip():
            raise ValueError("Raw request cannot be empty")
        if self.confidence_score < 0 or self.confidence_score > 1:
            raise ValueError("Confidence score must be between 0 and 1")
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if the intent has high confidence"""
        return self.confidence_score >= threshold
    
    def involves_tool(self, tool_name: str) -> bool:
        """Check if the intent involves a specific tool"""
        return tool_name.lower() in [self.source_tool.lower(), self.target_tool.lower()]


@dataclass(frozen=True)
class WorkflowExecutionContext:
    """Value object for workflow execution context"""
    execution_id: str
    user_id: str
    workflow_id: str
    test_mode: bool
    environment: str
    execution_parameters: Dict[str, Any]
    
    def __post_init__(self):
        """Validate execution context"""
        if not self.execution_id or not self.execution_id.strip():
            raise ValueError("Execution ID cannot be empty")
        if not self.user_id or not self.user_id.strip():
            raise ValueError("User ID cannot be empty")
        if not self.workflow_id or not self.workflow_id.strip():
            raise ValueError("Workflow ID cannot be empty") 