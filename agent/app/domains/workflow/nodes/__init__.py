"""Conversational Workflow Nodes

This package contains all the conversational workflow nodes organized by functionality.
Each module contains specific nodes and their helper functions:

- intent_classification: User intent classification
- requirements_analysis: Requirements analysis and platform detection  
- user_interaction: Human interaction and clarification
- workflow_management: Workflow review and modification
- routing: Conversation phase routing
- routing_helpers: Additional routing logic functions
- greeting_nodes: Greeting generation
- mcp_integration_nodes: MCP tool discovery and validation
- workflow_generation_nodes: Workflow generation with MCP tools
- workflow_execution_nodes: Workflow execution with MCP integration
- question_handling_nodes: General question handling
- shared_helpers: Common utility functions
"""

# Import all node functions
from .intent_classification import (
    classify_intent_node,
    _extract_and_parse_json,
    _classify_intent_by_keywords
)

from .requirements_analysis import (
    analyze_requirements_node,
    _format_available_mcp_servers,
    _validate_required_servers,
    _generate_structured_form_fields,
    _create_form_field,
    _determine_input_type,
    _get_field_validation,
    _get_field_placeholder,
    _get_field_help_text
)

from .user_interaction import (
    human_interaction_node,
    request_user_input_node,
    _generate_clarification_questions
)

from .workflow_management import (
    workflow_review_node,
    handle_modification_node
)

from .routing_nodes import (
    route_after_intent_classification,
    route_after_requirements_analysis,
    route_after_mcp_tool_discovery,
    route_conversation_phase
)

from .greeting_nodes import (
    generate_greeting_node
)

from .mcp_integration_nodes import (
    discover_mcp_tools_node,
    validate_mcp_tools_node,
    _extract_entity_names,
    _get_mock_tools
)

from .workflow_generation_nodes import (
    generate_workflow_node,
    _generate_tool_parameters,
    _determine_step_type,
    _generate_expected_output,
    _build_workflow_description,
    _get_step_type_emoji
)

from .workflow_execution_nodes import (
    execute_workflow_node,
    _check_mcp_availability,
    _simulate_step_execution,
    _generate_execution_summary
)

from .question_handling_nodes import (
    handle_question_node,
    _generate_help_response,
    _generate_status_response,
    _generate_technical_response,
    _generate_troubleshooting_response,
    _generate_pricing_response,
    _generate_examples_response,
    _generate_security_response,
    _generate_default_response
)

from .shared_helpers import (
    _get_available_mcp_servers_list,
    _format_available_tools,
    _validate_mcp_server_availability
)

# Export all main node functions
__all__ = [
    # Main node functions
    "classify_intent_node",
    "analyze_requirements_node",
    "human_interaction_node",
    "request_user_input_node",
    "workflow_review_node",
    "handle_modification_node",
    "route_conversation_phase",
    "generate_greeting_node",
    "discover_mcp_tools_node",
    "validate_mcp_tools_node",
    "generate_workflow_node",
    "execute_workflow_node",
    "handle_question_node",
    
    # Routing functions
    "route_after_intent_classification",
    "route_after_requirements_analysis",
    "route_after_mcp_tool_discovery",
    
    # Helper functions (exported for backward compatibility and testing)
    "_extract_and_parse_json",
    "_classify_intent_by_keywords",
    "_format_available_mcp_servers",
    "_validate_required_servers",
    "_generate_structured_form_fields",
    "_create_form_field",
    "_determine_input_type",
    "_get_field_validation",
    "_get_field_placeholder",
    "_get_field_help_text",
    "_generate_clarification_questions",
    "_get_available_mcp_servers_list",
    "_format_available_tools",
    "_validate_mcp_server_availability",
    "_extract_entity_names",
    "_get_mock_tools",
    "_generate_workflow_steps_with_mcp",
    "_generate_tool_parameters",
    "_determine_step_type",
    "_generate_expected_output",
    "_build_workflow_description",
    "_get_step_type_emoji",
    "_check_mcp_availability",
    "_simulate_step_execution",
    "_generate_execution_summary",
    "_generate_help_response",
    "_generate_status_response",
    "_generate_technical_response",
    "_generate_troubleshooting_response",
    "_generate_pricing_response",
    "_generate_examples_response",
    "_generate_security_response",
    "_generate_default_response"
] 