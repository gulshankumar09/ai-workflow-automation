"""
Workflow Domain Repositories

Repository interfaces following the Repository pattern for data access abstraction.
These interfaces define the contract for workflow data persistence.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from .entities import Workflow, WorkflowStep, WorkflowExecution, WorkflowVersion
from .value_objects import WorkflowStatus, WorkflowTemplate, WorkflowMetrics


class WorkflowRepository(ABC):
    """Abstract repository interface for workflow persistence"""

    @abstractmethod
    async def save(self, workflow: Workflow) -> str:
        """
        Save a workflow and return its ID
        
        Args:
            workflow: The workflow entity to save
            
        Returns:
            The workflow ID
            
        Raises:
            RepositoryError: If save operation fails
        """
        pass

    @abstractmethod
    async def find_by_id(self, workflow_id: str) -> Optional[Workflow]:
        """
        Find a workflow by its ID
        
        Args:
            workflow_id: The workflow ID to search for
            
        Returns:
            The workflow entity if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_by_user_id(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Workflow]:
        """
        Find workflows by user ID with pagination
        
        Args:
            user_id: The user ID to search for
            limit: Maximum number of workflows to return
            offset: Number of workflows to skip
            
        Returns:
            List of workflow entities
        """
        pass

    @abstractmethod
    async def find_by_status(self, status: WorkflowStatus, limit: int = 100, offset: int = 0) -> List[Workflow]:
        """
        Find workflows by status
        
        Args:
            status: The workflow status to filter by
            limit: Maximum number of workflows to return
            offset: Number of workflows to skip
            
        Returns:
            List of workflow entities
        """
        pass

    @abstractmethod
    async def find_by_tags(self, tags: List[str], user_id: Optional[str] = None) -> List[Workflow]:
        """
        Find workflows by tags
        
        Args:
            tags: List of tags to search for
            user_id: Optional user ID to filter by
            
        Returns:
            List of workflow entities
        """
        pass

    @abstractmethod
    async def update(self, workflow: Workflow) -> bool:
        """
        Update an existing workflow
        
        Args:
            workflow: The workflow entity to update
            
        Returns:
            True if update was successful, False otherwise
        """
        pass

    @abstractmethod
    async def delete(self, workflow_id: str) -> bool:
        """
        Delete a workflow by ID
        
        Args:
            workflow_id: The workflow ID to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        pass

    @abstractmethod
    async def exists(self, workflow_id: str) -> bool:
        """
        Check if a workflow exists
        
        Args:
            workflow_id: The workflow ID to check
            
        Returns:
            True if workflow exists, False otherwise
        """
        pass

    @abstractmethod
    async def count_by_user(self, user_id: str) -> int:
        """
        Count workflows for a specific user
        
        Args:
            user_id: The user ID to count workflows for
            
        Returns:
            Number of workflows for the user
        """
        pass

    @abstractmethod
    async def find_recent_by_user(self, user_id: str, days: int = 30, limit: int = 10) -> List[Workflow]:
        """
        Find recent workflows by user
        
        Args:
            user_id: The user ID to search for
            days: Number of days to look back
            limit: Maximum number of workflows to return
            
        Returns:
            List of recent workflow entities
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Workflow]:
        """
        Search workflows by query with optional filters
        
        Args:
            query: Search query string
            user_id: Optional user ID filter
            status: Optional status filter
            tags: Optional tags filter
            limit: Maximum number of results
            
        Returns:
            List of matching workflow entities
        """
        pass


class WorkflowTemplateRepository(ABC):
    """Abstract repository interface for workflow template persistence"""

    @abstractmethod
    async def save_template(self, template: WorkflowTemplate) -> str:
        """
        Save a workflow template
        
        Args:
            template: The workflow template to save
            
        Returns:
            The template ID
        """
        pass

    @abstractmethod
    async def find_template_by_id(self, template_id: str) -> Optional[WorkflowTemplate]:
        """
        Find a template by ID
        
        Args:
            template_id: The template ID to search for
            
        Returns:
            The template if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_templates_by_category(self, category: str) -> List[WorkflowTemplate]:
        """
        Find templates by category
        
        Args:
            category: The category to filter by
            
        Returns:
            List of templates in the category
        """
        pass

    @abstractmethod
    async def find_templates_by_tags(self, tags: List[str]) -> List[WorkflowTemplate]:
        """
        Find templates by tags
        
        Args:
            tags: List of tags to search for
            
        Returns:
            List of matching templates
        """
        pass

    @abstractmethod
    async def get_all_templates(self, limit: int = 100, offset: int = 0) -> List[WorkflowTemplate]:
        """
        Get all templates with pagination
        
        Args:
            limit: Maximum number of templates to return
            offset: Number of templates to skip
            
        Returns:
            List of workflow templates
        """
        pass

    @abstractmethod
    async def delete_template(self, template_id: str) -> bool:
        """
        Delete a template by ID
        
        Args:
            template_id: The template ID to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        pass


class WorkflowExecutionRepository(ABC):
    """Abstract repository interface for workflow execution tracking"""

    @abstractmethod
    async def save_execution(self, execution_data: Dict[str, Any]) -> str:
        """
        Save workflow execution data
        
        Args:
            execution_data: The execution data to save
            
        Returns:
            The execution ID
        """
        pass

    @abstractmethod
    async def find_execution_by_id(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Find execution by ID
        
        Args:
            execution_id: The execution ID to search for
            
        Returns:
            The execution data if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_executions_by_workflow(
        self,
        workflow_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Find executions by workflow ID
        
        Args:
            workflow_id: The workflow ID to search for
            limit: Maximum number of executions to return
            offset: Number of executions to skip
            
        Returns:
            List of execution data
        """
        pass

    @abstractmethod
    async def find_executions_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Find executions by user ID
        
        Args:
            user_id: The user ID to search for
            limit: Maximum number of executions to return
            offset: Number of executions to skip
            
        Returns:
            List of execution data
        """
        pass

    @abstractmethod
    async def update_execution_status(self, execution_id: str, status: str, output_data: Dict[str, Any] = None) -> bool:
        """
        Update execution status and output data
        
        Args:
            execution_id: The execution ID to update
            status: The new status
            output_data: Optional output data
            
        Returns:
            True if update was successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_execution_metrics(self, workflow_id: str, days: int = 30) -> WorkflowMetrics:
        """
        Get execution metrics for a workflow
        
        Args:
            workflow_id: The workflow ID to get metrics for
            days: Number of days to analyze
            
        Returns:
            Workflow metrics value object
        """
        pass

    @abstractmethod
    async def get_user_execution_statistics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get execution statistics for a user
        
        Args:
            user_id: The user ID to get statistics for
            days: Number of days to analyze
            
        Returns:
            Dictionary containing user execution statistics
        """
        pass


class WorkflowVersionRepository(ABC):
    """Repository interface for workflow versions"""

    @abstractmethod
    async def save_version(self, version: WorkflowVersion) -> str:
        """Save a workflow version and return its ID"""
        pass

    @abstractmethod
    async def get_version_by_id(self, version_id: str) -> Optional[WorkflowVersion]:
        """Get a workflow version by ID"""
        pass

    @abstractmethod
    async def get_versions_by_workflow_id(self, workflow_id: str) -> List[WorkflowVersion]:
        """Get all versions for a specific workflow"""
        pass

    @abstractmethod
    async def get_active_version(self, workflow_id: str) -> Optional[WorkflowVersion]:
        """Get the currently active version of a workflow"""
        pass

    @abstractmethod
    async def get_latest_version(self, workflow_id: str) -> Optional[WorkflowVersion]:
        """Get the latest version of a workflow (highest version number)"""
        pass

    @abstractmethod
    async def activate_version(self, workflow_id: str, version_id: str) -> bool:
        """Activate a specific version and deactivate others"""
        pass

    @abstractmethod
    async def delete_version(self, version_id: str) -> bool:
        """Delete a workflow version"""
        pass

    @abstractmethod
    async def get_version_history(
        self, 
        workflow_id: str, 
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[WorkflowVersion]:
        """Get version history with pagination"""
        pass

    @abstractmethod
    async def compare_versions(
        self, 
        version_1_id: str, 
        version_2_id: str
    ) -> Dict[str, Any]:
        """Compare two workflow versions and return differences"""
        pass


class RepositoryError(Exception):
    """Exception raised for repository operation errors"""
    
    def __init__(self, message: str, operation: str = "", entity_id: str = ""):
        super().__init__(message)
        self.operation = operation
        self.entity_id = entity_id
        
    def __str__(self):
        parts = [super().__str__()]
        if self.operation:
            parts.append(f"Operation: {self.operation}")
        if self.entity_id:
            parts.append(f"Entity ID: {self.entity_id}")
        return " | ".join(parts) 