"""Intent Classification Node for Conversational Workflows

This module handles user intent classification from conversational messages.
"""

import json
import re
from typing import Dict, Any, Optional

from langchain_core.prompts import PromptTemplate

from ..graphs.states import WorkflowState, ConversationPhase, UserIntent
from ....shared.exceptions import ValidationException
from ....shared import get_logger
from ....ai.llm import get_llm

logger = get_logger(__name__)


async def classify_intent_node(state: WorkflowState) -> Dict[str, Any]:
    """Classify user intent from current message.
    
    Args:
        state: Current conversational workflow state
        
    Returns:
        Updated state with classified intent
    """
    try:
        logger.info(f"Classifying intent for state: {state}")

        current_message = state.get("current_message", "").strip()
        conversation_phase = state.get("conversation_phase", ConversationPhase.INTENT_DISCOVERY.value)
        message_history = state.get("message_history", [])
        
        if not current_message:
            return {"errors": ["No message to classify"]}
        
        # Initialize LLM for intent classification
        llm = get_llm()
        
        # Build context from conversation history
        history_context = ""
        if message_history:
            recent_messages = message_history[-10:]  # Last 10 messages for context
            history_context = "\n".join([
                f"{'User' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('content', '')}"
                for msg in recent_messages
            ])
        
        # Intent classification prompt with better JSON formatting
        intent_prompt = PromptTemplate(
            input_variables=["message", "phase", "history"],
            template="""You are an intent classifier for conversational workflow generation. 
Analyze the user's message and classify their intent.

Current Conversation Phase: {phase}
Recent Conversation History:
{history}

Current User Message: {message}

Classify the intent as one of:
- greeting: User is greeting or introducing themselves
- workflow_request: User wants to create a new workflow or automation
- provide_info: User is providing information or clarification
- modify_workflow: User wants to change an existing workflow
- approve_execution: User approves running a workflow
- ask_question: User has questions about workflow or tools
- clarification: User is asking for clarification

IMPORTANT: You must respond with ONLY a valid JSON object. No other text before or after.

{{"intent": "intent_name", "confidence": 0.85, "entities": ["entity1", "entity2"], "reasoning": "brief explanation"}}"""
        )
        
        formatted_prompt = intent_prompt.format(
            message=current_message,
            phase=conversation_phase,
            history=history_context
        )
        
        # Get intent classification
        response = await llm.ainvoke(formatted_prompt)
        
        # Extract and clean response content
        response_content = response.content.strip()
        
        # Try to extract JSON from response if it's wrapped in text
        intent_result = _extract_and_parse_json(response_content)
        
        if intent_result:
            intent = intent_result.get("intent", UserIntent.ASK_QUESTION.value)
            confidence = float(intent_result.get("confidence", 0.5))
            entities = intent_result.get("entities", [])
            reasoning = intent_result.get("reasoning", "")
            
            if intent not in {intent.value for intent in UserIntent}:
                intent = UserIntent.ASK_QUESTION.value
            
            if not (0.0 <= confidence <= 1.0):
                confidence = 0.5
            
            logger.info(f"Intent classified: {intent} (confidence: {confidence})")
            
            return {
                "current_intent": intent,
                "conversation_phase": ConversationPhase.REQUIREMENT_GATHERING.value,
                "conversation_context": {
                    **state.get("conversation_context", {}),
                    "intent_confidence": confidence,
                    "extracted_entities": entities if isinstance(entities, list) else [],
                    "intent_reasoning": reasoning
                }
            }
        else:
            # Fallback to simple keyword-based classification
            logger.warning("Failed to parse intent classification JSON, using keyword-based fallback")
            fallback_intent = _classify_intent_by_keywords(current_message)
            return {
                "current_intent": fallback_intent,
                "conversation_phase": ConversationPhase.REQUIREMENT_GATHERING.value,
                "conversation_context": {
                    **state.get("conversation_context", {}),
                    "intent_confidence": 0.3,  # Lower confidence for fallback
                    "extracted_entities": [],
                    "intent_reasoning": "Keyword-based classification due to JSON parsing failure"
                }
            }
        
    except Exception as e:
        logger.error(f"Intent classification failed: {str(e)}")
        return {
            "errors": [f"Intent classification failed: {str(e)}"],
            "current_intent": UserIntent.ASK_QUESTION.value,
            "conversation_context": {
                **state.get("conversation_context", {}),
                "intent_confidence": 0.1,
                "extracted_entities": [],
                "intent_reasoning": f"Error-based fallback: {str(e)}"
            }
        }


def _extract_and_parse_json(content: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON from response content with multiple strategies.
    
    Args:
        content: Raw response content
        
    Returns:
        Parsed JSON dictionary or None if parsing fails
    """
    if not content:
        return None
    
    # Strategy 1: Try parsing directly
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Look for JSON within code blocks
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    json_match = re.search(json_block_pattern, content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Look for JSON object anywhere in the content
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    json_matches = re.findall(json_pattern, content, re.DOTALL)
    
    for match in json_matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    # Strategy 4: Try to fix common JSON issues
    try:
        # Remove any text before the first {
        start_idx = content.find('{')
        if start_idx != -1:
            # Remove any text after the last }
            end_idx = content.rfind('}')
            if end_idx != -1:
                json_content = content[start_idx:end_idx + 1]
                return json.loads(json_content)
    except (json.JSONDecodeError, IndexError):
        pass
    
    return None


def _classify_intent_by_keywords(message: str) -> str:
    """Fallback keyword-based intent classification.
    
    Args:
        message: User message to classify
        
    Returns:
        Classified intent string
    """
    message_lower = message.lower()
    
    # Create a scoring system for better classification
    scores = {
        "greeting": 0,
        "workflow_request": 0,
        "modify_workflow": 0,
        "approve_execution": 0,
        "ask_question": 0
    }
    
    # Greeting patterns
    greeting_patterns = [
        "hello", "hi ", "hey", "good morning", "good afternoon", "good evening"
    ]
    for pattern in greeting_patterns:
        if pattern in message_lower:
            scores["greeting"] += 2
    
    # Question patterns (strong indicators)
    if "?" in message_lower:
        scores["ask_question"] += 3
    
    question_words = ["how", "what", "why", "when", "where", "who"]
    for word in question_words:
        if f" {word} " in f" {message_lower} ":  # Word boundary check
            scores["ask_question"] += 2
    
    help_patterns = ["can you", "help me", "help"]
    for pattern in help_patterns:
        if pattern in message_lower:
            scores["ask_question"] += 1
    
    # Workflow request patterns
    workflow_patterns = [
        "create", "build", "make", "automate", "workflow", "automation", 
        "connect", "integrate", "want to", "need to"
    ]
    for pattern in workflow_patterns:
        if pattern in message_lower:
            scores["workflow_request"] += 1
    
    # Modification patterns
    modify_patterns = ["change", "modify", "update", "edit", "alter", "fix"]
    for pattern in modify_patterns:
        if pattern in message_lower:
            scores["modify_workflow"] += 2
    
    # Approval patterns
    approval_patterns = ["yes", "approve", "confirm", "proceed", "go ahead", "execute", "run"]
    for pattern in approval_patterns:
        if pattern in message_lower:
            scores["approve_execution"] += 2
    
    # Find the highest scoring intent
    max_score = max(scores.values())
    
    if max_score == 0:
        return "ask_question"  # Default
    
    # Return the intent with the highest score
    for intent, score in scores.items():
        if score == max_score:
            return intent
    
    return "ask_question" 