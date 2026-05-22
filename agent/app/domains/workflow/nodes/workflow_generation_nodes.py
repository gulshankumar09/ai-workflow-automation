"""Workflow Generation Nodes for Conversational Workflows

This module handles conversational workflow generation using selected and validated MCP tools.
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from langchain_core.prompts import PromptTemplate

from ..graphs.states import WorkflowState, ConversationPhase
from ....shared import get_logger
from ....shared.exceptions import WorkflowGenerationError
from ....application.mcp_service import MCPService
from ....ai.llm import get_llm
from ....infrastructure.database.providers.factory import DatabaseProviderFactory
from .intent_classification import _extract_and_parse_json

logger = get_logger(__name__)


async def generate_workflow_node(state: WorkflowState, mcp_service: MCPService = None) -> Dict[str, Any]:
    """Generate workflow using selected and validated MCP tools with enhanced analysis.
    
    Args:
        state: Current conversational workflow state
        mcp_service: Optional MCP service instance
        
    Returns:
        Updated state with generated workflow
    """
    try:
        logger.info("Starting enhanced workflow generation with MCP tools...")
        
        collected_requirements = state.get("collected_requirements", {})
        
        # Get tools from the enhanced discovery process
        selected_tools = state.get("selected_tools", [])
        validated_tools = state.get("validated_tools", [])
        discovered_tools = state.get("discovered_tools", [])
        
        # Collect user-provided tool parameters
        user_provided_parameters = _extract_user_tool_parameters(state)
        
        # Use the best available tool set (preference order)
        tools_to_use = validated_tools or selected_tools or discovered_tools
        
        user_id = state.get("user_id", "")
        session_id = state.get("session_id", "")
        correlation_id = state.get("correlation_id", "unknown")
        tool_selection_reasoning = state.get("conversation_context", {}).get("tool_selection_reasoning", "")
        
        logger.info(f"[{correlation_id}] Using {len(tools_to_use)} tools for workflow generation")
        
        if not tools_to_use:
            return {
                "assistant_response": "I need to discover and validate some tools first. Let me find what's available for your workflow.",
                "conversation_phase": ConversationPhase.TOOL_DISCOVERY.value
            }
        
        # Use LLM to generate intelligent workflow steps
        workflow_result = await _generate_intelligent_workflow_with_llm(
            current_message=state.get("current_message", ""),
            requirements=collected_requirements,
            available_tools=tools_to_use,
            user_parameters=user_provided_parameters,
            tool_reasoning=tool_selection_reasoning,
            correlation_id=correlation_id
        )
        
        # Create enhanced workflow definition
        workflow_definition = {
            "name": workflow_result.get("workflow_name", f"Generated Workflow - {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
            "description": workflow_result.get("workflow_description", _build_workflow_description(collected_requirements)),
            "steps": workflow_result.get("workflow_steps", []),
            "mcp_tools_used": [_get_tool_name(tool) for tool in tools_to_use],
            "tool_selection_reasoning": tool_selection_reasoning,
            "execution_strategy": workflow_result.get("execution_strategy", "sequential"),
            "estimated_duration": workflow_result.get("estimated_duration", "5-10 minutes"),
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "session_id": session_id,
                "correlation_id": correlation_id,
                "mcp_integration": True,
                "tool_count": len(tools_to_use),
                "step_count": len(workflow_result.get("workflow_steps", [])),
                "generation_method": "llm_enhanced",
                "user_parameters_provided": len(user_provided_parameters) > 0
            }
        }
        
        # Save workflow to database
        saved_workflow = await _save_workflow_to_database(
            workflow_definition=workflow_definition,
            user_id=user_id,
            correlation_id=correlation_id
        )
        
        # Generate enhanced user-friendly workflow review
        workflow_review = _generate_enhanced_workflow_review(
            workflow_definition, 
            tools_to_use, 
            workflow_result.get("user_benefits", []),
            correlation_id,
            saved_workflow.get("id") if saved_workflow else None
        )
        
        logger.info(f"[{correlation_id}] Enhanced workflow generated successfully with {len(workflow_definition['steps'])} steps")
        
        return {
            "workflow_draft": workflow_definition,
            "saved_workflow_id": saved_workflow.get("id") if saved_workflow else None,
            "assistant_response": workflow_review,
            "should_generate_workflow": True,
            "workflow_complete": True,
            "conversation_phase": ConversationPhase.WORKFLOW_REVIEW.value
        }
        
    except Exception as e:
        logger.error(f"[{correlation_id}] Enhanced workflow generation failed: {e}")
        return {
            "assistant_response": "I encountered an issue while generating your workflow. Let me gather more information about your requirements.",
            "errors": [f"Workflow generation failed: {str(e)}"],
            "conversation_phase": ConversationPhase.REQUIREMENT_GATHERING.value
        }


async def _generate_intelligent_workflow_with_llm(
    current_message: str,
    requirements: Dict[str, Any],
    available_tools: List[Dict[str, Any]], 
    user_parameters: Dict[str, Any],
    tool_reasoning: str,
    correlation_id: str
) -> Dict[str, Any]:
    """Generate intelligent workflow using LLM with available tools and user parameters.
    
    Args:
        requirements: Workflow requirements dictionary
        available_tools: List of selected/validated MCP tools
        user_parameters: User-provided tool parameters
        tool_reasoning: LLM reasoning for tool selection
        correlation_id: Request correlation ID
        
    Returns:
        Dictionary containing intelligent workflow structure
    """
    try:
        logger.info(f"[{correlation_id}] Generating intelligent workflow with LLM")
        
        llm = get_llm()
        
        # Create comprehensive workflow generation prompt
        workflow_prompt = PromptTemplate(
            input_variables=["current_message", "requirements", "tools", "user_parameters", "tool_reasoning"],
            template="""You are an expert workflow architect. Generate a comprehensive, executable workflow using the provided tools and requirements.

User Message: {current_message}

WORKFLOW REQUIREMENTS:
{requirements}

AVAILABLE TOOLS:
{tools}

USER PROVIDED PARAMETERS:
{user_parameters}

TOOL SELECTION REASONING:
{tool_reasoning}

Your task is to create a practical, executable workflow that:
1. **FOLLOWS LOGICAL SEQUENCE** - Order steps logically based on dependencies
2. **USES AVAILABLE TOOLS** - Only use the tools provided in the available tools list
3. **INCORPORATES USER PARAMETERS** - Use the parameters provided by the user
4. **HANDLES ERROR SCENARIOS** - Include error handling and retry logic
5. **PROVIDES CLEAR DESCRIPTIONS** - Each step should be understandable

WORKFLOW GENERATION GUIDELINES:
- Start with authentication/setup steps if needed
- Follow data flow: source → processing → target
- Include validation steps between major operations
- Add error handling and rollback capabilities
- Estimate realistic timeouts and retry counts
- Use provided user parameters in appropriate steps

RESPONSE FORMAT (JSON only):
{{
    "workflow_name": "descriptive workflow name",
    "workflow_description": "clear description of what the workflow accomplishes",
    "execution_strategy": "sequential|parallel|hybrid",
    "estimated_duration": "realistic time estimate",
    "workflow_steps": [
        {{
            "step_id": "step_1",
            "step_name": "descriptive step name",
            "tool_name": "exact_tool_name_from_available_tools",
            "server_name": "server_name_from_tools",
            "description": "detailed step description",
            "step_type": "authentication|data_retrieval|data_processing|data_output|validation|notification",
            "parameters": {{}},
            "dependencies": [],
            "timeout_seconds": 30,
            "retry_count": 3,
            "error_handling": "continue|stop|retry|fallback",
            "expected_output": "description of expected output",
            "validation_criteria": "how to validate step success"
        }}
    ],
    "user_benefits": [
        "benefit 1: specific outcome user will see",
        "benefit 2: time/effort saved",
        "benefit 3: automation advantage"
    ],
    "prerequisites": [
        "any setup or permissions needed"
    ],
    "success_criteria": "how to measure workflow success",
    "troubleshooting": {{
        "common_issues": [
            {{"issue": "description", "solution": "how to fix"}}
        ]
    }}
}}

EXAMPLES:
For "sync GitHub issues to Slack":
- Step 1: Authenticate with GitHub (using github_auth_tool)
- Step 2: Retrieve open issues (using github_issues_tool)
- Step 3: Format issue data (using data_transform_tool)
- Step 4: Send to Slack channel (using slack_message_tool)
- Step 5: Confirm delivery (using validation_tool)

For "backup Notion pages to storage":
- Step 1: Authenticate with Notion (using notion_auth_tool)
- Step 2: List pages to backup (using notion_pages_tool)
- Step 3: Export page content (using notion_export_tool)
- Step 4: Upload to storage (using file_storage_tool)
- Step 5: Verify backup integrity (using validation_tool)"""
        )
        
        # Format tools for the prompt
        tools_formatted = _format_tools_for_workflow_generation(available_tools)
        requirements_formatted = json.dumps(requirements, indent=2)
        user_params_formatted = json.dumps(user_parameters, indent=2)
        
        formatted_prompt = workflow_prompt.format(
            current_message=current_message,
            requirements=requirements_formatted,
            tools=tools_formatted,
            user_parameters=user_params_formatted,
            tool_reasoning=tool_reasoning
        )
        
        response = await llm.ainvoke(formatted_prompt)
        response_content = response.content.strip()
        
        logger.info(f"[{correlation_id}] Raw LLM response for workflow generation: {response_content[:500]}...")
        
        # Parse the LLM response
        workflow_result = _extract_and_parse_json(response_content)
        
        if workflow_result:
            # Validate and enhance the workflow steps
            workflow_steps = workflow_result.get("workflow_steps", [])
            enhanced_steps = _enhance_workflow_steps_with_user_params(workflow_steps, user_parameters, available_tools)
            workflow_result["workflow_steps"] = enhanced_steps
            
            logger.info(f"[{correlation_id}] Intelligent workflow generation complete: {len(enhanced_steps)} steps")
            return workflow_result
        else:
            logger.warning(f"[{correlation_id}] Failed to parse workflow generation JSON, using fallback")
            return _fallback_workflow_generation(requirements, available_tools, user_parameters)
            
    except Exception as e:
        logger.error(f"[{correlation_id}] Intelligent workflow generation failed: {str(e)}")
        return _fallback_workflow_generation(requirements, available_tools, user_parameters)


async def _save_workflow_to_database(
    workflow_definition: Dict[str, Any],
    user_id: str,
    correlation_id: str
) -> Dict[str, Any]:
    """Save the generated workflow to the database.
    
    Args:
        workflow_definition: The complete workflow definition
        user_id: User identifier
        correlation_id: Request correlation ID
        
    Returns:
        Dictionary containing the saved workflow information
    """
    try:
        logger.info(f"[{correlation_id}] Saving workflow to database for user {user_id}")
        
        # Initialize database provider
        db_provider = DatabaseProviderFactory.create_provider()
        
        # Check if a similar workflow already exists for this user
        existing_workflow = await _check_existing_workflow(
            db_provider=db_provider,
            user_id=user_id,
            workflow_name=workflow_definition.get("name", ""),
            correlation_id=correlation_id
        )
        
        if existing_workflow:
            logger.info(f"[{correlation_id}] Updating existing workflow: {existing_workflow.get('id')}")
            return await _update_existing_workflow(
                db_provider=db_provider,
                workflow_id=existing_workflow.get("id"),
                workflow_definition=workflow_definition,
                correlation_id=correlation_id
            )
        
        # Generate new workflow ID
        workflow_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Prepare workflow data for database insertion
        workflow_data = {
            "id": workflow_id,
            "user_id": user_id,
            "name": workflow_definition.get("name", "Generated Workflow"),
            "description": workflow_definition.get("description", ""),
            "definition": workflow_definition,  # Store the complete workflow definition as JSONB
            "status": "draft",  # Initial status
            "tags": [],  # Empty tags array initially
            "created_at": current_time,
            "updated_at": current_time
        }
        
        # Insert workflow into database
        result = await db_provider.insert(
            table="workflows",
            data=workflow_data,
            returning=["id", "name", "status", "created_at"]
        )
        
        if result and result.get("data"):
            saved_workflow = result["data"]
            logger.info(f"[{correlation_id}] Workflow saved successfully with ID: {workflow_id}")
            return saved_workflow
        elif result:
            # Handle case where insert succeeded but no data returned
            logger.info(f"[{correlation_id}] Workflow saved successfully (no data returned)")
            return {"id": workflow_id, "status": "saved"}
        else:
            logger.warning(f"[{correlation_id}] Workflow save operation returned no result")
            return {"id": workflow_id, "status": "saved"}
            
    except Exception as e:
        logger.error(f"[{correlation_id}] Failed to save workflow to database: {str(e)}")
        # Don't fail the entire workflow generation if database save fails
        # Just log the error and continue
        return None


async def _check_existing_workflow(
    db_provider,
    user_id: str,
    workflow_name: str,
    correlation_id: str
) -> Optional[Dict[str, Any]]:
    """Check if a similar workflow already exists for the user.
    
    Args:
        db_provider: Database provider instance
        user_id: User identifier
        workflow_name: Name of the workflow to check
        correlation_id: Request correlation ID
        
    Returns:
        Existing workflow data if found, None otherwise
    """
    try:
        # Check for workflows with the same name for this user
        result = await db_provider.select(
            table="workflows",
            columns=["id", "name", "status", "created_at"],
            filters={
                "user_id": user_id,
                "name": workflow_name
            },
            order_by={"created_at": "desc"},
            limit=1
        )
        
        if result and result.get("data") and len(result["data"]) > 0:
            existing_workflow = result["data"][0]
            logger.info(f"[{correlation_id}] Found existing workflow: {existing_workflow.get('id')}")
            return existing_workflow
        
        return None
        
    except Exception as e:
        logger.warning(f"[{correlation_id}] Error checking for existing workflow: {str(e)}")
        return None


async def _update_existing_workflow(
    db_provider,
    workflow_id: str,
    workflow_definition: Dict[str, Any],
    correlation_id: str
) -> Dict[str, Any]:
    """Update an existing workflow with new definition.
    
    Args:
        db_provider: Database provider instance
        workflow_id: ID of the workflow to update
        workflow_definition: New workflow definition
        correlation_id: Request correlation ID
        
    Returns:
        Updated workflow data
    """
    try:
        current_time = datetime.now(timezone.utc).isoformat()
        
        # Prepare update data
        update_data = {
            "definition": workflow_definition,
            "description": workflow_definition.get("description", ""),
            "status": "updated",
            "updated_at": current_time
        }
        
        # Update the workflow
        result = await db_provider.update(
            table="workflows",
            data=update_data,
            filters={"id": workflow_id},
            returning=["id", "name", "status", "updated_at"]
        )
        
        if result and result.get("data"):
            updated_workflow = result["data"]
            logger.info(f"[{correlation_id}] Workflow updated successfully: {workflow_id}")
            return updated_workflow
        else:
            logger.warning(f"[{correlation_id}] Workflow update operation returned no data")
            return {"id": workflow_id, "status": "updated"}
            
    except Exception as e:
        logger.error(f"[{correlation_id}] Failed to update workflow: {str(e)}")
        return {"id": workflow_id, "status": "update_failed"}


def _extract_user_tool_parameters(state: WorkflowState) -> Dict[str, Any]:
    """Extract user-provided tool parameters from the conversation state.
    
    Args:
        state: Current conversational workflow state
        
    Returns:
        Dictionary of user-provided tool parameters
    """
    user_parameters = {}
    
    # Get parameters from user input
    user_input = state.get("user_input", "")
    
    # Get parameters from collected requirements
    collected_requirements = state.get("collected_requirements", {})
    extracted_params = collected_requirements.get("extracted_parameters", {})
    
    # Merge explicit and implicit parameters
    user_parameters.update(extracted_params.get("explicit_params", {}))
    user_parameters.update(extracted_params.get("implicit_params", {}))
    user_parameters.update(extracted_params.get("user_context_params", {}))
    
    # Get parameters from tool parameter collection
    # (This would be populated if user provided tool-specific parameters)
    tool_parameters = state.get("tool_parameters", {})
    user_parameters.update(tool_parameters)
    
    return user_parameters


def _format_tools_for_workflow_generation(tools: List[Dict[str, Any]]) -> str:
    """Format tools for workflow generation prompt.
    
    Args:
        tools: List of available MCP tools
        
    Returns:
        Formatted string representation of tools
    """
    if not tools:
        return "No tools available."
    
    tool_descriptions = []
    for i, tool in enumerate(tools, 1):
        tool_name = _get_tool_name(tool)
        server_name = tool.get("server_name", "unknown")
        description = tool.get("description", "No description")
        workflow_role = tool.get("workflow_role", "utility")
        parameters_schema = tool.get("parameters_schema", {})
        
        # Extract parameter information
        if isinstance(parameters_schema, dict) and "properties" in parameters_schema:
            required_params = parameters_schema.get("required", [])
            optional_params = [p for p in parameters_schema["properties"].keys() if p not in required_params]
            params_info = f"Required: {', '.join(required_params[:3])}" if required_params else "No required params"
            if optional_params:
                params_info += f" | Optional: {', '.join(optional_params[:3])}"
        else:
            params_info = "Parameters schema not available"
        
        tool_descriptions.append(
            f"{i}. **{tool_name}** (Server: {server_name})\n"
            f"   Role: {workflow_role}\n"
            f"   Description: {description}\n"
            f"   Parameters: {params_info}\n"
            f"   Schema: {json.dumps(parameters_schema, indent=4) if parameters_schema else 'Not available'}"
        )
    
    return "\n\n".join(tool_descriptions)


def _enhance_workflow_steps_with_user_params(
    workflow_steps: List[Dict[str, Any]], 
    user_parameters: Dict[str, Any],
    available_tools: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Enhance workflow steps with user-provided parameters and tool validation.
    
    Args:
        workflow_steps: Generated workflow steps
        user_parameters: User-provided parameters
        available_tools: Available MCP tools
        
    Returns:
        Enhanced workflow steps
    """
    enhanced_steps = []
    
    for step in workflow_steps:
        enhanced_step = step.copy()
        
        # Merge user parameters into step parameters
        step_params = enhanced_step.get("parameters", {})
        
        # Add user parameters that match this step's tool
        tool_name = enhanced_step.get("tool_name", "")
        for param_key, param_value in user_parameters.items():
            # Add parameter if it matches tool name or is a general parameter
            if tool_name.lower() in param_key.lower() or param_key in ["repository", "channel", "token", "webhook_url", "database", "table"]:
                step_params[param_key.replace(f"{tool_name}_", "")] = param_value
        
        enhanced_step["parameters"] = step_params
        
        # Validate tool exists in available tools
        tool_exists = any(_get_tool_name(tool) == tool_name for tool in available_tools)
        if not tool_exists:
            enhanced_step["validation_warning"] = f"Tool '{tool_name}' not found in available tools"
        
        enhanced_steps.append(enhanced_step)
    
    return enhanced_steps


def _get_tool_name(tool: Dict[str, Any]) -> str:
    """Get tool name from tool dictionary, handling both old and new formats.
    
    Args:
        tool: Tool configuration dictionary
        
    Returns:
        Tool name string
    """
    return tool.get("tool_name") or tool.get("name", "unknown_tool")


def _fallback_workflow_generation(
    requirements: Dict[str, Any],
    available_tools: List[Dict[str, Any]], 
    user_parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Fallback workflow generation when LLM generation fails.
    
    Args:
        requirements: Workflow requirements
        available_tools: Available tools
        user_parameters: User parameters
        
    Returns:
        Basic workflow structure
    """
    workflow_intent = requirements.get("workflow_intent", {})
    action = workflow_intent.get("action_type", "process")
    data_type = workflow_intent.get("data_type", "data")
    
    # Generate basic steps using available tools
    steps = []
    for i, tool in enumerate(available_tools[:3]):  # Limit to 3 tools
        step = {
            "step_id": f"step_{i+1}",
            "step_name": f"Execute {_get_tool_name(tool)}",
            "tool_name": _get_tool_name(tool),
            "server_name": tool.get("server_name", "unknown"),
            "description": f"Execute {_get_tool_name(tool)}: {tool.get('description', 'Basic operation')}",
            "step_type": "processing",
            "parameters": _generate_tool_parameters(tool, requirements, user_parameters),
            "dependencies": [f"step_{i}"] if i > 0 else [],
            "timeout_seconds": 30,
            "retry_count": 3,
            "error_handling": "retry",
            "expected_output": f"Processed {data_type}",
            "validation_criteria": "Operation completed without errors"
        }
        steps.append(step)
    
    return {
        "workflow_name": f"Basic {action} Workflow",
        "workflow_description": f"Basic workflow to {action} {data_type}",
        "execution_strategy": "sequential",
        "estimated_duration": "2-5 minutes",
        "workflow_steps": steps,
        "user_benefits": [f"Automated {action} of {data_type}"],
        "prerequisites": ["Required tools must be configured"],
        "success_criteria": "All steps complete without errors"
    }


def _generate_tool_parameters(tool: Dict[str, Any], requirements: Dict[str, Any], user_parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate parameters for a tool based on requirements and user parameters.
    
    Args:
        tool: Tool configuration dictionary
        requirements: Workflow requirements dictionary
        user_parameters: User-provided parameters
        
    Returns:
        Generated parameters dictionary
    """
    parameters = {}
    
    # Get tool's parameter schema
    schema = tool.get("parameters_schema", {})
    workflow_intent = requirements.get("workflow_intent", {})
    extracted_params = requirements.get("extracted_parameters", {})
    
    # Map common parameters from workflow intent
    source_platform = workflow_intent.get("source_platform")
    target_platform = workflow_intent.get("target_platform")
    action_type = workflow_intent.get("action_type")
    data_type = workflow_intent.get("data_type")
    
    # Map schema fields to requirements
    for param_name, param_type in schema.items():
        if param_name == "repository" and source_platform == "github":
            parameters[param_name] = extracted_params.get("repository", "example/repo")
        elif param_name == "channel" and (source_platform == "slack" or target_platform == "slack"):
            parameters[param_name] = extracted_params.get("channel", "#general")
        elif param_name == "message":
            parameters[param_name] = f"Automated workflow: {action_type} {data_type}"
        elif param_name == "path":
            parameters[param_name] = extracted_params.get("path", "/tmp/workflow")
        elif param_name == "action":
            parameters[param_name] = action_type or "process"
        elif param_name == "database":
            parameters[param_name] = extracted_params.get("database", "default")
        elif param_name == "table":
            parameters[param_name] = extracted_params.get("table", "data")
        elif param_name == "query":
            parameters[param_name] = f"SELECT * FROM {data_type}"
        elif param_name in extracted_params:
            parameters[param_name] = extracted_params[param_name]
    
    # Add any custom parameters from requirements
    custom_params = requirements.get("parameters", {})
    parameters.update(custom_params)
    
    # Add user parameters that match this tool's parameters
    for param_key, param_value in user_parameters.items():
        if param_key in parameters:
            parameters[param_key] = param_value
    
    return parameters


def _determine_step_type(tool: Dict[str, Any], action: str) -> str:
    """Determine the type of workflow step based on tool and action.
    
    Args:
        tool: Tool configuration dictionary
        action: Action type from requirements
        
    Returns:
        Step type string
    """
    tool_name = _get_tool_name(tool).lower()
    server_name = tool.get("server_name", "").lower()
    
    # Categorize based on tool characteristics
    if any(keyword in tool_name for keyword in ["github", "git"]):
        return "source_control"
    elif any(keyword in tool_name for keyword in ["slack", "discord", "teams", "notification"]):
        return "communication"
    elif any(keyword in tool_name for keyword in ["postgres", "database", "sql"]):
        return "data_storage"
    elif any(keyword in tool_name for keyword in ["file", "filesystem", "storage"]):
        return "file_operation"
    elif any(keyword in tool_name for keyword in ["api", "http", "webhook"]):
        return "api_call"
    elif action:
        action_lower = action.lower()
        if action_lower in ["sync", "synchronize"]:
            return "synchronization"
        elif action_lower in ["transform", "process"]:
            return "transformation"
        elif action_lower in ["monitor", "watch"]:
            return "monitoring"
        elif action_lower in ["notify", "alert"]:
            return "notification"
    
    return "processing"  # Default


def _generate_expected_output(tool: Dict[str, Any], data_type: str) -> str:
    """Generate expected output description for a workflow step.
    
    Args:
        tool: Tool configuration dictionary
        data_type: Data type from requirements
        
    Returns:
        Expected output description string
    """
    tool_name = _get_tool_name(tool).lower()
    
    if any(keyword in tool_name for keyword in ["github", "git"]):
        return f"Repository {data_type} information"
    elif any(keyword in tool_name for keyword in ["slack", "discord", "teams"]):
        return f"Message sent with {data_type} content"
    elif any(keyword in tool_name for keyword in ["postgres", "database"]):
        return f"Database {data_type} records"
    elif any(keyword in tool_name for keyword in ["file", "filesystem"]):
        return f"File {data_type} operation result"
    elif data_type:
        return f"Processed {data_type} data"
    else:
        return "Operation completed successfully"


def _build_workflow_description(requirements: Dict[str, Any]) -> str:
    """Build a description for the workflow based on requirements.
    
    Args:
        requirements: Workflow requirements dictionary
        
    Returns:
        Workflow description string
    """
    workflow_intent = requirements.get("workflow_intent", {})
    
    source = workflow_intent.get("source_platform", requirements.get("source", ""))
    target = workflow_intent.get("target_platform", requirements.get("target", ""))
    action = workflow_intent.get("action_type", requirements.get("action", ""))
    data_type = workflow_intent.get("data_type", "data")
    
    if source and target and action:
        return f"Workflow to {action} {data_type} from {source} to {target}"
    elif action and data_type:
        return f"Workflow to {action} {data_type}"
    elif action:
        return f"Workflow to {action}"
    else:
        return "Custom automated workflow"


def _generate_enhanced_workflow_review(
    workflow_definition: Dict[str, Any],
    tools: List[Dict[str, Any]],
    user_benefits: List[str],
    correlation_id: str,
    saved_workflow_id: str = None
) -> str:
    """Generate a user-friendly workflow review.
    
    Args:
        workflow_definition: Generated workflow definition
        tools: List of validated tools used
        user_benefits: List of user benefits
        correlation_id: Request correlation ID
        saved_workflow_id: ID of the saved workflow in database
        
    Returns:
        User-friendly workflow review string
    """
    steps = workflow_definition.get("steps", [])
    tools_used = [_get_tool_name(tool) for tool in tools]
    
    review = f"""🎯 **Workflow Generated Successfully!**

**What it does:** {workflow_definition.get("description", "Custom workflow")}

**Steps involved:** {len(steps)} steps
**Tools used:** {", ".join(tools_used[:3])}{"..." if len(tools_used) > 3 else ""}

**Workflow Preview:**
"""
    
    for i, step in enumerate(steps, 1):
        step_type_emoji = _get_step_type_emoji(step.get("step_type", "processing"))
        review += f"{step_type_emoji} {i}. {step.get('description', step.get('tool_name', 'Unknown step'))}\n"
    
    # Check if MCP is available by looking at validation status
    mcp_active = any(tool.get("validation_status") == "valid" for tool in tools)
    
    # Add database save information
    if saved_workflow_id:
        review += f"""
💾 **Workflow Saved:** Your workflow has been saved to the database with ID: `{saved_workflow_id}`

**MCP Integration:** {'🟢 Active' if mcp_active else '🟡 Simulated'}

✅ **Ready to execute!** Would you like me to run this workflow, or would you like to modify anything first?

💡 *Tip: You can ask me to modify specific steps or add new ones!*

**User Benefits:**
"""
    else:
        review += f"""
⚠️ **Note:** Workflow could not be saved to database, but it's ready for execution.

**MCP Integration:** {'🟢 Active' if mcp_active else '🟡 Simulated'}

✅ **Ready to execute!** Would you like me to run this workflow, or would you like to modify anything first?

💡 *Tip: You can ask me to modify specific steps or add new ones!*

**User Benefits:**
"""
    
    for benefit in user_benefits:
        review += f"- {benefit}\n"
    
    review += f"""
**MCP Integration:** {'🟢 Active' if mcp_active else '🟡 Simulated'}

✅ **Ready to execute!** Would you like me to run this workflow, or would you like to modify anything first?

💡 *Tip: You can ask me to modify specific steps or add new ones!*"""
    
    return review


def _get_step_type_emoji(step_type: str) -> str:
    """Get emoji for step type visualization.
    
    Args:
        step_type: Type of workflow step
        
    Returns:
        Appropriate emoji for the step type
    """
    emoji_map = {
        "source_control": "🔧",
        "communication": "💬", 
        "data_storage": "💾",
        "file_operation": "📁",
        "api_call": "🌐",
        "synchronization": "🔁",
        "transformation": "⚙️",
        "monitoring": "👀",
        "notification": "🔔",
        "processing": "⚡"
    }
    return emoji_map.get(step_type, "⚡")


async def get_user_workflows(
    user_id: str,
    correlation_id: str,
    limit: int = 10,
    offset: int = 0
) -> Dict[str, Any]:
    """Retrieve workflows for a specific user from the database.
    
    Args:
        user_id: User identifier
        correlation_id: Request correlation ID
        limit: Maximum number of workflows to return
        offset: Number of workflows to skip
        
    Returns:
        Dictionary containing user workflows and metadata
    """
    try:
        logger.info(f"[{correlation_id}] Retrieving workflows for user {user_id}")
        
        # Initialize database provider
        db_provider = DatabaseProviderFactory.create_provider()
        
        # Query workflows for the user
        result = await db_provider.select(
            table="workflows",
            columns=["id", "name", "description", "status", "created_at", "updated_at"],
            filters={"user_id": user_id},
            order_by={"created_at": "desc"},
            limit=limit,
            offset=offset
        )
        
        if result and result.get("data"):
            workflows = result["data"]
            logger.info(f"[{correlation_id}] Retrieved {len(workflows)} workflows for user {user_id}")
            
            return {
                "workflows": workflows,
                "total_count": len(workflows),
                "user_id": user_id,
                "correlation_id": correlation_id
            }
        else:
            logger.info(f"[{correlation_id}] No workflows found for user {user_id}")
            return {
                "workflows": [],
                "total_count": 0,
                "user_id": user_id,
                "correlation_id": correlation_id
            }
            
    except Exception as e:
        logger.error(f"[{correlation_id}] Failed to retrieve workflows for user {user_id}: {str(e)}")
        return {
            "workflows": [],
            "total_count": 0,
            "user_id": user_id,
            "error": str(e),
            "correlation_id": correlation_id
        }


async def get_workflow_by_id(
    workflow_id: str,
    user_id: str,
    correlation_id: str
) -> Dict[str, Any]:
    """Retrieve a specific workflow by ID for a user.
    
    Args:
        workflow_id: Workflow identifier
        user_id: User identifier
        correlation_id: Request correlation ID
        
    Returns:
        Dictionary containing the workflow data
    """
    try:
        logger.info(f"[{correlation_id}] Retrieving workflow {workflow_id} for user {user_id}")
        
        # Initialize database provider
        db_provider = DatabaseProviderFactory.create_provider()
        
        # Query the specific workflow
        result = await db_provider.select(
            table="workflows",
            columns=["id", "name", "description", "definition", "status", "tags", "created_at", "updated_at"],
            filters={
                "id": workflow_id,
                "user_id": user_id
            },
            limit=1
        )
        
        if result and result.get("data") and len(result["data"]) > 0:
            workflow = result["data"][0]
            logger.info(f"[{correlation_id}] Retrieved workflow {workflow_id} successfully")
            
            return {
                "workflow": workflow,
                "found": True,
                "correlation_id": correlation_id
            }
        else:
            logger.warning(f"[{correlation_id}] Workflow {workflow_id} not found for user {user_id}")
            return {
                "workflow": None,
                "found": False,
                "error": "Workflow not found",
                "correlation_id": correlation_id
            }
            
    except Exception as e:
        logger.error(f"[{correlation_id}] Failed to retrieve workflow {workflow_id}: {str(e)}")
        return {
            "workflow": None,
            "found": False,
            "error": str(e),
            "correlation_id": correlation_id
        } 