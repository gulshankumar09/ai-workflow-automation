"""
Workflow Service - Core Application Service for Workflow Generation and Management

This service implements the main workflow generation logic using LangGraph and manages
workflow lifecycle operations. It handles intent parsing, tool discovery, and 
workflow generation from natural language requests.

Key Features:
- Natural language workflow generation using LangGraph
- Tool discovery and validation
- Workflow template management
- Workflow state management
- Integration with MCP tools
"""

import time
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from app.shared.exceptions import (
    WorkflowGenerationError,
    ValidationException,
    NotFoundException,
    ExternalServiceException
)
from app.shared.config import get_settings
from app.infrastructure.database.providers.factory import DatabaseProviderFactory
from app.infrastructure.cache.factory import CacheProviderFactory
from app.ai.llm import get_llm
from app.shared.dependency_injection import get_dependency_container


# class WorkflowGenerationState(BaseModel):
#     """State model for LangGraph workflow generation process"""
#     user_request: str
#     user_id: str
#     correlation_id: str
#     parsed_intent: Dict[str, Any] = Field(default_factory=dict)
#     available_tools: List[Dict[str, Any]] = Field(default_factory=list)
#     workflow_steps: List[Dict[str, Any]] = Field(default_factory=list)
#     current_context: Dict[str, Any] = Field(default_factory=dict)
#     errors: List[str] = Field(default_factory=list)
#     final_workflow: Dict[str, Any] = Field(default_factory=dict)
#     status: str = "initializing"


class WorkflowDefinition(BaseModel):
    """Workflow definition model"""
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    steps: List[Dict[str, Any]]
    status: str = "draft"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class WorkflowService:
    """
    Core service for workflow generation and management
    
    This service orchestrates the workflow generation process using LangGraph
    and provides lifecycle management for workflows.
    """
    
    def __init__(
        self,
        database_provider_factory: Optional[DatabaseProviderFactory] = None,
        cache_provider_factory: Optional[CacheProviderFactory] = None,
        correlation_id: Optional[str] = None,
        dependency_container = None
    ):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.settings = get_settings()
        
        # Use dependency injection container if provided, otherwise use factories
        if dependency_container:
            self.dependency_container = dependency_container
            self.database = dependency_container.create_database_provider()
            self.cache = dependency_container.create_cache_provider()
            self.llm = get_llm()
        else:
            # Fallback to manual factory creation
            self.database_factory = database_provider_factory or DatabaseProviderFactory()
            self.cache_factory = cache_provider_factory or CacheProviderFactory()
            
            # Create providers using dependency injection
            container = get_dependency_container(self.correlation_id)
            self.database = container.create_database_provider()
            self.cache = container.create_cache_provider()
            self.llm = get_llm()
        
        # Build LangGraph for workflow generation
        # self.generation_graph = self._build_generation_graph()
    
    # def _build_generation_graph(self) -> CompiledStateGraph:
    #     """Build LangGraph state machine for workflow generation"""
        
    #     graph = StateGraph(WorkflowGenerationState)
        
    #     # Add nodes for each step of workflow generation
    #     graph.add_node("parse_intent", self._parse_intent_node)
    #     graph.add_node("discover_tools", self._discover_tools_node)
    #     graph.add_node("validate_tools", self._validate_tools_node)
    #     graph.add_node("generate_steps", self._generate_steps_node)
    #     graph.add_node("optimize_workflow", self._optimize_workflow_node)
    #     graph.add_node("finalize_workflow", self._finalize_workflow_node)
    #     graph.add_node("handle_error", self._handle_error_node)
        
    #     # Set entry point
    #     graph.set_entry_point("parse_intent")
        
    #     # Add edges with conditional logic
    #     graph.add_edge("parse_intent", "discover_tools")
        
    #     graph.add_conditional_edges(
    #         "discover_tools",
    #         self._check_tools_available,
    #         {
    #             "valid": "validate_tools",
    #             "invalid": "handle_error",
    #             "retry": "discover_tools"  # Allow retries
    #         }
    #     )
        
    #     graph.add_edge("validate_tools", "generate_steps")
    #     graph.add_edge("generate_steps", "optimize_workflow")
    #     graph.add_edge("optimize_workflow", "finalize_workflow")
    #     graph.add_edge("finalize_workflow", END)
    #     graph.add_edge("handle_error", END)
        
    #     return graph.compile()
    
    # async def _parse_intent_node(self, state: WorkflowGenerationState) -> Dict[str, Any]:
    #     """Parse user intent using LLM and extract entities"""
    #     try:
    #         # Get user context for better parsing
    #         user_context = await self._get_user_context(state.user_id)
            
    #         # Build prompt for intent parsing
    #         parsing_prompt = self._build_intent_parsing_prompt(
    #             state.user_request, 
    #             user_context
    #         )
            
    #         # Use LLM to parse intent
    #         intent_response = await self.llm.ainvoke(parsing_prompt)
            
    #         # Parse LLM response into structured intent
    #         parsed_intent = self._parse_llm_intent_response(intent_response.content)
            
    #         return {
    #             "parsed_intent": parsed_intent,
    #             "status": "intent_parsed"
    #         }
            
    #     except Exception as e:
    #         return {
    #             "errors": [f"Intent parsing failed: {str(e)}"],
    #             "status": "error"
    #         }
    
    # async def _discover_tools_node(self, state: WorkflowGenerationState) -> Dict[str, Any]:
    #     """Discover available MCP tools based on parsed intent"""
    #     try:
    #         intent = state.parsed_intent
    #         entities = intent.get("entities", [])
            
    #         # Check cache first
    #         cache_key = f"tools_discovery:{':'.join(sorted(entities))}"
    #         cached_tools = await self.cache.get(cache_key)
            
    #         if cached_tools:
    #             return {
    #                 "available_tools": cached_tools,
    #                 "status": "tools_discovered"
    #             }
            
    #         # Query database for available tools matching entities
    #         tools_query = {
    #             "table": "mcp_tools",
    #             "filters": {
    #                 "is_available": True,
    #                 "server_name__in": [entity.lower() for entity in entities]
    #             }
    #         }
            
    #         tools_result = await self.database.select(**tools_query)
    #         available_tools = tools_result.get("data", [])
            
    #         # Cache results for future use
    #         await self.cache.set(cache_key, available_tools, ttl=300)  # 5 minutes
            
    #         return {
    #             "available_tools": available_tools,
    #             "status": "tools_discovered"
    #         }
            
    #     except Exception as e:
    #         return {
    #             "errors": [f"Tool discovery failed: {str(e)}"],
    #             "status": "error"
    #         }
    
    # async def _validate_tools_node(self, state: WorkflowGenerationState) -> Dict[str, Any]:
    #     """Validate that discovered tools can fulfill the workflow requirements"""
    #     try:
    #         intent = state.parsed_intent
    #         available_tools = state.available_tools
            
    #         # Check if we have tools for source and target systems
    #         source_tools = [
    #             tool for tool in available_tools
    #             if intent.get("source", "").lower() in tool.get("name", "").lower()
    #         ]
            
    #         target_tools = [
    #             tool for tool in available_tools  
    #             if intent.get("target", "").lower() in tool.get("name", "").lower()
    #         ]
            
    #         if not source_tools and intent.get("source"):
    #             return {
    #                 "errors": [f"No tools available for source system: {intent.get('source')}"],
    #                 "status": "error"
    #             }
            
    #         if not target_tools and intent.get("target"):
    #             return {
    #                 "errors": [f"No tools available for target system: {intent.get('target')}"],
    #                 "status": "error"
    #             }
            
    #         return {
    #             "status": "tools_validated",
    #             "current_context": {
    #                 "source_tools": source_tools,
    #                 "target_tools": target_tools
    #             }
    #         }
            
    #     except Exception as e:
    #         return {
    #             "errors": [f"Tool validation failed: {str(e)}"],
    #             "status": "error"
    #         }
    
    # async def _generate_steps_node(self, state: WorkflowGenerationState) -> Dict[str, Any]:
    #     """Generate workflow steps using LangGraph logic"""
    #     try:
    #         intent = state.parsed_intent
    #         context = state.current_context
    #         available_tools = state.available_tools
            
    #         steps = []
    #         step_counter = 1
            
    #         # Generate steps based on intent pattern
    #         action = intent.get("action", "").lower()
            
    #         if action == "sync":
    #             # Create sync workflow steps
    #             steps = await self._generate_sync_workflow_steps(
    #                 intent, context, available_tools, step_counter
    #             )
    #         elif action == "notify":
    #             # Create notification workflow steps
    #             steps = await self._generate_notification_workflow_steps(
    #                 intent, context, available_tools, step_counter
    #             )
    #         else:
    #             # Generic workflow steps
    #             steps = await self._generate_generic_workflow_steps(
    #                 intent, context, available_tools, step_counter
    #             )
            
    #         return {
    #             "workflow_steps": steps,
    #             "status": "steps_generated"
    #         }
            
    #     except Exception as e:
    #         return {
    #             "errors": [f"Step generation failed: {str(e)}"],
    #             "status": "error"
    #         }
    
    # async def _optimize_workflow_node(self, state: WorkflowGenerationState) -> Dict[str, Any]:
    #     """Optimize workflow for parallel execution and efficiency"""
    #     try:
    #         steps = state.workflow_steps
            
    #         # Analyze dependencies and mark parallel-eligible steps
    #         optimized_steps = []
            
    #         for step in steps:
    #             # Check if step can run in parallel
    #             step["parallel_eligible"] = self._can_run_in_parallel(step, optimized_steps)
                
    #             # Add retry configuration
    #             step["max_retries"] = 3
    #             step["retry_delay"] = 2
                
    #             optimized_steps.append(step)
            
    #         return {
    #             "workflow_steps": optimized_steps,
    #             "status": "workflow_optimized"
    #         }
            
    #     except Exception as e:
    #         return {
    #             "errors": [f"Workflow optimization failed: {str(e)}"],
    #             "status": "error"
    #         }
    
    # async def _finalize_workflow_node(self, state: WorkflowGenerationState) -> Dict[str, Any]:
    #     """Finalize workflow definition and prepare for storage"""
    #     try:
    #         workflow_definition = {
    #             "id": str(uuid.uuid4()),
    #             "user_id": state.user_id,
    #             "name": self._generate_workflow_name(state.parsed_intent),
    #             "description": self._generate_workflow_description(state.parsed_intent),
    #             "steps": state.workflow_steps,
    #             "metadata": {
    #                 "correlation_id": state.correlation_id,
    #                 "parsed_intent": state.parsed_intent,
    #                 "generation_timestamp": datetime.utcnow().isoformat(),
    #                 "tool_count": len(state.available_tools),
    #                 "step_count": len(state.workflow_steps)
    #             },
    #             "status": "draft",
    #             "created_at": datetime.utcnow().isoformat(),
    #             "updated_at": datetime.utcnow().isoformat()
    #         }
            
    #         return {
    #             "final_workflow": workflow_definition,
    #             "status": "completed"
    #         }
            
    #     except Exception as e:
    #         return {
    #             "errors": [f"Workflow finalization failed: {str(e)}"],
    #             "status": "error"
    #         }
    
    # async def _handle_error_node(self, state: WorkflowGenerationState) -> Dict[str, Any]:
    #     """Handle errors during workflow generation"""
    #     errors = state.errors
        
    #     # Log errors for monitoring
    #     error_context = {
    #         "user_id": state.user_id,
    #         "correlation_id": state.correlation_id,
    #         "user_request": state.user_request,
    #         "errors": errors
    #     }
        
    #     # Return error state
    #     return {
    #         "status": "failed",
    #         "final_workflow": {
    #             "error": True,
    #             "errors": errors,
    #             "correlation_id": state.correlation_id
    #         }
    #     }
    
    # def _check_tools_available(self, state: WorkflowGenerationState) -> str:
    #     """Conditional edge function to check if sufficient tools are available"""
    #     available_tools = state.available_tools
    #     parsed_intent = state.parsed_intent
        
    #     if not available_tools:
    #         return "invalid"
        
    #     # Check if we have minimum required tools
    #     required_entities = parsed_intent.get("entities", [])
    #     tool_servers = set(tool.get("server_name", "") for tool in available_tools)
    #     required_servers = set(entity.lower() for entity in required_entities)
        
    #     if required_servers.issubset(tool_servers):
    #         return "valid"
    #     elif len(available_tools) == 0:
    #         return "invalid"
    #     else:
    #         return "retry"
    
    # Public API methods
    
    # async def generate_workflow(
    #     self, 
    #     user_request: str, 
    #     user_id: str,
    #     correlation_id: Optional[str] = None
    # ) -> Dict[str, Any]:
    #     """
    #     Generate a workflow from natural language request
        
    #     Args:
    #         user_request: Natural language description of desired workflow
    #         user_id: ID of the user requesting the workflow
    #         correlation_id: Optional correlation ID for tracking
            
    #     Returns:
    #         Dictionary containing workflow definition and metadata
    #     """
    #     correlation_id = correlation_id or str(uuid.uuid4())
        
    #     try:
    #         # Create initial state
    #         initial_state = WorkflowGenerationState(
    #             user_request=user_request,
    #             user_id=user_id,
    #             correlation_id=correlation_id
    #         )
            
    #         # Execute LangGraph workflow generation
    #         result = await self.generation_graph.ainvoke(initial_state.dict())
            
    #         if result.get("status") == "completed":
    #             # Save workflow to database
    #             workflow_data = result["final_workflow"]
                
    #             save_result = await self.database.insert(
    #                 "workflows",
    #                 workflow_data
    #             )
                
    #             if save_result.get("error"):
    #                 raise WorkflowGenerationError(
    #                     "Failed to save generated workflow",
    #                     correlation_id=correlation_id,
    #                     details={"database_error": save_result["error"]}
    #                 )
                
    #             return {
    #                 "success": True,
    #                 "workflow_id": workflow_data["id"],
    #                 "definition": workflow_data,
    #                 "steps": workflow_data["steps"],
    #                 "correlation_id": correlation_id
    #             }
    #         else:
    #             # Handle generation failure
    #             errors = result.get("errors", ["Unknown error during generation"])
    #             raise WorkflowGenerationError(
    #                 f"Workflow generation failed: {'; '.join(errors)}",
    #                 correlation_id=correlation_id,
    #                 details={"generation_errors": errors}
    #             )
                
    #     except Exception as e:
    #         if isinstance(e, WorkflowGenerationError):
    #             raise
    #         else:
    #             raise WorkflowGenerationError(
    #                 f"Unexpected error during workflow generation: {str(e)}",
    #                 correlation_id=correlation_id,
    #                 details={"exception_type": type(e).__name__}
    #             )
    
    async def get_workflow(self, workflow_id: str, user_id: str) -> Optional[WorkflowDefinition]:
        """Get workflow by ID"""
        try:
            result = await self.database.select(
                "workflows",
                filters={"id": workflow_id, "user_id": user_id}
            )
            
            if not result.get("data"):
                return None
                
            workflow_data = result["data"][0]
            return WorkflowDefinition(**workflow_data)
            
        except Exception as e:
            raise NotFoundException(
                f"Workflow {workflow_id} not found",
                correlation_id=self.correlation_id,
                details={"workflow_id": workflow_id, "user_id": user_id}
            )
    
    async def list_user_workflows(self, user_id: str, status: Optional[str] = None) -> List[WorkflowDefinition]:
        """List workflows for a user"""
        try:
            filters = {"user_id": user_id}
            if status:
                filters["status"] = status
                
            result = await self.database.select(
                "workflows",
                filters=filters,
                order_by=[{"field": "created_at", "direction": "desc"}]
            )
            
            workflows = []
            for workflow_data in result.get("data", []):
                workflows.append(WorkflowDefinition(**workflow_data))
                
            return workflows
            
        except Exception as e:
            raise ExternalServiceException(
                f"Failed to list workflows for user {user_id}",
                correlation_id=self.correlation_id,
                details={"user_id": user_id, "status": status}
            )
    
    async def update_workflow_status(
        self, 
        workflow_id: str, 
        user_id: str, 
        new_status: str
    ) -> bool:
        """Update workflow status"""
        try:
            result = await self.database.update(
                "workflows",
                {"status": new_status, "updated_at": datetime.utcnow().isoformat()},
                {"id": workflow_id, "user_id": user_id}
            )
            
            return result.get("data") is not None
            
        except Exception as e:
            raise ExternalServiceException(
                f"Failed to update workflow {workflow_id} status to {new_status}",
                correlation_id=self.correlation_id,
                details={"workflow_id": workflow_id, "user_id": user_id, "new_status": new_status}
            )
    
    # Helper methods
    
    async def _get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Get user context for better workflow generation"""
        try:
            cache_key = f"user_context:{user_id}"
            cached_context = await self.cache.get(cache_key)
            
            if cached_context:
                return cached_context
            
            # Load from database
            result = await self.database.select(
                "user_contexts",
                filters={"user_id": user_id}
            )
            
            context = {}
            if result.get("data"):
                context = result["data"][0].get("context_data", {})
                # Cache for 30 minutes
                await self.cache.set(cache_key, context, ttl=1800)
            
            return context
            
        except Exception:
            # Return empty context if unavailable
            return {}
    
    # def _build_intent_parsing_prompt(self, user_request: str, user_context: Dict[str, Any]) -> str:
    #     """Build prompt for LLM intent parsing"""
    #     return f"""
    #     Parse the following user request and extract structured workflow intent.
        
    #     User Request: {user_request}
        
    #     User Context: {user_context.get('preferences', {})}
        
    #     Extract and return JSON with:
    #     - entities: List of mentioned tools/services (e.g., ["Slack", "Notion"])
    #     - action: Main action (e.g., "sync", "notify", "backup")
    #     - source: Source system (if applicable)
    #     - target: Target system (if applicable)  
    #     - parameters: Additional parameters mentioned
        
    #     Example Response:
    #     {{
    #         "entities": ["Slack", "Notion"],
    #         "action": "sync",
    #         "source": "slack",
    #         "target": "notion",
    #         "parameters": {{"channel_name": "team-updates"}}
    #     }}
    #     """
    
    # def _parse_llm_intent_response(self, response: str) -> Dict[str, Any]:
    #     """Parse LLM response into structured intent"""
    #     import json
    #     try:
    #         # Extract JSON from response
    #         start_idx = response.find("{")
    #         end_idx = response.rfind("}") + 1
    #         json_str = response[start_idx:end_idx]
            
    #         return json.loads(json_str)
    #     except Exception:
    #         # Fallback parsing
    #         return {
    #             "entities": ["generic"],
    #             "action": "process",
    #             "source": None,
    #             "target": None,
    #             "parameters": {}
    #         }
    
    # async def _generate_sync_workflow_steps(
    #     self, 
    #     intent: Dict[str, Any], 
    #     context: Dict[str, Any], 
    #     tools: List[Dict[str, Any]], 
    #     step_counter: int
    # ) -> List[Dict[str, Any]]:
    #     """Generate steps for sync workflows"""
    #     steps = []
        
    #     source_tools = context.get("source_tools", [])
    #     target_tools = context.get("target_tools", [])
        
    #     # Step 1: Get data from source
    #     if source_tools:
    #         source_tool = source_tools[0]  # Use first available tool
    #         steps.append({
    #             "id": f"step_{step_counter}",
    #             "name": f"Get data from {intent.get('source', 'source')}",
    #             "tool_name": source_tool["name"],
    #             "parameters": intent.get("parameters", {}),
    #             "dependencies": [],
    #             "parallel_eligible": False
    #         })
    #         step_counter += 1
        
    #     # Step 2: Transform data (if needed)
    #     steps.append({
    #         "id": f"step_{step_counter}",
    #         "name": "Transform data format",
    #         "tool_name": "data_transformer",
    #         "parameters": {"format": "json"},
    #         "dependencies": [steps[-1]["id"]] if steps else [],
    #         "parallel_eligible": False
    #     })
    #     step_counter += 1
        
    #     # Step 3: Save to target
    #     if target_tools:
    #         target_tool = target_tools[0]  # Use first available tool
    #         steps.append({
    #             "id": f"step_{step_counter}",
    #             "name": f"Save to {intent.get('target', 'target')}",
    #             "tool_name": target_tool["name"],
    #             "parameters": intent.get("parameters", {}),
    #             "dependencies": [steps[-1]["id"]] if steps else [],
    #             "parallel_eligible": False
    #         })
        
    #     return steps
    
    # async def _generate_notification_workflow_steps(
    #     self, 
    #     intent: Dict[str, Any], 
    #     context: Dict[str, Any], 
    #     tools: List[Dict[str, Any]], 
    #     step_counter: int
    # ) -> List[Dict[str, Any]]:
    #     """Generate steps for notification workflows"""
    #     steps = []
        
    #     # Implementation for notification workflows
    #     # This would be expanded based on specific notification patterns
        
    #     return steps
    
    # async def _generate_generic_workflow_steps(
    #     self, 
    #     intent: Dict[str, Any], 
    #     context: Dict[str, Any], 
    #     tools: List[Dict[str, Any]], 
    #     step_counter: int
    # ) -> List[Dict[str, Any]]:
    #     """Generate generic workflow steps"""
    #     steps = []
        
    #     # Implementation for generic workflows
    #     # This would analyze the intent and create appropriate steps
        
    #     return steps
    
    # def _can_run_in_parallel(self, step: Dict[str, Any], previous_steps: List[Dict[str, Any]]) -> bool:
    #     """Check if a step can run in parallel with others"""
    #     dependencies = step.get("dependencies", [])
        
    #     # If step has no dependencies, it can potentially run in parallel
    #     if not dependencies:
    #         return True
        
    #     # Check if dependencies are already satisfied
    #     completed_steps = [s["id"] for s in previous_steps]
    #     return all(dep in completed_steps for dep in dependencies)
    
    # def _generate_workflow_name(self, intent: Dict[str, Any]) -> str:
    #     """Generate a descriptive name for the workflow"""
    #     action = intent.get("action", "process")
    #     source = intent.get("source", "")
    #     target = intent.get("target", "")
        
    #     if source and target:
    #         return f"{action.title()} {source.title()} to {target.title()}"
    #     elif source:
    #         return f"{action.title()} from {source.title()}"
    #     elif target:
    #         return f"{action.title()} to {target.title()}"
    #     else:
    #         return f"{action.title()} Workflow"
    
    # def _generate_workflow_description(self, intent: Dict[str, Any]) -> str:
    #     """Generate a description for the workflow"""
    #     action = intent.get("action", "process")
    #     entities = intent.get("entities", [])
        
    #     if len(entities) >= 2:
    #         return f"Automatically {action} data between {' and '.join(entities)}"
    #     elif entities:
    #         return f"Automatically {action} data using {entities[0]}"
    #     else:
    #         return f"Automated {action} workflow" 
