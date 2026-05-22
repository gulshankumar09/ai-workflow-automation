"""
Workflow Domain

Core domain for workflow management, generation, execution, and versioning.
Follows Domain-Driven Design principles with clear separation of:
- Entities: Core business objects (Workflow, WorkflowStep, WorkflowVersion)
- Value Objects: Immutable business concepts (WorkflowStatus, UserIntent)
- Repositories: Data access abstractions
- Domain Services: Complex business logic coordination

Import Structure:
- WorkflowDomainService: Core domain logic in services.py
- Recovery/Versioning Services: Specialized services in specialized_services/ directory
"""

from .entities import Workflow, WorkflowStep, WorkflowVersion
from .value_objects import (
    WorkflowStatus, StepType, UserIntent, WorkflowTemplate,
    ToolCapability, WorkflowExecutionContext, WorkflowMetrics
)
from .repositories import (
    WorkflowRepository, WorkflowTemplateRepository, 
    WorkflowExecutionRepository, WorkflowVersionRepository
)
from .services import WorkflowDomainService  # Now imports from services.py file

__all__ = [
    # Entities
    "Workflow",
    "WorkflowStep",
    
    # Value Objects
    "WorkflowStatus",
    "StepType",
    "UserIntent",
    "WorkflowTemplate",
    "ToolCapability",
    "WorkflowExecutionContext",
    "WorkflowMetrics",
    
    # Repositories
    "WorkflowRepository",
    "WorkflowTemplateRepository",
    "WorkflowExecutionRepository",
    "WorkflowVersionRepository",
    
    # Domain Services
    "WorkflowDomainService",
    "WorkflowVersioningService",
] 