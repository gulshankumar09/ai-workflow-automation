"""
Workflow Domain Entities

Core business entities for workflow management following Domain-Driven Design principles.
"""

from builtins import ValueError
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TypedDict, Annotated
from datetime import datetime
import uuid
from enum import Enum
import operator

from .value_objects import WorkflowStatus, StepType

@dataclass
class WorkflowStep:
    """
    Represents a single step in a workflow execution plan.
    
    This is a core entity that encapsulates all information needed
    to execute a specific tool with its parameters and dependencies.
    """
    id: str
    name: str
    tool_name: str
    parameters: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    parallel_eligible: bool = False
    retry_count: int = 0
    max_retries: int = 3
    step_type: StepType = StepType.TOOL_EXECUTION
    timeout_seconds: int = 30
    
    @classmethod
    def create_new(
        cls,
        name: str,
        tool_name: str,
        parameters: Dict[str, Any],
        dependencies: List[str] = None,
        parallel_eligible: bool = False,
        max_retries: int = 3
    ) -> 'WorkflowStep':
        """Create a new workflow step with generated ID"""
        return cls(
            id=f"step_{uuid.uuid4().hex[:8]}",
            name=name,
            tool_name=tool_name,
            parameters=parameters,
            dependencies=dependencies or [],
            parallel_eligible=parallel_eligible,
            max_retries=max_retries
        )
    
    def can_execute_after(self, completed_steps: List[str]) -> bool:
        """Check if this step can execute given completed steps"""
        return all(dep in completed_steps for dep in self.dependencies)
    
    def increment_retry(self) -> bool:
        """Increment retry count and return if more retries are allowed"""
        self.retry_count += 1
        return self.retry_count <= self.max_retries
    
    def reset_retries(self) -> None:
        """Reset retry count to 0"""
        self.retry_count = 0


@dataclass
class WorkflowVersion:
    """Represents a specific version of a workflow"""
    id: str
    workflow_id: str
    version_number: int
    name: str
    description: Optional[str]
    definition: Dict[str, Any]
    created_by: str
    created_at: datetime
    is_active: bool = False
    change_notes: Optional[str] = None
    parent_version_id: Optional[str] = None

    @classmethod
    def create_new(
        cls,
        workflow_id: str,
        version_number: int,
        name: str,
        definition: Dict[str, Any],
        created_by: str,
        change_notes: Optional[str] = None,
        parent_version_id: Optional[str] = None
    ) -> 'WorkflowVersion':
        return cls(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            version_number=version_number,
            name=name,
            description=None,
            definition=definition,
            created_by=created_by,
            created_at=datetime.utcnow(),
            is_active=False,
            change_notes=change_notes,
            parent_version_id=parent_version_id
        )

    def activate(self) -> None:
        """Mark this version as the active version"""
        self.is_active = True

    def deactivate(self) -> None:
        """Mark this version as inactive"""
        self.is_active = False


@dataclass 
class Workflow:
    """
    Core workflow entity representing a complete automation workflow.
    
    Aggregates workflow steps and provides domain logic for workflow
    lifecycle management, validation, and execution coordination.
    """
    id: str
    user_id: str
    name: str
    description: Optional[str]
    current_version_id: Optional[str]
    status: str  # draft, active, archived
    created_at: datetime
    updated_at: datetime
    total_versions: int = 1
    steps: List[WorkflowStep] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    estimated_duration_seconds: Optional[int] = None
    
    @classmethod
    def create_new(
        cls,
        user_id: str,
        name: str,
        steps: List[WorkflowStep],
        description: Optional[str] = None,
        tags: List[str] = None
    ) -> 'Workflow':
        """Create a new workflow with generated ID and default values"""
        now = datetime.utcnow()
        
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            current_version_id=None,
            status="draft",
            created_at=now,
            updated_at=now,
            total_versions=1,
            steps=steps,
            tags=tags or [],
            estimated_duration_seconds=cls._calculate_estimated_duration(steps)
        )
    
    @staticmethod
    def _calculate_estimated_duration(steps: List[WorkflowStep]) -> int:
        """Calculate estimated workflow duration based on steps"""
        total_duration = 0
        parallel_groups = []
        sequential_steps = []
        
        # Group parallel and sequential steps
        for step in steps:
            if step.parallel_eligible:
                parallel_groups.append(step.timeout_seconds)
            else:
                sequential_steps.append(step.timeout_seconds)
        
        # Add sequential step durations
        total_duration += sum(sequential_steps)
        
        # Add maximum parallel group duration
        if parallel_groups:
            total_duration += max(parallel_groups)
            
        return total_duration
    
    def activate(self) -> None:
        """Activate the workflow for execution"""
        if self.status != "draft":
            raise ValueError(f"Cannot activate workflow in {self.status} status")
        
        self.status = "active"
        self.updated_at = datetime.utcnow()
    
    def archive(self) -> None:
        """Archive the workflow"""
        self.status = "archived"
        self.updated_at = datetime.utcnow()
    
    def pause(self) -> None:
        """Pause an active workflow"""
        if self.status != "active":
            raise ValueError(f"Cannot pause workflow in {self.status} status")
        
        self.status = "paused"
        self.updated_at = datetime.utcnow()
    
    def resume(self) -> None:
        """Resume a paused workflow"""
        if self.status != "paused":
            raise ValueError(f"Cannot resume workflow in {self.status} status")
        
        self.status = "active"
        self.updated_at = datetime.utcnow()
    
    def add_step(self, step: WorkflowStep) -> None:
        """Add a new step to the workflow"""
        if self.status == "archived":
            raise ValueError("Cannot modify archived workflow")
        
        self.steps.append(step)
        self.updated_at = datetime.utcnow()
        self.estimated_duration_seconds = self._calculate_estimated_duration(self.steps)
    
    def remove_step(self, step_id: str) -> bool:
        """Remove a step from the workflow by ID"""
        if self.status == "archived":
            raise ValueError("Cannot modify archived workflow")
        
        original_count = len(self.steps)
        self.steps = [step for step in self.steps if step.id != step_id]
        
        if len(self.steps) < original_count:
            self.updated_at = datetime.utcnow()
            self.estimated_duration_seconds = self._calculate_estimated_duration(self.steps)
            return True
        
        return False
    
    def get_step_by_id(self, step_id: str) -> Optional[WorkflowStep]:
        """Get a step by its ID"""
        return next((step for step in self.steps if step.id == step_id), None)
    
    def validate_dependencies(self) -> bool:
        """Validate that all step dependencies are valid"""
        step_ids = {step.id for step in self.steps}
        
        for step in self.steps:
            for dep_id in step.dependencies:
                if dep_id not in step_ids:
                    return False
        
        return True
    
    def get_executable_steps(self, completed_steps: List[str]) -> List[WorkflowStep]:
        """Get steps that can be executed given completed steps"""
        return [
            step for step in self.steps
            if step.can_execute_after(completed_steps) and step.id not in completed_steps
        ]
    
    def get_parallel_executable_steps(self, completed_steps: List[str]) -> List[WorkflowStep]:
        """Get steps that can be executed in parallel"""
        executable_steps = self.get_executable_steps(completed_steps)
        return [step for step in executable_steps if step.parallel_eligible]
    
    def update_metadata(self, key: str, value: Any) -> None:
        """Update workflow metadata"""
        self.metadata[key] = value
        self.updated_at = datetime.utcnow()
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the workflow"""
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.utcnow()
    
    def remove_tag(self, tag: str) -> bool:
        """Remove a tag from the workflow"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow to dictionary representation"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "steps": [
                {
                    "id": step.id,
                    "name": step.name,
                    "tool_name": step.tool_name,
                    "parameters": step.parameters,
                    "dependencies": step.dependencies,
                    "parallel_eligible": step.parallel_eligible,
                    "max_retries": step.max_retries,
                    "step_type": step.step_type.value,
                    "timeout_seconds": step.timeout_seconds
                }
                for step in self.steps
            ],
            "tags": self.tags,
            "metadata": self.metadata,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    def update_current_version(self, version_id: str) -> None:
        """Update the current active version"""
        self.current_version_id = version_id
        self.updated_at = datetime.utcnow()

    def increment_version_count(self) -> None:
        """Increment the total version count"""
        self.total_versions += 1
        self.updated_at = datetime.utcnow()


@dataclass
class WorkflowExecution:
    """
    Represents a single execution instance of a workflow.
    
    This entity tracks the runtime state, progress, and results
    of a workflow execution from start to completion.
    """
    id: str
    workflow_id: str
    user_id: str
    status: str  # pending, running, completed, failed, cancelled
    started_at: datetime
    completed_at: Optional[datetime] = None
    progress: float = 0.0  # 0.0 to 1.0
    current_step_id: Optional[str] = None
    execution_context: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    output_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create_new(
        cls,
        workflow_id: str,
        user_id: str,
        execution_context: Dict[str, Any] = None
    ) -> 'WorkflowExecution':
        """Create a new workflow execution"""
        return cls(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            user_id=user_id,
            status="pending",
            started_at=datetime.utcnow(),
            execution_context=execution_context or {}
        )
    
    def start(self) -> None:
        """Mark execution as started"""
        if self.status != "pending":
            raise ValueError(f"Cannot start execution in {self.status} status")
        
        self.status = "running"
        self.started_at = datetime.utcnow()
    
    def complete(self, output_data: Dict[str, Any] = None) -> None:
        """Mark execution as completed"""
        if self.status != "running":
            raise ValueError(f"Cannot complete execution in {self.status} status")
        
        self.status = "completed"
        self.completed_at = datetime.utcnow()
        self.progress = 1.0
        if output_data:
            self.output_data = output_data
    
    def fail(self, error_message: str) -> None:
        """Mark execution as failed"""
        if self.status in ["completed", "cancelled"]:
            raise ValueError(f"Cannot fail execution in {self.status} status")
        
        self.status = "failed"
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
    
    def cancel(self) -> None:
        """Cancel the execution"""
        if self.status in ["completed", "failed"]:
            raise ValueError(f"Cannot cancel execution in {self.status} status")
        
        self.status = "cancelled"
        self.completed_at = datetime.utcnow()
    
    def update_progress(self, progress: float, current_step_id: str = None) -> None:
        """Update execution progress"""
        if not 0.0 <= progress <= 1.0:
            raise ValueError("Progress must be between 0.0 and 1.0")
        
        self.progress = progress
        if current_step_id:
            self.current_step_id = current_step_id
    
    def add_step_result(self, step_id: str, result: Dict[str, Any]) -> None:
        """Add result for a completed step"""
        self.step_results[step_id] = result
    
    def get_step_result(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Get result for a specific step"""
        return self.step_results.get(step_id)
    
    def update_context(self, key: str, value: Any) -> None:
        """Update execution context"""
        self.execution_context[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert execution to dictionary representation"""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "current_step_id": self.current_step_id,
            "execution_context": self.execution_context,
            "step_results": self.step_results,
            "error_message": self.error_message,
            "output_data": self.output_data,
            "metadata": self.metadata
        } 