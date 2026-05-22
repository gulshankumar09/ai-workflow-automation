"""
Workflow Domain Services

Domain services containing business logic that doesn't naturally fit
into a single entity or value object. Following Domain-Driven Design principles.
"""

from builtins import ValueError
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .entities import Workflow, WorkflowStep
from .repositories import WorkflowRepository, WorkflowTemplateRepository, WorkflowExecutionRepository
from .value_objects import (
    WorkflowStatus, StepType, UserIntent, WorkflowTemplate, 
    ToolCapability, WorkflowExecutionContext, WorkflowMetrics
)
from ..mcp.services import MCPOperationsService


class WorkflowDomainService:
    """
    Core domain service for workflow-related business logic.
    
    Handles complex business operations that involve multiple entities
    or require coordination between different domain concepts.
    """
    
    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        template_repo: WorkflowTemplateRepository,
        execution_repo: WorkflowExecutionRepository,
        mcp_service: MCPOperationsService
    ):
        self.workflow_repo = workflow_repo
        self.template_repo = template_repo
        self.execution_repo = execution_repo
        self.mcp_service = mcp_service
    
    async def create_workflow_from_intent(
        self, 
        user_id: str, 
        intent: UserIntent
    ) -> Workflow:
        """
        Create a workflow from parsed user intent.
        
        This is the core business logic for transforming natural language
        intent into an executable workflow definition.
        
        Args:
            user_id: The user creating the workflow
            intent: Parsed user intent containing entities and parameters
            
        Returns:
            A new workflow entity ready for execution
            
        Raises:
            ValueError: If intent cannot be converted to valid workflow
            MCPToolError: If required tools are not available
        """
        # Validate intent confidence
        if not intent.is_high_confidence():
            raise ValueError(f"Intent confidence too low: {intent.confidence_score}")
        
        # Discover available tools for the intent
        available_tools = await self.mcp_service.discover_tools_for_entities(list(intent.entities))
        
        if not available_tools:
            raise ValueError(f"No tools available for entities: {intent.entities}")
        
        # Generate workflow steps based on intent and available tools
        workflow_steps = await self._generate_steps_from_intent(intent, available_tools)
        
        if not workflow_steps:
            raise ValueError("Unable to generate workflow steps from intent")
        
        # Create workflow name from intent
        workflow_name = self._generate_workflow_name(intent)
        
        # Create workflow entity
        workflow = Workflow.create_new(
            user_id=user_id,
            name=workflow_name,
            steps=workflow_steps,
            description=f"Workflow generated from: '{intent.raw_request}'",
            tags=self._extract_tags_from_intent(intent)
        )
        
        # Validate workflow before saving
        if not workflow.validate_dependencies():
            raise ValueError("Generated workflow has invalid step dependencies")
        
        # Save workflow
        workflow_id = await self.workflow_repo.save(workflow)
        workflow.id = workflow_id
        
        return workflow
    
    async def _generate_steps_from_intent(
        self,
        intent: UserIntent,
        available_tools: List[ToolCapability]
    ) -> List[WorkflowStep]:
        """Generate workflow steps based on intent and available tools"""
        steps = []
        
        # Map intent to specific workflow patterns
        if intent.action.lower() in ["sync", "transfer", "copy"]:
            steps = await self._generate_sync_workflow_steps(intent, available_tools)
        elif intent.action.lower() in ["notify", "alert", "send"]:
            steps = await self._generate_notification_workflow_steps(intent, available_tools)
        elif intent.action.lower() in ["create", "generate", "build"]:
            steps = await self._generate_creation_workflow_steps(intent, available_tools)
        elif intent.action.lower() in ["monitor", "watch", "track"]:
            steps = await self._generate_monitoring_workflow_steps(intent, available_tools)
        else:
            # Generic workflow generation
            steps = await self._generate_generic_workflow_steps(intent, available_tools)
        
        return steps
    
    async def _generate_sync_workflow_steps(
        self,
        intent: UserIntent,
        available_tools: List[ToolCapability]
    ) -> List[WorkflowStep]:
        """Generate steps for sync/transfer workflows"""
        steps = []
        
        # Step 1: Get data from source
        source_tool = self._find_tool_for_action(available_tools, intent.source_tool, "get")
        if source_tool:
            step1 = WorkflowStep.create_new(
                name=f"Get data from {intent.source_tool}",
                tool_name=source_tool.tool_name,
                parameters=self._extract_source_parameters(intent),
                parallel_eligible=False
            )
            steps.append(step1)
        
            # Step 2: Transform data if needed
            if self._needs_transformation(intent):
                step2 = WorkflowStep.create_new(
                    name="Transform data",
                    tool_name="data_transformer",
                    parameters={"source_format": intent.source_tool, "target_format": intent.target_tool},
                    dependencies=[step1.id],
                    parallel_eligible=False
                )
                steps.append(step2)
                last_step_id = step2.id
            else:
                last_step_id = step1.id
            
            # Step 3: Send data to target
            target_tool = self._find_tool_for_action(available_tools, intent.target_tool, "create")
            if target_tool:
                step3 = WorkflowStep.create_new(
                    name=f"Send data to {intent.target_tool}",
                    tool_name=target_tool.tool_name,
                    parameters=self._extract_target_parameters(intent),
                    dependencies=[last_step_id],
                    parallel_eligible=False
                )
                steps.append(step3)
        
        return steps
    
    async def _generate_notification_workflow_steps(
        self,
        intent: UserIntent,
        available_tools: List[ToolCapability]
    ) -> List[WorkflowStep]:
        """Generate steps for notification workflows"""
        steps = []
        
        # Find notification tools
        notification_tools = [
            tool for tool in available_tools 
            if any(action in tool.capability_name.lower() for action in ["send", "post", "notify"])
        ]
        
        for tool in notification_tools:
            step = WorkflowStep.create_new(
                name=f"Send notification via {tool.tool_name}",
                tool_name=tool.tool_name,
                parameters=self._extract_notification_parameters(intent, tool),
                parallel_eligible=True  # Notifications can be parallel
            )
            steps.append(step)
        
        return steps
    
    async def _generate_creation_workflow_steps(
        self,
        intent: UserIntent,
        available_tools: List[ToolCapability]
    ) -> List[WorkflowStep]:
        """Generate steps for creation workflows"""
        steps = []
        
        # Find creation tools
        creation_tool = self._find_tool_for_action(available_tools, intent.target_tool, "create")
        if creation_tool:
            step = WorkflowStep.create_new(
                name=f"Create {intent.parameters.get('object_type', 'item')} in {intent.target_tool}",
                tool_name=creation_tool.tool_name,
                parameters=intent.parameters,
                parallel_eligible=False
            )
            steps.append(step)
        
        return steps
    
    async def _generate_monitoring_workflow_steps(
        self,
        intent: UserIntent,
        available_tools: List[ToolCapability]
    ) -> List[WorkflowStep]:
        """Generate steps for monitoring workflows"""
        steps = []
        
        # Step 1: Check/monitor source
        monitor_tool = self._find_tool_for_action(available_tools, intent.source_tool, "get")
        if monitor_tool:
            step1 = WorkflowStep.create_new(
                name=f"Check {intent.source_tool} for changes",
                tool_name=monitor_tool.tool_name,
                parameters=intent.parameters,
                parallel_eligible=False
            )
            steps.append(step1)
            
            # Step 2: Conditional notification if changes detected
            notification_tool = self._find_tool_for_action(available_tools, intent.target_tool, "send")
            if notification_tool:
                step2 = WorkflowStep.create_new(
                    name=f"Notify about changes",
                    tool_name=notification_tool.tool_name,
                    parameters={"message": "Changes detected", "conditional": True},
                    dependencies=[step1.id],
                    parallel_eligible=False,
                    step_type=StepType.CONDITIONAL
                )
                steps.append(step2)
        
        return steps
    
    async def _generate_generic_workflow_steps(
        self,
        intent: UserIntent,
        available_tools: List[ToolCapability]
    ) -> List[WorkflowStep]:
        """Generate generic workflow steps when specific patterns don't match"""
        steps = []
        
        # Simple sequential execution of available tools
        for i, tool in enumerate(available_tools[:3]):  # Limit to 3 steps for generic workflows
            dependencies = [steps[-1].id] if steps else []
            
            step = WorkflowStep.create_new(
                name=f"Execute {tool.tool_name}",
                tool_name=tool.tool_name,
                parameters=intent.parameters,
                dependencies=dependencies,
                parallel_eligible=False
            )
            steps.append(step)
        
        return steps
    
    def _find_tool_for_action(
        self,
        tools: List[ToolCapability],
        tool_name: str,
        action: str
    ) -> Optional[ToolCapability]:
        """Find a tool that matches the name and supports the action"""
        for tool in tools:
            if (tool_name.lower() in tool.tool_name.lower() and 
                action.lower() in tool.capability_name.lower()):
                return tool
        return None
    
    def _extract_source_parameters(self, intent: UserIntent) -> Dict[str, Any]:
        """Extract parameters for source tool from intent"""
        params = intent.parameters.copy()
        
        # Add common source parameters
        if 'channel' in params or 'channel_name' in params:
            params['channel_id'] = params.get('channel', params.get('channel_name'))
        
        if 'limit' not in params:
            params['limit'] = 50  # Default limit
            
        return params
    
    def _extract_target_parameters(self, intent: UserIntent) -> Dict[str, Any]:
        """Extract parameters for target tool from intent"""
        params = intent.parameters.copy()
        
        # Add common target parameters
        if 'title' not in params and 'name' not in params:
            params['title'] = f"Data from {intent.source_tool}"
        
        return params
    
    def _extract_notification_parameters(
        self,
        intent: UserIntent,
        tool: ToolCapability
    ) -> Dict[str, Any]:
        """Extract parameters for notification tools"""
        params = intent.parameters.copy()
        
        if 'message' not in params:
            params['message'] = f"Workflow notification: {intent.raw_request}"
        
        return params
    
    def _needs_transformation(self, intent: UserIntent) -> bool:
        """Check if data transformation is needed between source and target"""
        # Simple heuristic - different tool types likely need transformation
        source_type = intent.source_tool.lower()
        target_type = intent.target_tool.lower()
        
        incompatible_pairs = [
            ('slack', 'notion'),
            ('github', 'slack'),
            ('notion', 'github')
        ]
        
        return (source_type, target_type) in incompatible_pairs
    
    def _generate_workflow_name(self, intent: UserIntent) -> str:
        """Generate a human-readable workflow name from intent"""
        action = intent.action.title()
        source = intent.source_tool.title()
        target = intent.target_tool.title()
        
        return f"{action} {source} to {target}"
    
    def _extract_tags_from_intent(self, intent: UserIntent) -> List[str]:
        """Extract relevant tags from intent for workflow categorization"""
        tags = []
        
        # Add action as tag
        tags.append(intent.action.lower())
        
        # Add involved tools as tags
        tags.extend([intent.source_tool.lower(), intent.target_tool.lower()])
        
        # Add entity types as tags
        for entity in intent.entities:
            if isinstance(entity, str) and len(entity) > 2:
                tags.append(entity.lower())
        
        return list(set(tags))  # Remove duplicates
    
    async def optimize_workflow_execution_order(self, workflow: Workflow) -> Workflow:
        """
        Optimize the execution order of workflow steps for better performance.
        
        Args:
            workflow: The workflow to optimize
            
        Returns:
            Optimized workflow with updated step dependencies
        """
        if not workflow.steps:
            return workflow
        
        # Identify parallelizable steps
        parallel_groups = self._identify_parallel_groups(workflow.steps)
        
        # Optimize dependencies to maximize parallelism
        optimized_steps = self._optimize_step_dependencies(workflow.steps, parallel_groups)
        
        # Create new workflow with optimized steps
        optimized_workflow = Workflow(
            id=workflow.id,
            user_id=workflow.user_id,
            name=workflow.name,
            description=workflow.description,
            steps=optimized_steps,
            status=workflow.status,
            created_at=workflow.created_at,
            updated_at=datetime.utcnow(),
            tags=workflow.tags,
            metadata=workflow.metadata,
            estimated_duration_seconds=Workflow._calculate_estimated_duration(optimized_steps)
        )
        
        return optimized_workflow
    
    def _identify_parallel_groups(self, steps: List[WorkflowStep]) -> List[List[str]]:
        """Identify groups of steps that can be executed in parallel"""
        parallel_groups = []
        
        # Group steps by their dependencies
        dependency_groups = {}
        for step in steps:
            dep_key = tuple(sorted(step.dependencies))
            if dep_key not in dependency_groups:
                dependency_groups[dep_key] = []
            dependency_groups[dep_key].append(step.id)
        
        # Convert to parallel groups
        for group in dependency_groups.values():
            if len(group) > 1:
                parallel_groups.append(group)
        
        return parallel_groups
    
    def _optimize_step_dependencies(
        self,
        steps: List[WorkflowStep],
        parallel_groups: List[List[str]]
    ) -> List[WorkflowStep]:
        """Optimize step dependencies for maximum parallelism"""
        optimized_steps = []
        
        for step in steps:
            # Mark steps as parallel eligible if they're in a parallel group
            parallel_eligible = any(step.id in group for group in parallel_groups)
            
            optimized_step = WorkflowStep(
                id=step.id,
                name=step.name,
                tool_name=step.tool_name,
                parameters=step.parameters,
                dependencies=step.dependencies,
                parallel_eligible=parallel_eligible,
                retry_count=step.retry_count,
                max_retries=step.max_retries,
                step_type=step.step_type,
                timeout_seconds=step.timeout_seconds
            )
            
            optimized_steps.append(optimized_step)
        
        return optimized_steps
    
    async def get_workflow_recommendations(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get workflow recommendations for a user based on their history and patterns.
        
        Args:
            user_id: The user to get recommendations for
            limit: Maximum number of recommendations
            
        Returns:
            List of workflow recommendations
        """
        # Get user's workflow history
        user_workflows = await self.workflow_repo.find_by_user_id(user_id, limit=50)
        
        if not user_workflows:
            # Return popular templates for new users
            return await self._get_popular_templates(limit)
        
        # Analyze user patterns
        patterns = self._analyze_user_patterns(user_workflows)
        
        # Generate recommendations based on patterns
        recommendations = await self._generate_recommendations_from_patterns(patterns, limit)
        
        return recommendations
    
    def _analyze_user_patterns(self, workflows: List[Workflow]) -> Dict[str, Any]:
        """Analyze user workflow patterns"""
        patterns = {
            "most_used_tools": {},
            "common_actions": {},
            "preferred_tags": {},
            "average_complexity": 0
        }
        
        total_steps = 0
        for workflow in workflows:
            # Count tool usage
            for step in workflow.steps:
                tool_name = step.tool_name
                patterns["most_used_tools"][tool_name] = patterns["most_used_tools"].get(tool_name, 0) + 1
            
            # Count workflow complexity
            total_steps += len(workflow.steps)
            
            # Count tags
            for tag in workflow.tags:
                patterns["preferred_tags"][tag] = patterns["preferred_tags"].get(tag, 0) + 1
        
        patterns["average_complexity"] = total_steps / len(workflows) if workflows else 0
        
        return patterns
    
    async def _generate_recommendations_from_patterns(
        self,
        patterns: Dict[str, Any],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on user patterns"""
        recommendations = []
        
        # Get templates that match user's preferred tags
        preferred_tags = list(patterns["preferred_tags"].keys())[:3]
        matching_templates = await self.template_repo.find_templates_by_tags(preferred_tags)
        
        for template in matching_templates[:limit]:
            recommendations.append({
                "type": "template",
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "match_reason": f"Matches your interests in {', '.join(preferred_tags)}"
            })
        
        return recommendations
    
    async def _get_popular_templates(self, limit: int) -> List[Dict[str, Any]]:
        """Get popular workflow templates for new users"""
        templates = await self.template_repo.get_all_templates(limit=limit)
        
        return [
            {
                "type": "template",
                "name": template.name,
                "description": template.description,
                "category": template.category,
                "match_reason": "Popular template"
            }
            for template in templates
        ] 