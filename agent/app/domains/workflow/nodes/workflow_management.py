"""Workflow Management Nodes for Conversational Workflows

This module handles workflow review, modification, and approval processes.
"""

import json
from typing import Dict, Any
from datetime import datetime

from langchain_core.prompts import PromptTemplate

from ..graphs.states import WorkflowState, ConversationPhase
from ....shared.exceptions import ValidationException
from ....shared import get_logger
from ....ai.llm import get_llm

logger = get_logger(__name__)


async def workflow_review_node(state: WorkflowState) -> Dict[str, Any]:
    """Generate a human-readable review of the workflow for user approval.
    
    Args:
        state: Current conversational workflow state
        
    Returns:
        Updated state with workflow review response
    """
    try:
        workflow_draft = state.get("workflow_draft", {})
        collected_requirements = state.get("collected_requirements", {})
        
        if not workflow_draft:
            return {"errors": ["No workflow to review"]}
        
        # Initialize LLM
        llm = get_llm()
        
        # Build review prompt
        review_prompt = PromptTemplate(
            input_variables=["workflow", "requirements"],
            template="""
You are presenting a generated workflow to a user for review and approval.

User Requirements: {requirements}
Generated Workflow: {workflow}

Create a clear, friendly explanation of the workflow that includes:
1. A brief summary of what the workflow will do
2. The main steps in simple terms
3. Which tools/services will be used
4. Any important details about timing or conditions
5. Ask if they'd like any changes or if they're ready to run it

Make it conversational and easy to understand, avoiding technical jargon.
End with something like "Does this look good to you, or would you like me to modify anything?"
"""
        )
        
        formatted_prompt = review_prompt.format(
            requirements=json.dumps(collected_requirements, indent=2),
            workflow=json.dumps(workflow_draft, indent=2)
        )
        
        response = await llm.ainvoke(formatted_prompt)
        
        review_response = response.content.strip()
        
        logger.info("Generated workflow review")
        
        return {
            "assistant_response": review_response,
            "conversation_phase": ConversationPhase.WORKFLOW_REVIEW.value
        }
        
    except Exception as e:
        logger.error(f"Workflow review generation failed: {str(e)}")
        fallback_response = ("I've created a workflow based on your requirements. "
                           "Would you like me to show you the details and run it?")
        return {
            "assistant_response": fallback_response,
            "errors": [f"Workflow review failed: {str(e)}"]
        }


async def handle_modification_node(state: WorkflowState) -> Dict[str, Any]:
    """Handle user requests to modify the workflow.
    
    Args:
        state: Current conversational workflow state
        
    Returns:
        Updated state with modified workflow
    """
    try:
        current_message = state.get("current_message", "")
        workflow_draft = state.get("workflow_draft", {})
        workflow_modifications = state.get("workflow_modifications", [])
        
        if not workflow_draft:
            return {"errors": ["No workflow to modify"]}
        
        # Initialize LLM
        llm = get_llm()
        
        # Build modification prompt
        modification_prompt = PromptTemplate(
            input_variables=["user_request", "current_workflow", "previous_modifications"],
            template="""
            The user wants to modify their workflow. Analyze their request and apply the changes.

            User Modification Request: {user_request}
            Current Workflow: {current_workflow}
            Previous Modifications: {previous_modifications}

            Update the workflow according to the user's request. Common modifications include:
            - Changing parameters (channel names, repositories, etc.)
            - Adding or removing steps
            - Changing the order of operations
            - Modifying conditions or triggers

            Response format (JSON only):
            {{
                "modified_workflow": {{...workflow_object...}},
                "changes_made": ["description of change 1", "description of change 2"],
                "explanation": "friendly explanation of what was changed"
            }}
            """
        )
        
        formatted_prompt = modification_prompt.format(
            user_request=current_message,
            current_workflow=json.dumps(workflow_draft, indent=2),
            previous_modifications=json.dumps(workflow_modifications, indent=2)
        )
        
        response = await llm.ainvoke(formatted_prompt)
        
        try:
            modification_result = json.loads(response.content)
            
            modified_workflow = modification_result.get("modified_workflow", workflow_draft)
            changes_made = modification_result.get("changes_made", [])
            explanation = modification_result.get("explanation", "I've updated your workflow.")
            
            # Record the modification
            modification_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_request": current_message,
                "changes": changes_made
            }
            
            logger.info(f"Workflow modified: {len(changes_made)} changes made")
            
            return {
                "workflow_draft": modified_workflow,
                "workflow_modifications": [modification_record],
                "assistant_response": explanation,
                "conversation_phase": ConversationPhase.WORKFLOW_REVIEW.value
            }
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse modification result")
            return {
                "assistant_response": "I understand you want to make changes. Could you be more specific about what you'd like me to modify?",
                "errors": ["Failed to parse modification instructions"]
            }
            
    except Exception as e:
        logger.error(f"Workflow modification failed: {str(e)}")
        return {
            "assistant_response": "I had trouble understanding your modification request. Could you try rephrasing it?",
            "errors": [f"Modification handling failed: {str(e)}"]
        }
