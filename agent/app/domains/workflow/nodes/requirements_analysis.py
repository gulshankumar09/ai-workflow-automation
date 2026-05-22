"""Requirements Analysis Node for Conversational Workflows

This module handles requirement analysis with platform detection and MCP server identification.
"""

import json
from typing import Dict, Any, List
from datetime import datetime

from langchain_core.prompts import PromptTemplate

from ..graphs.states import WorkflowState, ConversationPhase, UserIntent
from ....shared.exceptions import ValidationException, WorkflowGenerationError
from ....shared import get_logger
from ....ai.llm import get_llm
from .intent_classification import _extract_and_parse_json

logger = get_logger(__name__)


async def analyze_requirements_node(state: WorkflowState) -> Dict[str, Any]:
    """Simplified requirements analysis with platform detection and basic MCP server identification.

    Analyzes user messages to:
    1. Detect platforms mentioned (Slack, GitHub, Notion, etc.)
    2. Extract workflow actions and data types
    3. Identify required MCP servers from available list
    4. Identify missing parameters for workflow completion
    5. Generate structured requirements output

    Args:
        state: Current conversational workflow state

    Returns:
        Updated state with platform mapping, required MCP servers, and missing parameters
    """
    try:
        current_message = state.get("current_message", "")
        current_intent = state.get("current_intent", "")
        collected_requirements = state.get("collected_requirements", {})
        correlation_id = state.get("correlation_id", "unknown")
        available_servers = state.get("available_servers", [])
        conversation_context = state.get("conversation_context", {})
        intent_reasoning = conversation_context.get("intent_reasoning", current_message)

        if current_intent not in [UserIntent.WORKFLOW_REQUEST.value, UserIntent.PROVIDE_INFO.value, UserIntent.CLARIFICATION.value]:
            return {}

        llm = get_llm()

        # Enhanced requirements analysis with server setup validation
        simplified_prompt = PromptTemplate(
            input_variables=["intent", "existing_requirements", "available_servers"],
            template="""You are a workflow requirements analyzer. Extract basic workflow requirements and identify servers based on available MCP servers and existing context.

Analyze the intent to understand their workflow needs and map them to available servers and actions.

User Message: {intent}
Existing Requirements: {existing_requirements}
Available MCP Servers: {available_servers}

PLATFORM MAPPING: Based on the Available MCP Servers list above, identify which servers the user needs:
- Look for platform names mentioned in the user message (slack, notion, github, etc.)
- Match them exactly to the server names from the Available MCP Servers list
- Consider the server descriptions to understand their capabilities
- If existing requirements mention platforms, include those as well

ACTION DETERMINATION: Based on the intent and existing requirements, determine the workflow action:
- Analyze what the user wants to accomplish
- Consider verbs and intentions in their message (sync, create, send, monitor, backup, etc.)
- Look at existing requirements for context about previous workflow intentions
- Choose the most appropriate action type for their use case

EXAMPLES:
Example 1: "I want to sync my GitHub issues to Slack"
- Platforms: github (source), slack (target)
- Action: sync (synchronizing data between platforms)
- Required servers: ["github", "slack"] (if available in server list)

Example 2: "Create notifications in Teams when Notion pages are updated" 
- Platforms: notion (source), teams (target)
- Action: notify (sending alerts based on events)
- Required servers: ["notion", "teams"] (if available in server list)

IMPORTANT: 
- ONLY use server names that exist in the Available MCP Servers list
- Match platforms mentioned in the message to exact server names from the list
- If a platform is mentioned but no corresponding server exists, note it in missing_server

RESPONSE FORMAT (JSON only):
{{
    "workflow_intent": {{
        "source_platform": "server_name_from_list or null",
        "target_platform": "server_name_from_list or null", 
        "action_type": "sync|create|monitor|transform|notify|backup|migrate",
        "data_type": "messages|issues|files|pages|etc",
        "trigger_type": "manual|scheduled|realtime|webhook"
    }},
    "detected_platforms": [
        {{
            "name": "server_name_from_available_list",
            "role": "source|target|both",
            "confidence": 0.95,
            "context": "relevant context from message"
        }}
    ],
    "required_servers": [
        "exact_server_name_from_list1",
        "exact_server_name_from_list2"
    ],
    "extracted_parameters": {{
        "explicit_params": {{}},
        "implicit_params": {{}},
        "user_context_params": {{}}
    }},
    "missing_servers": [
        {{
            "platform_name": "mentioned_platform_name",
            "context": "how platform was mentioned in message",
            "role": "source|target|both",
            "suggested_description": "inferred purpose based on context"
        }}
    ],
    "missing_informations": [
        {{
            "parameter": "param_name",
            "question": "What is the specific value for param_name?",
            "type": "user_input|selection|discovery",
            "suggested_values": [],
            "priority": "high|medium|low"
        }}
    ],
    "reasoning": "Brief explanation of the analysis and requirements"
}}"""
        )

        # Format available MCP servers for the prompt
        servers = available_servers.get("servers", [])
        server_list_formatted = _format_available_mcp_servers(servers)

        formatted_prompt = simplified_prompt.format(
            intent=intent_reasoning,
            existing_requirements=json.dumps(collected_requirements, indent=2),
            available_servers=server_list_formatted
        )

        response = await llm.ainvoke(formatted_prompt)
        response_content = response.content.strip()

        analysis_result = _extract_and_parse_json(response_content)

        if analysis_result:
            # Extract basic workflow components
            workflow_intent = analysis_result.get("workflow_intent", {})
            detected_platforms = analysis_result.get("detected_platforms", [])
            required_servers = analysis_result.get("required_servers", [])
            extracted_parameters = analysis_result.get("extracted_parameters", {})
            missing_servers = analysis_result.get("missing_server", [])
            missing_info = analysis_result.get("missing_information", [])
            can_proceed = analysis_result.get("can_proceed", False)
            reasoning = analysis_result.get("reasoning", "")

            # Validate that required servers are in available list and check setup status
            server_validation_result = _validate_required_servers(
                required_servers, 
                available_servers, 
                correlation_id
            )

            validated_required_servers = server_validation_result["validated_servers"]
            servers_need_setup = server_validation_result["servers_need_setup"]
            setup_required = len(servers_need_setup) > 0
            custom_servers_needed = len(missing_servers) > 0
            can_proceed = len(validated_required_servers) > 0 and not setup_required and not custom_servers_needed

            # Build enhanced requirements structure
            requirements = {
                **collected_requirements,
                "workflow_intent": workflow_intent,
                "detected_platforms": detected_platforms,
                "required_servers": validated_required_servers,
                "servers_need_setup": servers_need_setup,
                "missing_servers": missing_servers,
                "extracted_parameters": extracted_parameters,
                "analysis_reasoning": reasoning,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

            # Check if custom servers are needed first (highest priority)
            if custom_servers_needed:
                custom_server_message = _generate_custom_server_message(missing_servers)
                custom_server_form_fields = _generate_custom_server_form_fields(missing_servers)
                
                return {
                    "collected_requirements": requirements,
                    "missing_parameters": missing_info,
                    "missing_servers": missing_servers,
                    "needs_user_input": True,
                    "can_proceed": False,
                    "custom_servers_needed": True,
                    "setup_required": False,
                    "pending_clarifications": [f"add_server_{server['platform_name']}" for server in missing_servers],
                    "form_fields": custom_server_form_fields["fields"],
                    "form_metadata": custom_server_form_fields["metadata"],
                    "assistant_response": custom_server_message,
                    "conversation_phase": ConversationPhase.REQUIREMENT_GATHERING.value
                }
            # Check if servers need setup second (high priority)
            elif setup_required:
                setup_message = _generate_server_setup_message(servers_need_setup)
                setup_form_fields = _generate_server_setup_form_fields(servers_need_setup)
                
                return {
                    "collected_requirements": requirements,
                    "missing_parameters": missing_info,
                    "missing_servers": missing_servers,
                    "servers_need_setup": servers_need_setup,
                    "needs_user_input": True,
                    "can_proceed": False,
                    "custom_servers_needed": False,
                    "setup_required": True,
                    "pending_clarifications": [f"setup_{server['name']}" for server in servers_need_setup],
                    "form_fields": setup_form_fields["fields"],
                    "form_metadata": setup_form_fields["metadata"],
                    "assistant_response": setup_message,
                    "conversation_phase": ConversationPhase.REQUIREMENT_GATHERING.value
                }
            elif not can_proceed and missing_info:
                # Generate structured form fields for dynamic UI generation
                form_fields = _generate_structured_form_fields(missing_info)

                logger.info(f"Form fields: {form_fields}")
                
                return {
                    "collected_requirements": requirements,
                    "missing_parameters": missing_info,
                    "missing_servers": missing_servers,
                    "needs_clarification": True,
                    "can_proceed": False,
                    "custom_servers_needed": False,
                    "setup_required": False,
                    "pending_clarifications": [item["parameter"] for item in missing_info],
                    "form_fields": form_fields["fields"],
                    "form_metadata": form_fields["metadata"],
                    "assistant_response": form_fields["user_message"],
                    "conversation_phase": ConversationPhase.REQUIREMENT_GATHERING.value
                }
            else:
                return {
                    "collected_requirements": requirements,
                    "missing_parameters": [],
                    "missing_servers": missing_servers,
                    "needs_clarification": False,
                    "can_proceed": True,
                    "custom_servers_needed": False,
                    "setup_required": False,
                    "ready_for_mcp_server_discovery": True,
                    "conversation_phase": ConversationPhase.TOOL_DISCOVERY.value,
                }
        else:
            logger.warning(f"[{correlation_id}] Failed to parse requirements analysis JSON, requesting clarification")
            return {
                "needs_clarification": True,
                "can_proceed": False,
                "assistant_response": ("I had trouble understanding your workflow requirements. "
                                     "Could you please provide more details about what platforms you want to connect "
                                     "and what actions you'd like to automate?"),
                "conversation_phase": ConversationPhase.REQUIREMENT_GATHERING.value
            }

    except Exception as e:
        logger.error(f"Requirements analysis failed: {str(e)}")
        return {
            "errors": [f"Requirements analysis failed: {str(e)}"],
            "conversation_phase": ConversationPhase.ERROR_HANDLING.value
        }


def _format_available_mcp_servers(available_servers: List[Dict[str, Any]]) -> str:
    """Format available MCP servers for prompt context with new server structure."""
    if not available_servers:
        return "No MCP servers available."
    
    # Type checking
    if not isinstance(available_servers, list):
        logger.warning(f"available_servers is not a list, got type: {type(available_servers)}")
        return "No MCP servers available (type error)."
    
    server_descriptions = []
    for i, server in enumerate(available_servers):
        if not isinstance(server, dict):
            logger.warning(f"Server at index {i} is not a dict: {type(server)} - {server}")
            continue
            
        name = server.get('name', 'unknown')
        description = server.get('description', 'No description')
        server_id = server.get('id', 'unknown')
        is_setup = server.get('is_setup', False)
        is_active = server.get('is_active', False)
        status = server.get('status', 'unknown')
        
        # Create server description with setup status
        setup_status = "✅ Ready" if is_setup and is_active else "⚠️ Needs Setup"
        server_descriptions.append(f"- {name} (ID: {server_id}): {description} - Status: {setup_status}")
    
    return "\n".join(server_descriptions) if server_descriptions else "No valid MCP servers available."


def _validate_required_servers(
    required_servers: List[str], 
    available_servers: List[Dict[str, Any]], 
    correlation_id: str
) -> Dict[str, Any]:
    """Validate that required servers exist in available servers list and check setup status.
    
    Args:
        required_servers: List of server names identified as required
        available_servers: List of available MCP server configurations
        correlation_id: Request correlation ID
        
    Returns:
        Dictionary containing validated servers and servers that need setup
    """
    validated_servers = []
    servers_need_setup = []
    
    # Type checking and defensive programming
    available_servers_list = available_servers.get("servers", [])
    if not isinstance(available_servers_list, list):
        logger.error(f"[{correlation_id}] available_servers is not a list, got type: {type(available_servers)}")
        logger.error(f"[{correlation_id}] available_servers value: {available_servers}")
        return {"validated_servers": [], "servers_need_setup": []}
    
    if not isinstance(required_servers, list):
        logger.error(f"[{correlation_id}] required_servers is not a list, got type: {type(required_servers)}")
        return {"validated_servers": [], "servers_need_setup": []}
    
    # Filter out non-dict items and log warnings
    valid_servers = []
    for server in available_servers_list:
        if isinstance(server, dict):
            valid_servers.append(server)
        else:
            logger.warning(f"[{correlation_id}] Item in available_servers is not a dict: {type(server)} - {server}")
    
    for required_server in required_servers:
        server_name_lower = required_server.lower()
        
        # Find matching server in available list
        matching_server = None
        for server in valid_servers:
            if server.get('name', '').lower() == server_name_lower:
                matching_server = server
                break
        
        if matching_server:
            server_id = matching_server.get('id')
            name = matching_server.get('name')
            description = matching_server.get('description', '')
            is_setup = matching_server.get('is_setup', False)
            is_active = matching_server.get('is_active', False)
            status = matching_server.get('status')
            
            validated_server = {
                "id": server_id,
                "name": name,
                "description": description,
                "is_setup": is_setup,
                "is_active": is_active,
                "status": status,
                "validation_status": "available",
                "validation_timestamp": datetime.utcnow().isoformat()
            }
            validated_servers.append(validated_server)
            
            # Check if server needs setup
            if not is_setup or not is_active:
                setup_server = {
                    "id": server_id,
                    "name": name,
                    "description": description,
                    "is_setup": is_setup,
                    "is_active": is_active,
                    "status": status,
                    "required_config": matching_server.get('required_config', {}),
                    "setup_reason": "Server is not properly configured" if not is_setup else "Server is not active"
                }
                servers_need_setup.append(setup_server)
                logger.warning(f"[{correlation_id}] Server '{name}' needs setup: is_setup={is_setup}, is_active={is_active}")
            else:
                logger.debug(f"[{correlation_id}] Server '{name}' is ready to use")
                
        else:
            # Server not found in available list
            missing_server = {
                "name": required_server,
                "validation_status": "not_available",
                "validation_timestamp": datetime.utcnow().isoformat(),
                "validation_note": f"Server '{required_server}' not found in available MCP servers"
            }
            validated_servers.append(missing_server)
            logger.warning(f"[{correlation_id}] Required server not available: {required_server}")
    
    return {
        "validated_servers": validated_servers,
        "servers_need_setup": servers_need_setup
    }


def _generate_structured_form_fields(missing_info: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate structured form fields for dynamic UI generation from missing information.
    
    Args:
        missing_info: List of missing parameter information
        
    Returns:
        Structured form fields with metadata for dynamic UI generation
    """
    if not missing_info:
        return {
            "fields": [],
            "metadata": {"total_fields": 0, "required_fields": 0},
            "user_message": "No additional information needed."
        }
    
    # Prioritize fields by priority level
    high_priority = [item for item in missing_info if item.get("priority") == "high"]
    medium_priority = [item for item in missing_info if item.get("priority") == "medium"]
    low_priority = [item for item in missing_info if item.get("priority") == "low"]
    
    # Start with high priority fields, limit to 5 fields at a time
    fields_to_generate = (high_priority or medium_priority or low_priority)[:5]
    remaining_count = len(missing_info) - len(fields_to_generate)
    
    form_fields = []
    
    for item in fields_to_generate:
        field = _create_form_field(item)
        form_fields.append(field)
    
    # Generate user-friendly message
    if len(fields_to_generate) == 1:
        user_message = "To create your workflow, I need one more piece of information:"
    elif remaining_count > 0:
        user_message = f"I need some information to create your workflow. Let's start with these {len(fields_to_generate)} details:"
    else:
        user_message = f"To create your workflow, I need {len(fields_to_generate)} more details:"
    
    if remaining_count > 0:
        user_message += f" (I'll ask about {remaining_count} more details after these.)"
    
    return {
        "fields": form_fields,
        "metadata": {
            "total_fields": len(fields_to_generate),
            "required_fields": len([f for f in form_fields if f.get("required", False)]),
            "remaining_fields": remaining_count,
            "priority_breakdown": {
                "high": len(high_priority),
                "medium": len(medium_priority),
                "low": len(low_priority)
            }
        },
        "user_message": user_message
    }


def _create_form_field(missing_item: Dict[str, Any]) -> Dict[str, Any]:
    """Create a structured form field from missing parameter information.
    
    Args:
        missing_item: Single missing parameter information
        
    Returns:
        Structured form field definition
    """
    parameter = missing_item.get("parameter", "unknown")
    question = missing_item.get("question", "Please provide additional details")
    field_type = missing_item.get("type", "user_input")
    suggested_values = missing_item.get("suggested_values", [])
    priority = missing_item.get("priority", "medium")
    
    # Determine HTML input type based on parameter name and type
    input_type = _determine_input_type(parameter, field_type, suggested_values)
    
    field = {
        "id": parameter.lower().replace(" ", "_"),
        "name": parameter,
        "label": question,
        "type": input_type,
        "required": priority in ["high", "critical"],
        "priority": priority,
        "validation": _get_field_validation(parameter, input_type),
        "metadata": {
            "source_type": field_type,
            "parameter_name": parameter
        }
    }
    
    # Add options for select/radio fields
    if suggested_values and input_type in ["select", "radio", "checkbox"]:
        field["options"] = [
            {"value": val, "label": val} for val in suggested_values
        ]
    
    # Add placeholder text
    field["placeholder"] = _get_field_placeholder(parameter, input_type)
    
    # Add help text
    field["help_text"] = _get_field_help_text(parameter, field_type)
    
    return field


def _determine_input_type(parameter: str, field_type: str, suggested_values: List[str]) -> str:
    """Determine the appropriate HTML input type for a form field.
    
    Args:
        parameter: Parameter name
        field_type: Type of field (user_input, selection, discovery)
        suggested_values: List of suggested values
        
    Returns:
        HTML input type string
    """
    parameter_lower = parameter.lower()
    
    # If there are suggested values, use selection types
    if suggested_values:
        if len(suggested_values) <= 3:
            return "radio"
        elif len(suggested_values) <= 10:
            return "select"
        else:
            return "text"  # Too many options, let user type with autocomplete
    
    # Email detection
    if "email" in parameter_lower or "mail" in parameter_lower:
        return "email"
    
    # URL detection
    if any(keyword in parameter_lower for keyword in ["url", "webhook", "endpoint", "link"]):
        return "url"
    
    # Number detection
    if any(keyword in parameter_lower for keyword in ["port", "number", "count", "limit", "timeout"]):
        return "number"
    
    # Password detection
    if any(keyword in parameter_lower for keyword in ["password", "secret", "key", "token"]):
        return "password"
    
    # Date/Time detection
    if any(keyword in parameter_lower for keyword in ["date", "time", "schedule"]):
        return "datetime-local"
    
    # Boolean detection
    if field_type == "selection" and not suggested_values:
        return "checkbox"
    
    # File detection
    if any(keyword in parameter_lower for keyword in ["file", "path", "document"]):
        return "text"  # Could be enhanced to file input if needed
    
    # Default to text input
    return "text"


def _get_field_validation(parameter: str, input_type: str) -> Dict[str, Any]:
    """Get validation rules for a form field.
    
    Args:
        parameter: Parameter name
        input_type: HTML input type
        
    Returns:
        Validation rules dictionary
    """
    validation = {}
    parameter_lower = parameter.lower()
    
    if input_type == "email":
        validation["pattern"] = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        validation["error_message"] = "Please enter a valid email address"
    
    elif input_type == "url":
        validation["pattern"] = r"^https?:\/\/.+"
        validation["error_message"] = "Please enter a valid URL starting with http:// or https://"
    
    elif input_type == "number":
        if "port" in parameter_lower:
            validation["min"] = 1
            validation["max"] = 65535
        elif "timeout" in parameter_lower:
            validation["min"] = 1
            validation["max"] = 3600
    
    elif input_type == "text":
        if any(keyword in parameter_lower for keyword in ["name", "title"]):
            validation["minLength"] = 1
            validation["maxLength"] = 100
        elif "description" in parameter_lower:
            validation["maxLength"] = 500
        else:
            validation["minLength"] = 1
    
    return validation


def _get_field_placeholder(parameter: str, input_type: str) -> str:
    """Get placeholder text for a form field.
    
    Args:
        parameter: Parameter name
        input_type: HTML input type
        
    Returns:
        Placeholder text string
    """
    parameter_lower = parameter.lower()
    
    if input_type == "email":
        return "user@example.com"
    elif input_type == "url":
        return "https://example.com"
    elif "channel" in parameter_lower:
        return "#general"
    elif "repository" in parameter_lower or "repo" in parameter_lower:
        return "username/repository-name"
    elif "token" in parameter_lower:
        return "Enter your access token"
    elif "webhook" in parameter_lower:
        return "https://hooks.slack.com/services/..."
    else:
        return f"Enter {parameter.lower()}"


def _get_field_help_text(parameter: str, field_type: str) -> str:
    """Get help text for a form field.
    
    Args:
        parameter: Parameter name
        field_type: Type of field
        
    Returns:
        Help text string
    """
    parameter_lower = parameter.lower()
    
    if "token" in parameter_lower:
        return "You can find this in your account settings or developer console"
    elif "webhook" in parameter_lower:
        return "Create a webhook URL in your application settings"
    elif "channel" in parameter_lower:
        return "Include the # symbol for public channels"
    elif "repository" in parameter_lower:
        return "Format: owner/repository-name"
    elif field_type == "discovery":
        return "This will be automatically discovered from your account"
    else:
        return ""


def _generate_server_setup_message(servers_need_setup: List[Dict[str, Any]]) -> str:
    """Generate a conversational message for servers that need setup.
    
    Args:
        servers_need_setup: List of servers that need setup
        
    Returns:
        Conversational message about server setup
    """
    if not servers_need_setup:
        return ""
    
    if len(servers_need_setup) == 1:
        server = servers_need_setup[0]
        return (f"Great! I found that you need the **{server['name']}** server for your workflow. "
                f"However, it looks like this server needs to be set up first. "
                f"\n\n📋 **{server['name']}**: {server['description']}"
                f"\n\n🔧 To proceed, I'll need you to configure this server. "
                f"Would you like me to guide you through the setup process?")
    else:
        server_names = [server['name'] for server in servers_need_setup]
        if len(server_names) == 2:
            server_list = f"**{server_names[0]}** and **{server_names[1]}**"
        else:
            server_list = f"**{', '.join(server_names[:-1])}**, and **{server_names[-1]}**"
        
        return (f"Perfect! I've identified the servers you'll need for your workflow: {server_list}. "
                f"\n\nHowever, {len(servers_need_setup)} of these servers need to be set up first:"
                f"\n\n" + 
                "\n".join([f"📋 **{server['name']}**: {server['description']}" for server in servers_need_setup]) +
                f"\n\n🔧 To create your workflow, I'll need you to configure these servers. "
                f"Would you like me to guide you through setting them up?")


def _generate_server_setup_form_fields(servers_need_setup: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate form fields for server setup.
    
    Args:
        servers_need_setup: List of servers that need setup
        
    Returns:
        Structured form fields for server setup
    """
    if not servers_need_setup:
        return {
            "fields": [],
            "metadata": {"total_fields": 0, "required_fields": 0},
            "user_message": "No server setup required."
        }
    
    form_fields = []
    
    # Create setup confirmation field
    setup_confirmation_field = {
        "id": "confirm_server_setup",
        "name": "Setup Confirmation",
        "label": f"I want to set up {len(servers_need_setup)} server(s) for my workflow",
        "type": "checkbox",
        "required": True,
        "value": False,
        "validation": {"required": True},
        "metadata": {
            "field_type": "setup_confirmation",
            "servers_count": len(servers_need_setup)
        },
        "help_text": "Check this box to proceed with server setup"
    }
    form_fields.append(setup_confirmation_field)
    
    # Add setup method selection
    setup_method_field = {
        "id": "setup_method",
        "name": "Setup Method",
        "label": "How would you like to set up the servers?",
        "type": "radio",
        "required": True,
        "options": [
            {"value": "guided", "label": "Guided Setup - Walk me through each step"},
            {"value": "manual", "label": "Manual Setup - I'll configure them myself"},
            {"value": "later", "label": "Setup Later - Save workflow and setup servers later"}
        ],
        "validation": {"required": True},
        "metadata": {
            "field_type": "setup_method"
        },
        "help_text": "Choose your preferred setup approach"
    }
    form_fields.append(setup_method_field)
    
    # Add server details for reference
    for i, server in enumerate(servers_need_setup):
        server_info_field = {
            "id": f"server_info_{server['id']}",
            "name": f"Server Info: {server['name']}",
            "label": f"📋 {server['name']} Details",
            "type": "display",
            "value": {
                "name": server['name'],
                "description": server['description'],
                "setup_reason": server['setup_reason'],
                "required_config": server.get('required_config', {})
            },
            "metadata": {
                "field_type": "server_info",
                "server_id": server['id'],
                "server_name": server['name']
            },
            "help_text": f"Configuration required for {server['name']}"
        }
        form_fields.append(server_info_field)
    
    return {
        "fields": form_fields,
        "metadata": {
            "total_fields": len(form_fields),
            "required_fields": 2,  # confirmation and method selection
            "servers_need_setup": len(servers_need_setup),
            "setup_type": "server_configuration"
        },
        "user_message": f"Please confirm if you'd like to set up {len(servers_need_setup)} server(s) for your workflow."
    }


def _generate_custom_server_message(missing_servers: List[Dict[str, Any]]) -> str:
    """Generate a conversational message for missing servers that need to be added.
    
    Args:
        missing_servers: List of missing server platforms
        
    Returns:
        Conversational message about adding custom servers
    """
    if not missing_servers:
        return ""
    
    if len(missing_servers) == 1:
        server = missing_servers[0]
        return (f"I noticed you mentioned **{server['platform_name']}** in your workflow request, "
                f"but I don't see that server in your available integrations. "
                f"\n\n🔍 **Context**: {server['context']}"
                f"\n\n💡 Would you like me to help you add **{server['platform_name']}** as a custom server? "
                f"I can guide you through setting up the integration so you can use it in your workflows.")
    else:
        platform_names = [server['platform_name'] for server in missing_servers]
        if len(platform_names) == 2:
            platform_list = f"**{platform_names[0]}** and **{platform_names[1]}**"
        else:
            platform_list = f"**{', '.join(platform_names[:-1])}**, and **{platform_names[-1]}**"
        
        return (f"I noticed you mentioned {platform_list} in your workflow request, "
                f"but I don't see these servers in your available integrations. "
                f"\n\n🔍 **Missing Platforms**:"
                f"\n" + 
                "\n".join([f"• **{server['platform_name']}**: {server['context']}" for server in missing_servers]) +
                f"\n\n💡 Would you like me to help you add these {len(missing_servers)} platforms as custom servers? "
                f"I can guide you through setting up the integrations so you can use them in your workflows.")


def _generate_custom_server_form_fields(missing_servers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate form fields for adding custom servers.
    
    Args:
        missing_servers: List of missing server platforms
        
    Returns:
        Structured form fields for custom server addition
    """
    if not missing_servers:
        return {
            "fields": [],
            "metadata": {"total_fields": 0, "required_fields": 0},
            "user_message": "No custom servers needed."
        }
    
    form_fields = []
    
    # Create confirmation field for adding custom servers
    add_servers_confirmation_field = {
        "id": "confirm_add_custom_servers",
        "name": "Add Custom Servers",
        "label": f"Yes, I want to add {len(missing_servers)} custom server(s) to my integrations",
        "type": "checkbox",
        "required": True,
        "value": False,
        "validation": {"required": True},
        "metadata": {
            "field_type": "add_servers_confirmation",
            "servers_count": len(missing_servers)
        },
        "help_text": "Check this box to proceed with adding custom servers"
    }
    form_fields.append(add_servers_confirmation_field)
    
    # Add method selection for server addition
    add_method_field = {
        "id": "add_servers_method",
        "name": "Addition Method",
        "label": "How would you like to add these servers?",
        "type": "radio",
        "required": True,
        "options": [
            {"value": "guided", "label": "Guided Addition - Walk me through each server"},
            {"value": "bulk", "label": "Bulk Addition - Add all servers at once"},
            {"value": "later", "label": "Add Later - Continue without these servers for now"}
        ],
        "validation": {"required": True},
        "metadata": {
            "field_type": "add_servers_method"
        },
        "help_text": "Choose your preferred approach for adding custom servers"
    }
    form_fields.append(add_method_field)
    
    # Add server details for each missing platform
    for i, server in enumerate(missing_servers):
        server_details_field = {
            "id": f"missing_server_{i}",
            "name": f"Custom Server: {server['platform_name']}",
            "label": f"🔧 {server['platform_name']} Server Details",
            "type": "display",
            "value": {
                "platform_name": server['platform_name'],
                "context": server['context'],
                "role": server['role'],
                "suggested_description": server.get('suggested_description', f"Integration for {server['platform_name']} platform")
            },
            "metadata": {
                "field_type": "missing_server_info",
                "platform_name": server['platform_name'],
                "role": server['role']
            },
            "help_text": f"Details about the {server['platform_name']} integration needed for your workflow"
        }
        form_fields.append(server_details_field)
    
    return {
        "fields": form_fields,
        "metadata": {
            "total_fields": len(form_fields),
            "required_fields": 2,  # confirmation and method selection
            "missing_servers_count": len(missing_servers),
            "form_type": "custom_server_addition"
        },
        "user_message": f"Please confirm if you'd like to add {len(missing_servers)} custom server(s) to your available integrations."
    } 