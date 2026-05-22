"""State Definitions for Workflow LangGraphs

Defines TypedDict states used across workflow generation and validation graphs.
These states maintain immutable data flow and support LangGraph's serialization requirements.
"""

import operator
from typing import TypedDict, List, Dict, Any, Annotated, Optional, NotRequired
from enum import Enum


class ConversationPhase(Enum):
    """Conversation phases for multi-turn workflow generation"""
    GREETING = "greeting"
    INTENT_DISCOVERY = "intent_discovery" 
    REQUIREMENT_GATHERING = "requirement_gathering"
    TOOL_DISCOVERY = "tool_discovery"
    WORKFLOW_GENERATION = "workflow_generation"
    WORKFLOW_REVIEW = "workflow_review"
    WORKFLOW_MODIFICATION = "workflow_modification"
    WORKFLOW_EXECUTION = "workflow_execution"
    EXECUTION_MONITORING = "execution_monitoring"
    ERROR_HANDLING = "error_handling"
    COMPLETED = "completed"


class UserIntent(Enum):
    """Types of user intents in conversation"""
    GREETING = "greeting"
    WORKFLOW_REQUEST = "workflow_request"
    PROVIDE_INFO = "provide_info"
    MODIFY_WORKFLOW = "modify_workflow"
    APPROVE_EXECUTION = "approve_execution"
    ASK_QUESTION = "ask_question"
    CLARIFICATION = "clarification"


class WorkflowState(TypedDict):
    """State for conversational workflow generation graph.
    
    This state tracks multi-turn conversations for building workflows
    with human feedback and clarification loops.
    """
    # Session and user context
    session_id: str
    user_id: str
    correlation_id: str
    
    # Conversation management
    conversation_phase: str  # ConversationPhase enum value as string
    current_intent: str  # UserIntent enum value as string
    message_history: Annotated[List[Dict[str, Any]], operator.add]
    
    # Current message processing
    current_message: str
    user_input: str
    assistant_response: str
    
    # Workflow building context
    collected_requirements: Dict[str, Any]
    missing_parameters: Annotated[List[Dict[str, Any]], operator.add]
    pending_clarifications: Annotated[List[str], operator.add]
    pending_questions: Annotated[List[Dict[str, Any]], operator.add]
    
    # Workflow state
    workflow_draft: Dict[str, Any]
    workflow_modifications: Annotated[List[Dict[str, Any]], operator.add]
    final_workflow: Dict[str, Any]

    # Form fields
    form_fields: Dict[str, Any]
    form_metadata: Dict[str, Any]
    
    # Tool discovery and validation
    discovered_tools: Annotated[List[Dict[str, Any]], operator.add]
    available_tools: List[Dict[str, Any]]
    selected_tools: List[Dict[str, Any]]
    available_servers: List[Dict[str, Any]]
    tool_parameters: Dict[str, Any]
    
    # Execution state
    execution_approved: bool
    execution_results: Dict[str, Any]
    execution_progress: Dict[str, Any]
    
    # Context and metadata
    user_context: Dict[str, Any]
    conversation_context: Dict[str, Any]
    session_metadata: Dict[str, Any]
    
    # Error handling
    errors: Annotated[List[str], operator.add]
    warnings: NotRequired[List[str]]
    
    # Control flags
    needs_clarification: NotRequired[bool]
    needs_user_input: NotRequired[bool]
    can_proceed: NotRequired[bool]
    waiting_for_user_input: NotRequired[bool]
    should_generate_workflow: bool
    should_execute: bool
    is_complete: bool
    
    # Processing metadata
    created_at: str
    updated_at: str
    retry_count: int
