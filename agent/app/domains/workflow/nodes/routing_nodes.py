"""Routing Helper Functions for Conversational Workflows

This module contains routing logic functions used by the workflow graph.
"""

from typing import Dict, Any

from ..graphs.states import WorkflowState, ConversationPhase, UserIntent
from ....shared import get_logger

logger = get_logger(__name__)


def route_after_intent_classification(state: WorkflowState) -> str:
    """Route conversation based on the classified user intent.
    
    Args:
        state: Current conversational workflow state
        
    Returns:
        Next node name to execute
    """
    try:
        # If we were waiting for user input, clear the flag
        if state.get("waiting_for_user_input"):
            state["waiting_for_user_input"] = False
            
            # If we have pending clarifications, go back to analyze requirements
            if state.get("pending_clarifications"):
                return "analyze_requirements"
            
        intent = state.get("current_intent")
        logger.debug(f"Routing based on intent: {intent}")

        if intent in [UserIntent.WORKFLOW_REQUEST.value, UserIntent.PROVIDE_INFO.value, UserIntent.CLARIFICATION.value]:
            return "analyze_requirements"
        if intent == UserIntent.GREETING.value:
            return "generate_greeting"
        if intent == UserIntent.MODIFY_WORKFLOW.value:
            return "handle_modification"
        if intent == UserIntent.APPROVE_EXECUTION.value:
            return "execute_workflow"

        return "handle_question"
        
    except Exception as e:
        logger.error(f"Intent routing failed: {str(e)}")
        return "handle_question"  # Fallback


def route_after_requirements_analysis(state: WorkflowState) -> str:
    """Route conversation after analyzing requirements.
    
    Args:
        state: Current conversational workflow state
        
    Returns:
        Next node name to execute
    """
    try:
        needs_clarification = state.get("needs_clarification", False)
        can_proceed = state.get("can_proceed", False)
        needs_user_input = state.get("needs_user_input", False)
        setup_required = state.get("setup_required", False)
        custom_servers_needed = state.get("custom_servers_needed", False)
        correlation_id = state.get("correlation_id", "unknown")
        
        logger.debug(
            f"[{correlation_id}] Routing after requirements analysis. "
            f"Needs clarification: {needs_clarification}, "
            f"Can proceed: {can_proceed}, "
            f"Needs user input: {needs_user_input}, "
            f"Setup required: {setup_required}, "
            f"Custom servers needed: {custom_servers_needed}"
        )
        
        # Priority order: custom servers > setup > clarification > proceed
        if custom_servers_needed or setup_required or needs_clarification or needs_user_input:
            return "request_user_input"
        
        if can_proceed:
            # Check if we have discovered tools already
            if not state.get("discovered_tools"):
                return "discover_mcp_tools"
            else:
                return "generate_workflow"  
    
        # Fallback if state is unclear
        return "handle_question"
        
    except Exception as e:
        logger.error(f"Requirements routing failed: {str(e)}")
        return "handle_question"  # Fallback


def route_after_mcp_tool_discovery(state: WorkflowState) -> str:
    """Route conversation after MCP tool discovery and analysis.
    
    Args:
        state: Current conversational workflow state
        
    Returns:
        Next node name to execute
    """
    try:
        tool_discovery_complete = state.get("tool_discovery_complete", False)
        tool_selection_complete = state.get("tool_selection_complete", False)
        needs_tool_parameters = state.get("needs_tool_parameters", False)
        missing_tool_parameters = state.get("missing_tool_parameters", [])
        errors = state.get("errors", [])
        correlation_id = state.get("correlation_id", "unknown")
        
        logger.debug(
            f"[{correlation_id}] Routing after MCP tool discovery. "
            f"Discovery complete: {tool_discovery_complete}, "
            f"Selection complete: {tool_selection_complete}, "
            f"Needs parameters: {needs_tool_parameters}, "
            f"Missing parameters count: {len(missing_tool_parameters)}, "
            f"Errors: {len(errors)}"
        )
        
        # Check for critical errors first
        if errors:
            logger.warning(f"[{correlation_id}] Errors detected in tool discovery, routing to error handling")
            return "handle_question"
        
        # Check if tool parameters are needed
        if needs_tool_parameters and missing_tool_parameters:
            logger.info(f"[{correlation_id}] Tool parameters needed, routing to user input")
            return "request_user_input"
        
        # Check if tool discovery was successful and complete
        if tool_discovery_complete and tool_selection_complete:
            logger.info(f"[{correlation_id}] Tool discovery and selection complete, proceeding to workflow generation")
            return "generate_workflow"
        
        # Check if only discovery is complete but selection is not
        if tool_discovery_complete and not tool_selection_complete:
            logger.info(f"[{correlation_id}] Tool discovery complete but selection incomplete, proceeding to workflow generation")
            return "generate_workflow"
        
        # If discovery is not complete, there might be an issue
        if not tool_discovery_complete:
            logger.warning(f"[{correlation_id}] Tool discovery incomplete, routing to error handling")
            return "handle_question"
        
        # Default fallback
        logger.warning(f"[{correlation_id}] No clear routing path from tool discovery, using fallback")
        return "generate_workflow"
        
    except Exception as e:
        logger.error(f"[{state.get('correlation_id', 'unknown')}] MCP tool discovery routing failed: {str(e)}")
        return "handle_question"  # Fallback
    

async def route_conversation_phase(state: WorkflowState) -> str:
    """Route to next conversation phase based on current state.
    
    Args:
        state: Current conversational workflow state
        
    Returns:
        Next node name to execute
    """
    current_intent = state.get("current_intent", "")
    conversation_phase = state.get("conversation_phase", ConversationPhase.GREETING.value)
    needs_clarification = state.get("needs_clarification", False)
    can_proceed = state.get("can_proceed", False)
    
    logger.info(f"Routing conversation: intent={current_intent}, phase={conversation_phase}, "
               f"needs_clarification={needs_clarification}, can_proceed={can_proceed}")
    
    # Handle different intents
    if current_intent == UserIntent.GREETING.value:
        return "generate_greeting"
    elif current_intent == UserIntent.WORKFLOW_REQUEST.value:
        if conversation_phase == ConversationPhase.GREETING.value:
            return "analyze_requirements"
        elif needs_clarification:
            return "human_interaction"
        elif can_proceed:
            return "generate_workflow"
    elif current_intent == UserIntent.PROVIDE_INFO.value:
        return "analyze_requirements"
    elif current_intent == UserIntent.MODIFY_WORKFLOW.value:
        return "handle_modification"
    elif current_intent == UserIntent.APPROVE_EXECUTION.value:
        return "execute_workflow"
    elif current_intent == UserIntent.ASK_QUESTION.value:
        return "handle_question"
    
    # Default flow based on phase
    if conversation_phase == ConversationPhase.GREETING.value:
        return "generate_greeting"
    elif conversation_phase == ConversationPhase.REQUIREMENT_GATHERING.value:
        if needs_clarification:
            return "human_interaction"
        elif can_proceed:
            return "generate_workflow"
    elif conversation_phase == ConversationPhase.WORKFLOW_REVIEW.value:
        return "workflow_review"
    
    logger.warning(f"No specific route found for current state, using fallback")
    return "handle_question"  # Fallback 