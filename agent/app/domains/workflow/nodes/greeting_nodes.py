"""Greeting Nodes for Conversational Workflows

This module handles greeting generation and initial user interactions.
"""

from typing import Dict, Any

from ..graphs.states import WorkflowState, ConversationPhase
from ....shared import get_logger

logger = get_logger(__name__)


async def generate_greeting_node(state: WorkflowState) -> Dict[str, Any]:
    """Generate a friendly greeting and introduction.
    
    Args:
        state: Current conversational workflow state
        
    Returns:
        Updated state with greeting response
    """
    try:
        user_context = state.get("user_context", {})
        user_name = user_context.get("name", "there")
        
        greeting = f"""Hi {user_name}! 👋 I'm Bili, your AI workflow assistant. I help you create powerful automation workflows that connect your favorite tools and services.

I can help you build workflows to:
🔗 Connect different platforms (GitHub, Slack, Notion, etc.)
⚡ Automate repetitive tasks
📊 Sync data between systems
🚀 Streamline your workflows

What would you like to automate today? Just describe what you have in mind, and I'll help you build it step by step!"""

        return {
            "assistant_response": greeting,
            "conversation_phase": ConversationPhase.INTENT_DISCOVERY.value
        }
        
    except Exception as e:
        logger.error(f"Greeting generation failed: {str(e)}")
        fallback_greeting = "Hi! I'm Bili, your workflow assistant. What would you like to automate today?"
        return {
            "assistant_response": fallback_greeting,
            "conversation_phase": ConversationPhase.INTENT_DISCOVERY.value,
            "errors": [f"Greeting generation failed: {str(e)}"]
        } 