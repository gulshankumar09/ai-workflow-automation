"""User Interaction Nodes for Conversational Workflows

This module handles user interaction including clarifying questions and input requests.
"""

import json
from typing import Dict, Any, List

from langchain_core.prompts import PromptTemplate

from ..graphs.states import WorkflowState, ConversationPhase
from ....shared.exceptions import ValidationException
from ....shared import get_logger
from ....ai.llm import get_llm

logger = get_logger(__name__)


async def human_interaction_node(state: WorkflowState) -> Dict[str, Any]:
    """Generate clarifying questions for user input.

    This node generates questions to gather more information from the user
    and updates the state to indicate that clarification is needed.
    """
    try:
        missing_parameters = state.get("missing_parameters", [])
        collected_requirements = state.get("collected_requirements", {})
        pending_clarifications = state.get("pending_clarifications", [])

        if not missing_parameters and not pending_clarifications:
            return {"needs_clarification": False}

        all_clarifications = list(set(missing_parameters + pending_clarifications))

        clarification_prompt = PromptTemplate(
            input_variables=["requirements", "clarifications"],
            template="""You are a helpful assistant responsible for gathering information to build a workflow.
            Your goal is to ask the user for the information you need in a clear, friendly, and conversational manner.

            Here's what I know so far about the user's request:
            {requirements}

            To proceed, I need some more information. Please ask the user for the following details:
            {clarifications}

            Based on the above, generate a response to the user. Follow these guidelines:
            1.  Start by acknowledging their request and showing you've understood what they want to do.
            2.  Politely state that you need a few more details.
            3.  Present the questions clearly, for example, as a numbered list. Phrase them as natural questions, not just keywords.
            4.  Conclude by letting them know you'll be ready to create the workflow once you have the information.

            Example of a good response:
            "Yes, I can help you with a workflow to sync a GitHub repo to a Slack channel. For this, I need some information:
            1. Which GitHub repository do you want to sync issues from?
            2. Which Slack channel should the issue updates be posted to?

            Once I have these details, I can generate the workflow for you."

            Now, generate the response for the user."""
        )

        formatted_prompt = clarification_prompt.format(
            requirements=json.dumps(collected_requirements, indent=2),
            clarifications=", ".join(all_clarifications)
        )

        llm = get_llm()
        response = await llm.ainvoke(formatted_prompt)
        clarification_response = response.content.strip()

        logger.info(f"Generated clarification question: {clarification_response}")

        # Instead of interrupting, update state to indicate clarification is needed
        # The graph will route back to handle the next user input
        return {
            "assistant_response": clarification_response,
            "pending_clarifications": all_clarifications,
            "needs_clarification": True,
            "waiting_for_user_input": True,
            "conversation_phase": ConversationPhase.REQUIREMENT_GATHERING.value
        }

    except Exception as e:
        logger.error(f"Clarification generation failed: {str(e)}")
        fallback_response = ("I need a bit more information to create your workflow. "
                           "Could you provide more details about what you'd like to accomplish?")
        return {
            "assistant_response": fallback_response,
            "errors": [f"Clarification generation failed: {str(e)}"]
        }


async def request_user_input_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Pauses the workflow to request input from the user.

    This node signals an interruption, allowing the application to collect
    user input before proceeding.
    Returns:
        An empty dictionary, as this node's purpose is to halt execution.
    """
    logger.info("Pausing workflow to request user input.")
    # The graph interrupt will be handled by the application layer
    # which will see the pending_questions in the state.
    return {"waiting_for_user_input": True}


def _generate_clarification_questions(missing_info: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Legacy function for backward compatibility. 
    
    Note: This is now handled by _generate_structured_form_fields in requirements_analysis.py
    
    Args:
        missing_info: List of missing parameter information
        
    Returns:
        Simple message format for backward compatibility
    """
    # Import here to avoid circular imports
    from .requirements_analysis import _generate_structured_form_fields
    
    form_fields = _generate_structured_form_fields(missing_info)
    return {"message": form_fields["user_message"]} 