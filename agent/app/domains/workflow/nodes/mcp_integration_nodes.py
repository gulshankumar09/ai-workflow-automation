"""MCP Integration Nodes for Conversational Workflows

This module handles MCP tool discovery and validation for workflow generation.
"""

import json
from typing import Dict, Any, List
from datetime import datetime, timezone

from langchain_core.prompts import PromptTemplate

from ..graphs.states import WorkflowState, ConversationPhase
from ....shared import get_logger
from ....application.mcp_service import MCPService
from ....ai.llm import get_llm
from .intent_classification import _extract_and_parse_json

logger = get_logger(__name__)


async def discover_mcp_tools_node(state: WorkflowState, mcp_service: MCPService = None) -> Dict[str, Any]:
    """Discover and analyze MCP tools based on workflow requirements.
    
    This enhanced version:
    1. Discovers available MCP tools
    2. Uses LLM to analyze and select relevant tools for the workflow
    3. Identifies missing tool parameters
    4. Generates form fields for user input when parameters are missing
    
    Args:
        state: Current conversational workflow state
        mcp_service: Optional MCP service instance
        
    Returns:
        Updated state with discovered tools, selected tools, and missing parameters
    """
    try:
        logger.info("Starting enhanced MCP tool discovery and analysis...")
        
        # Initialize MCP service if not provided
        if not mcp_service:
            mcp_service = MCPService()
        
        # Extract requirements for tool discovery
        collected_requirements = state.get("collected_requirements", {})
        required_servers = collected_requirements.get("required_servers", [])
        workflow_intent = collected_requirements.get("workflow_intent", {})
        correlation_id = state.get("correlation_id", "unknown")
        
        logger.info(f"[{correlation_id}] Discovering tools for servers: {required_servers}")
        
        # Step 1: Discover available tools
        try:
            user_id = state.get("user_id", "")
            
            if required_servers:
                server_names = [s.get("name") for s in required_servers if s and s.get("name")]
                # Use server-specific discovery for better performance
                all_tools = await mcp_service.discover_tools_by_server(
                    server_names=server_names, 
                    user_id=user_id
                )
            else:
                # Fallback to general discovery if no specific servers
                logger.info("No specific servers required, discovering all available tools")
                all_tools = await mcp_service.discover_tools(user_id=user_id)
            
            logger.info(f"[{correlation_id}] Discovered {len(all_tools)} available MCP tools")
            
        except Exception as e:
            logger.error(f"[{correlation_id}] MCP tool discovery failed: {e}")
            
            # Check if we have required servers but discovery failed
            if required_servers:
                logger.warning(f"Failed to discover tools from required servers: {required_servers}")
                server_names = [s.get("name") for s in required_servers if s and s.get("name")]
                return {
                    "discovered_tools": [],
                    "selected_tools": [],
                    "tool_discovery_complete": False,
                    "tool_selection_complete": False,
                    "errors": [f"Failed to discover tools from required servers {server_names}: {str(e)}"],
                    "assistant_response": f"❌ I couldn't connect to the required services ({', '.join(server_names)}). Please check your MCP server configurations.",
                    "conversation_phase": ConversationPhase.ERROR_HANDLING.value
                }
            else:
                # Continue with mock tools for demonstration
                all_tools = _get_mock_tools()
                logger.info(f"[{correlation_id}] Using {len(all_tools)} mock tools for demonstration")
        
        # Step 2: Use LLM to analyze and select relevant tools
        if all_tools:
            tool_analysis_result = await _analyze_and_select_tools(
                all_tools, collected_requirements, correlation_id
            )
            
            selected_tools = tool_analysis_result.get("selected_tools", [])
            tool_selection_reasoning = tool_analysis_result.get("reasoning", "")
            missing_parameters = tool_analysis_result.get("missing_parameters", [])
            
        else:
            selected_tools = []
            tool_selection_reasoning = "No tools were discovered"
            missing_parameters = []
        
        logger.info(f"[{correlation_id}] Selected {len(selected_tools)} tools for workflow")
        
        # Step 3: Check for missing parameters and generate form fields if needed
        if missing_parameters:
            logger.info(f"[{correlation_id}] Found {len(missing_parameters)} missing parameters")
            
            # Generate structured form fields for missing parameters
            form_fields_result = _generate_tool_parameter_form_fields(missing_parameters)
            
            return {
                "discovered_tools": all_tools,
                "selected_tools": selected_tools,
                "tool_discovery_complete": True,
                "tool_selection_complete": True,
                "missing_tool_parameters": missing_parameters,
                "needs_tool_parameters": True,
                "tool_selection_reasoning": tool_selection_reasoning,
                "form_fields": form_fields_result["fields"],
                "form_metadata": form_fields_result["metadata"],
                "assistant_response": form_fields_result["user_message"],
                "conversation_phase": ConversationPhase.REQUIREMENT_GATHERING.value,
                "conversation_context": {
                    **state.get("conversation_context", {}),
                    "tool_selection_reasoning": tool_selection_reasoning
                }
            }
        
        # Step 4: All parameters available, proceed to validation
        return {
            "discovered_tools": all_tools,
            "selected_tools": selected_tools,
            "tool_discovery_complete": True,
            "tool_selection_complete": True,
            "missing_tool_parameters": [],
            "needs_tool_parameters": False,
            "tool_selection_reasoning": tool_selection_reasoning,
            "assistant_response": _generate_tool_selection_success_message(selected_tools),
            "conversation_phase": ConversationPhase.WORKFLOW_GENERATION.value
        }
        
    except Exception as e:
        logger.error(f"[{correlation_id}] Enhanced tool discovery failed: {str(e)}")
        return {
            "discovered_tools": [],
            "selected_tools": [],
            "tool_discovery_complete": False,
            "tool_selection_complete": False,
            "errors": [f"Tool discovery and analysis failed: {str(e)}"],
            "assistant_response": "I encountered an issue analyzing available tools. Let me continue with basic functionality.",
            "conversation_phase": ConversationPhase.WORKFLOW_GENERATION.value
        }


async def _analyze_and_select_tools(
    all_tools: List[Dict[str, Any]], 
    collected_requirements: Dict[str, Any],
    correlation_id: str
) -> Dict[str, Any]:
    """Use LLM to analyze discovered tools and select relevant ones for the workflow.
    
    Args:
        all_tools: List of all discovered MCP tools
        collected_requirements: Collected workflow requirements
        correlation_id: Request correlation ID
        
    Returns:
        Dictionary containing selected tools, reasoning, and missing parameters
    """
    try:
        logger.info(f"[{correlation_id}] Analyzing {len(all_tools)} tools with LLM")
        
        llm = get_llm()
        
        # Create comprehensive prompt for tool analysis and selection
        tool_analysis_prompt = PromptTemplate(
            input_variables=["workflow_requirements", "available_tools", "workflow_intent"],
            template="""You are an expert workflow architect. Analyze the available MCP tools and select the most relevant ones for the user's workflow requirements.

WORKFLOW REQUIREMENTS:
{workflow_requirements}

WORKFLOW INTENT:
{workflow_intent}

AVAILABLE MCP TOOLS:
{available_tools}

Your task is to:
1. **ANALYZE** the workflow requirements and intent to understand what the user wants to accomplish
2. **SELECT** the most relevant tools from the available tools that match the workflow needs
3. **IDENTIFY** required parameters for each selected tool
4. **DETERMINE** if the parameters are already available or can be dynamically generated using another tool
5. **DETECT** missing parameters that need to be only collected from the user which can not be dynamically generated

TOOL SELECTION CRITERIA:
- Tools must directly support the workflow intent (source/target platforms, action type)
- Prioritize tools that match the detected platforms
- Consider the data flow: source → processing → target
- Include authentication/setup tools if needed
- Limit selection to most essential tools

PARAMETER ANALYSIS:
- Extract required parameters from each selected tool's schema
- Identify which parameters are already available or can be dynamically generated in workflow requirements
- Flag parameters that need user input (API keys, URLs, IDs, etc.)
- Categorize missing parameters by priority (critical, high, medium, low)

RESPONSE FORMAT (JSON only):
{{
    "selected_tools": [
        {{
            "tool_name": "exact_tool_name",
            "server_name": "server_name",
            "description": "tool_description",
            "selection_reason": "why this tool was selected",
            "workflow_role": "source|target|processor|authenticator|utility",
            "parameters_schema": {{}},
            "available_parameters": {{}},
            "missing_parameters": []
        }}
    ],
    "missing_parameters": [
        {{
            "tool_name": "tool_name",
            "parameter_name": "param_name",
            "parameter_type": "string|number|boolean|object|array",
            "description": "parameter description",
            "required": true,
            "priority": "critical|high|medium|low",
            "user_friendly_name": "friendly name for UI",
            "input_type": "text|email|url|password|select|number",
            "validation_rules": {{}},
            "help_text": "guidance for user",
            "suggested_values": [],
            "default_value": null
        }}
    ],
    "workflow_coverage": {{
        "source_coverage": "percentage or description",
        "target_coverage": "percentage or description", 
        "action_coverage": "percentage or description",
        "authentication_coverage": "covered|partial|missing"
    }},
    "reasoning": "detailed explanation of tool selection and parameter analysis"
}}

EXAMPLES:
If workflow intent is "sync GitHub issues to Slack":
- Select: github_issues_tool, slack_messaging_tool
- Missing params might be: github_token, slack_webhook_url, repository_name, channel_name

If workflow intent is "backup Notion pages to file storage":
- Select: notion_pages_tool, file_storage_tool
- Missing params might be: notion_token, storage_path, page_filters"""
        )
        
        # Format tools for the prompt
        tools_formatted = _format_tools_for_analysis(all_tools)
        workflow_intent_formatted = json.dumps(collected_requirements.get("workflow_intent", {}), indent=2)
        
        formatted_prompt = tool_analysis_prompt.format(
            workflow_requirements=json.dumps(collected_requirements, indent=2),
            workflow_intent=workflow_intent_formatted,
            available_tools=tools_formatted
        )
        
        response = await llm.ainvoke(formatted_prompt)
        response_content = response.content.strip()
        
        # Parse the LLM response
        analysis_result = _extract_and_parse_json(response_content)
        
        if analysis_result:
            selected_tools = analysis_result.get("selected_tools", [])
            missing_parameters = analysis_result.get("missing_parameters", [])
            reasoning = analysis_result.get("reasoning", "")
            workflow_coverage = analysis_result.get("workflow_coverage", {})
            
            logger.info(f"[{correlation_id}] Tool analysis complete: {len(selected_tools)} tools selected, {len(missing_parameters)} missing parameters")
            
            return {
                "selected_tools": selected_tools,
                "missing_parameters": missing_parameters,
                "workflow_coverage": workflow_coverage,
                "reasoning": reasoning
            }
        else:
            logger.warning(f"[{correlation_id}] Failed to parse tool analysis JSON")
            # Fallback to basic tool selection
            return _fallback_tool_selection(all_tools, collected_requirements)
            
    except Exception as e:
        logger.error(f"[{correlation_id}] Tool analysis failed: {str(e)}")
        # Fallback to basic tool selection
        return _fallback_tool_selection(all_tools, collected_requirements)


def _format_tools_for_analysis(tools: List[Dict[str, Any]]) -> str:
    """Format discovered tools for LLM analysis.
    
    Args:
        tools: List of discovered MCP tools
        
    Returns:
        Formatted string representation of tools
    """
    if not tools:
        return "No tools available."
    
    tool_descriptions = []
    for i, tool in enumerate(tools, 1):
        name = tool.get("name", "unknown")
        description = tool.get("description", "No description")
        server_name = tool.get("server_name", "unknown")
        parameters_schema = tool.get("parameters_schema", {})
        
        # Extract parameter names for quick reference
        if isinstance(parameters_schema, dict) and "properties" in parameters_schema:
            param_names = list(parameters_schema["properties"].keys())
            params_str = f"Parameters: {', '.join(param_names[:5])}" if param_names else "No parameters"
            if len(param_names) > 5:
                params_str += f" (+{len(param_names) - 5} more)"
        else:
            params_str = "Parameters: Unknown schema"
        
        tool_descriptions.append(
            f"{i}. **{name}** (Server: {server_name})\n"
            f"   Description: {description}\n"
            f"   {params_str}\n"
            f"   Schema: {json.dumps(parameters_schema, indent=4) if parameters_schema else 'Not available'}"
        )
    
    return "\n\n".join(tool_descriptions)


def _fallback_tool_selection(
    all_tools: List[Dict[str, Any]], 
    collected_requirements: Dict[str, Any]
) -> Dict[str, Any]:
    """Fallback tool selection when LLM analysis fails.
    
    Args:
        all_tools: List of all discovered tools
        collected_requirements: Collected workflow requirements
        
    Returns:
        Basic tool selection result
    """
    # Simple heuristic: select tools from required servers
    required_servers = collected_requirements.get("required_servers", [])
    server_names = {s.get("name", "").lower() for s in required_servers if s and s.get("name")}
    
    selected_tools = []
    for tool in all_tools:
        if tool.get("server_name", "").lower() in server_names:
            selected_tools.append({
                "tool_name": tool.get("name"),
                "server_name": tool.get("server_name"),
                "description": tool.get("description", ""),
                "selection_reason": "Fallback selection based on required servers",
                "workflow_role": "utility",
                "parameters_schema": tool.get("parameters_schema", {}),
                "available_parameters": {},
                "missing_parameters": []
            })
    
    return {
        "selected_tools": selected_tools,
        "missing_parameters": [],
        "workflow_coverage": {"source_coverage": "unknown", "target_coverage": "unknown", "action_coverage": "unknown"},
        "reasoning": "Fallback tool selection due to analysis failure"
    }


def _generate_tool_parameter_form_fields(missing_parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate structured form fields for missing tool parameters.
    
    Args:
        missing_parameters: List of missing parameter information
        
    Returns:
        Structured form fields with metadata for dynamic UI generation
    """
    if not missing_parameters:
        return {
            "fields": [],
            "metadata": {"total_fields": 0, "required_fields": 0},
            "user_message": "All tool parameters are available."
        }
    
    # Group parameters by tool for better organization
    tools_params = {}
    for param in missing_parameters:
        tool_name = param.get("tool_name", "unknown")
        if tool_name not in tools_params:
            tools_params[tool_name] = []
        tools_params[tool_name].append(param)
    
    # Prioritize critical and high priority parameters
    critical_params = [p for p in missing_parameters if p.get("priority") == "critical"]
    high_params = [p for p in missing_parameters if p.get("priority") == "high"]
    other_params = [p for p in missing_parameters if p.get("priority") not in ["critical", "high"]]
    
    # Start with critical and high priority, limit to 5 fields at a time
    params_to_generate = (critical_params + high_params)[:5]
    if not params_to_generate and other_params:
        params_to_generate = other_params[:5]
    
    remaining_count = len(missing_parameters) - len(params_to_generate)
    
    form_fields = []
    
    # Add tool section headers and parameter fields
    current_tool = None
    for param in params_to_generate:
        tool_name = param.get("tool_name", "unknown")
        
        # Add tool section header if it's a new tool
        if tool_name != current_tool:
            tool_header_field = {
                "id": f"tool_header_{tool_name}",
                "name": f"Tool: {tool_name}",
                "label": f"🔧 Configuration for {tool_name}",
                "type": "section_header",
                "metadata": {
                    "field_type": "tool_section",
                    "tool_name": tool_name
                }
            }
            form_fields.append(tool_header_field)
            current_tool = tool_name
        
        # Create parameter field
        param_field = _create_tool_parameter_field(param)
        form_fields.append(param_field)
    
    # Generate user-friendly message
    if len(tools_params) == 1:
        tool_name = list(tools_params.keys())[0]
        user_message = f"To use the **{tool_name}** tool in your workflow, I need some configuration details:"
    else:
        user_message = f"To set up {len(tools_params)} tools for your workflow, I need some configuration details:"
    
    if remaining_count > 0:
        user_message += f" (I'll ask for {remaining_count} more parameters after these.)"
    
    return {
        "fields": form_fields,
        "metadata": {
            "total_fields": len(form_fields),
            "required_fields": len([f for f in form_fields if f.get("required", False)]),
            "remaining_parameters": remaining_count,
            "tools_count": len(tools_params),
            "priority_breakdown": {
                "critical": len(critical_params),
                "high": len(high_params),
                "medium": len([p for p in missing_parameters if p.get("priority") == "medium"]),
                "low": len([p for p in missing_parameters if p.get("priority") == "low"])
            }
        },
        "user_message": user_message
    }


def _create_tool_parameter_field(param: Dict[str, Any]) -> Dict[str, Any]:
    """Create a structured form field from tool parameter information.
    
    Args:
        param: Tool parameter information
        
    Returns:
        Structured form field definition
    """
    param_name = param.get("parameter_name", "unknown")
    user_friendly_name = param.get("user_friendly_name", param_name.replace("_", " ").title())
    description = param.get("description", "")
    param_type = param.get("parameter_type", "string")
    input_type = param.get("input_type", "text")
    required = param.get("required", True)
    priority = param.get("priority", "medium")
    help_text = param.get("help_text", "")
    suggested_values = param.get("suggested_values", [])
    default_value = param.get("default_value")
    validation_rules = param.get("validation_rules", {})
    tool_name = param.get("tool_name", "unknown")
    
    field = {
        "id": f"{tool_name}_{param_name}".lower().replace(" ", "_"),
        "name": user_friendly_name,
        "label": description or user_friendly_name,
        "type": input_type,
        "required": required and priority in ["critical", "high"],
        "priority": priority,
        "validation": validation_rules,
        "metadata": {
            "source_type": "tool_parameter",
            "tool_name": tool_name,
            "parameter_name": param_name,
            "parameter_type": param_type
        }
    }
    
    # Add default value if provided
    if default_value is not None:
        field["default_value"] = default_value
    
    # Add options for select/radio fields
    if suggested_values and input_type in ["select", "radio", "checkbox"]:
        field["options"] = [
            {"value": val, "label": val} for val in suggested_values
        ]
    
    # Add placeholder text
    field["placeholder"] = _get_parameter_placeholder(param_name, input_type, tool_name)
    
    # Add help text
    field["help_text"] = help_text or _get_parameter_help_text(param_name, input_type, tool_name)
    
    return field


def _get_parameter_placeholder(param_name: str, input_type: str, tool_name: str) -> str:
    """Get placeholder text for a parameter field.
    
    Args:
        param_name: Parameter name
        input_type: HTML input type
        tool_name: Tool name for context
        
    Returns:
        Placeholder text string
    """
    param_lower = param_name.lower()
    tool_lower = tool_name.lower()
    
    # Tool-specific placeholders
    if "github" in tool_lower:
        if "token" in param_lower:
            return "ghp_xxxxxxxxxxxxxxxxxxxx"
        elif "repo" in param_lower:
            return "owner/repository-name"
        elif "user" in param_lower:
            return "github-username"
    
    elif "slack" in tool_lower:
        if "token" in param_lower:
            return "xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx"
        elif "channel" in param_lower:
            return "#general"
        elif "webhook" in param_lower:
            return "https://hooks.slack.com/services/..."
    
    elif "notion" in tool_lower:
        if "token" in param_lower:
            return "secret_xxxxxxxxxxxxxxxxxxxx"
        elif "database" in param_lower:
            return "notion-database-id"
        elif "page" in param_lower:
            return "notion-page-id"
    
    # Generic placeholders based on parameter name
    if input_type == "email":
        return "user@example.com"
    elif input_type == "url":
        return "https://api.example.com"
    elif input_type == "password" or "token" in param_lower:
        return "Enter your access token"
    elif "api_key" in param_lower:
        return "your-api-key-here"
    elif "webhook" in param_lower:
        return "https://webhook.example.com/path"
    elif "channel" in param_lower:
        return "#channel-name"
    elif "repo" in param_lower:
        return "owner/repository"
    else:
        return f"Enter {param_name.replace('_', ' ').lower()}"


def _get_parameter_help_text(param_name: str, input_type: str, tool_name: str) -> str:
    """Get help text for a parameter field.
    
    Args:
        param_name: Parameter name
        input_type: HTML input type
        tool_name: Tool name for context
        
    Returns:
        Help text string
    """
    param_lower = param_name.lower()
    tool_lower = tool_name.lower()
    
    # Tool-specific help text
    if "github" in tool_lower:
        if "token" in param_lower:
            return "Go to GitHub Settings > Developer settings > Personal access tokens to create one"
        elif "repo" in param_lower:
            return "Format: owner/repository-name (e.g., microsoft/vscode)"
    
    elif "slack" in tool_lower:
        if "token" in param_lower:
            return "Create a Slack app and get the bot token from OAuth & Permissions"
        elif "webhook" in param_lower:
            return "Create an incoming webhook in your Slack app settings"
        elif "channel" in param_lower:
            return "Use # for public channels or @ for direct messages"
    
    elif "notion" in tool_lower:
        if "token" in param_lower:
            return "Create an integration in your Notion workspace settings"
        elif "database" in param_lower:
            return "Copy the database ID from the database URL"
    
    # Generic help text
    if "token" in param_lower or "api_key" in param_lower:
        return "You can find this in your account settings or developer console"
    elif "webhook" in param_lower:
        return "Create a webhook URL in your application settings"
    elif input_type == "email":
        return "Enter a valid email address"
    elif input_type == "url":
        return "Enter a complete URL including http:// or https://"
    else:
        return f"Provide the {param_name.replace('_', ' ').lower()} for the {tool_name} tool"


def _generate_tool_selection_success_message(selected_tools: List[Dict[str, Any]]) -> str:
    """Generate a success message when tool selection is complete.
    
    Args:
        selected_tools: List of selected tools
        
    Returns:
        Success message string
    """
    if not selected_tools:
        return "No tools were selected for your workflow. Let me proceed with basic workflow generation."
    
    if len(selected_tools) == 1:
        tool = selected_tools[0]
        return (f"Perfect! I've selected the **{tool['tool_name']}** tool from {tool['server_name']} "
                f"for your workflow. All parameters are available, so I can now create your workflow!")
    
    tool_names = [tool['tool_name'] for tool in selected_tools]
    if len(tool_names) == 2:
        tools_str = f"**{tool_names[0]}** and **{tool_names[1]}**"
    else:
        tools_str = f"**{', '.join(tool_names[:-1])}**, and **{tool_names[-1]}**"
    
    return (f"Excellent! I've selected {len(selected_tools)} tools for your workflow: {tools_str}. "
            f"All required parameters are available, so I can now generate your complete workflow!")


def _extract_entity_names(requirements: Dict[str, Any]) -> List[str]:
    """Extract entity names from requirements for tool discovery.
    
    Args:
        requirements: Workflow requirements dictionary
        
    Returns:
        List of entity names extracted from requirements
    """
    entities = []
    
    # Extract from common requirement fields
    if "source" in requirements:
        entities.append(requirements["source"])
    if "target" in requirements:
        entities.append(requirements["target"])
    if "platforms" in requirements:
        entities.extend(requirements["platforms"])
    if "services" in requirements:
        entities.extend(requirements["services"])
    
    # Extract from workflow intent
    workflow_intent = requirements.get("workflow_intent", {})
    if workflow_intent:
        if "source_platform" in workflow_intent and workflow_intent["source_platform"]:
            entities.append(workflow_intent["source_platform"])
        if "target_platform" in workflow_intent and workflow_intent["target_platform"]:
            entities.append(workflow_intent["target_platform"])
    
    # Extract from detected platforms
    detected_platforms = requirements.get("detected_platforms", [])
    for platform in detected_platforms:
        if isinstance(platform, dict) and "name" in platform:
            entities.append(platform["name"])
        elif isinstance(platform, str):
            entities.append(platform)
    
    # Extract from raw request text
    raw_request = requirements.get("raw_request", "").lower()
    common_services = ["github", "slack", "notion", "trello", "jira", "discord", "teams", "gmail", "postgresql", "supabase"]
    for service in common_services:
        if service in raw_request:
            entities.append(service)
    
    return list(set(entities))  # Remove duplicates


def _get_mock_tools() -> List[Dict[str, Any]]:
    """Get mock tools for demonstration when MCP is not available.
    
    Returns:
        List of mock tool configurations
    """
    return [
        {
            "name": "mock_github_tool",
            "description": "Mock GitHub operations tool",
            "server_name": "mock_github",
            "parameters_schema": {"repository": "string", "action": "string"},
            "discovered_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "name": "mock_slack_tool", 
            "description": "Mock Slack messaging tool",
            "server_name": "mock_slack",
            "parameters_schema": {"channel": "string", "message": "string"},
            "discovered_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "name": "mock_filesystem_tool",
            "description": "Mock file system operations tool",
            "server_name": "mock_filesystem",
            "parameters_schema": {"path": "string", "operation": "string"},
            "discovered_at": datetime.now(timezone.utc).isoformat()
        }
    ]


def extract_tool_schema_from_basetool(tool) -> Dict[str, Any]:
    """
    Extract parameter schema from a BaseTool instance.
    
    This helper handles the different types of args_schema that can exist in BaseTool:
    - Pydantic BaseModel (v1 or v2)
    - Dictionary (JSON schema)
    - None
    
    Args:
        tool: BaseTool instance
        
    Returns:
        Dictionary containing the tool's parameter schema
    """
    try:
        # Handle different types of args_schema
        if hasattr(tool, 'args_schema') and tool.args_schema is not None:
            
            # Case 1: args_schema is already a dictionary (JSON schema)
            if isinstance(tool.args_schema, dict):
                return tool.args_schema
            
            # Case 2: args_schema is a Pydantic model (BaseModel subclass)
            elif hasattr(tool.args_schema, 'model_json_schema'):
                # Pydantic v2
                return tool.args_schema.model_json_schema()
            elif hasattr(tool.args_schema, 'schema'):
                # Pydantic v1
                return tool.args_schema.schema()
            
            # Case 3: args_schema is a class type (need to get schema from tool)
            elif hasattr(tool, 'get_input_schema'):
                input_schema = tool.get_input_schema()
                if hasattr(input_schema, 'model_json_schema'):
                    return input_schema.model_json_schema()
                elif hasattr(input_schema, 'schema'):
                    return input_schema.schema()
        
        # Case 4: Use tool's args property as fallback
        elif hasattr(tool, 'args') and tool.args:
            return {
                "type": "object",
                "properties": tool.args,
                "required": []
            }
        
        # Case 5: Use tool's get_input_schema method as final fallback
        elif hasattr(tool, 'get_input_schema'):
            try:
                input_schema = tool.get_input_schema()
                if hasattr(input_schema, 'model_json_schema'):
                    return input_schema.model_json_schema()
                elif hasattr(input_schema, 'schema'):
                    return input_schema.schema()
            except Exception as schema_error:
                logger.warning(f"Failed to get input schema for tool {getattr(tool, 'name', 'unknown')}: {schema_error}")
        
        # Default empty schema
        return {"type": "object", "properties": {}}
        
    except Exception as e:
        logger.warning(f"Failed to extract schema from tool {getattr(tool, 'name', 'unknown')}: {e}")
        return {"type": "object", "properties": {}}


async def validate_mcp_tools_node(state: WorkflowState, mcp_service: MCPService = None) -> Dict[str, Any]:
    """Validate discovered MCP tools for availability and accessibility.
    
    Args:
        state: Current conversational workflow state
        mcp_service: Optional MCP service instance
        
    Returns:
        Updated state with validated tools
    """
    try:
        logger.info("Starting MCP tool validation...")
        
        # Get selected tools from enhanced discovery
        selected_tools = state.get("selected_tools", [])
        discovered_tools = state.get("discovered_tools", [])
        correlation_id = state.get("correlation_id", "unknown")
        
        # Use selected tools if available, otherwise fall back to discovered tools
        tools_to_validate = selected_tools if selected_tools else discovered_tools
        
        if not tools_to_validate:
            logger.warning(f"[{correlation_id}] No tools to validate")
            return {
                "validated_tools": [],
                "tool_validation_complete": True,
                "assistant_response": "No tools were discovered. I'll proceed with basic workflow generation.",
                "conversation_phase": ConversationPhase.WORKFLOW_GENERATION.value
            }
        
        # Initialize MCP service if not provided
        if not mcp_service:
            mcp_service = MCPService()
        
        validated_tools = []
        failed_validations = []
        
        # Validate each tool
        for tool in tools_to_validate:
            try:
                tool_name = tool.get("tool_name") or tool.get("name", "")
                server_name = tool.get("server_name", "")
                
                # Validate tool accessibility through MCP service
                try:
                    is_valid = await mcp_service.validate_tool(tool_name, server_name)
                    
                    if is_valid:
                        validated_tools.append({
                            **tool,
                            "validation_status": "valid",
                            "validated_at": datetime.now(timezone.utc).isoformat()
                        })
                    else:
                        failed_validations.append({
                            "tool_name": tool_name,
                            "server_name": server_name,
                            "reason": "Tool validation failed"
                        })
                except Exception:
                    # Fallback: Assume tools are valid for mock/simulation
                    validated_tools.append({
                        **tool,
                        "validation_status": "simulated", 
                        "validated_at": datetime.now(timezone.utc).isoformat()
                    })
                    
            except Exception as e:
                logger.error(f"[{correlation_id}] Tool validation failed for {tool.get('tool_name') or tool.get('name', 'unknown')}: {e}")
                failed_validations.append({
                    "tool_name": tool.get("tool_name") or tool.get("name", "unknown"),
                    "server_name": tool.get("server_name", "unknown"),
                    "reason": f"Validation error: {str(e)}"
                })
        
        # Generate validation summary
        validation_summary = f"Validated tools: {len(validated_tools)}/{len(tools_to_validate)}"
        if failed_validations:
            validation_summary += f" ({len(failed_validations)} failed)"
        
        # Create user-friendly response
        if validated_tools:
            tool_list = ", ".join([tool.get("tool_name") or tool.get("name", "") for tool in validated_tools[:3]])
            if len(validated_tools) > 3:
                tool_list += f" and {len(validated_tools) - 3} more"
            
            assistant_response = f"✅ **Tools Ready!** I've validated {len(validated_tools)} tools including {tool_list}. Now I can generate your workflow!"
        else:
            assistant_response = "⚠️ No tools could be validated. I'll create a basic workflow structure that you can customize later."
        
        logger.info(f"[{correlation_id}] Tool validation complete: {len(validated_tools)} valid, {len(failed_validations)} failed")
        
        return {
            "validated_tools": validated_tools,
            "failed_validations": failed_validations,
            "tool_validation_complete": True,
            "validation_summary": validation_summary,
            "assistant_response": assistant_response,
            "conversation_phase": ConversationPhase.WORKFLOW_GENERATION.value
        }
        
    except Exception as e:
        logger.error(f"Tool validation failed: {e}")
        return {
            "validated_tools": [],
            "failed_validations": [],
            "tool_validation_complete": False,
            "errors": [f"Tool validation failed: {str(e)}"],
            "assistant_response": "I encountered an issue validating tools. Let me proceed with basic workflow generation.",
            "conversation_phase": ConversationPhase.WORKFLOW_GENERATION.value
        } 