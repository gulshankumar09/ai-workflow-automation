"""Conversational Workflow Service

Manages conversational workflow generation sessions with state persistence,
session management, and integration with the existing workflow infrastructure.
"""

from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime
import json
from app.domains.workflow.graphs.states import ConversationPhase, UserIntent
from app.shared.exceptions import (
    ValidationException, 
    NotFoundException, 
    WorkflowGenerationError
)
from app.infrastructure.database.providers.factory import DatabaseProviderFactory
from app.infrastructure.cache.factory import CacheProviderFactory
from app.shared.dependency_injection import get_dependency_container
from app.application.user_service import UserService
from app.domains.workflow.graphs.graph import WorkflowGraph
from app.shared import get_logger

logger = get_logger(__name__)


class ConversationalWorkflowService:
    """Service for managing workflow generation sessions.
    
    This service provides:
    - Session state management with persistence
    - Conversational workflow orchestration
    - Integration with existing workflow infrastructure
    - Real-time streaming responses
    """

    def __init__(self, dependency_container=None):
        """Initialize the conversational workflow service.
        
        Args:
            dependency_container: Optional dependency injection container
        """
        self.dependency_container = dependency_container or get_dependency_container()
        
        # Initialize database and cache providers
        self.db_provider = DatabaseProviderFactory.create_provider()
        self.cache_provider = CacheProviderFactory.create_provider()
        
        # # Initialize the conversational workflow graph
        # self.conversational_graph = ConversationalWorkflowGraph()
        
        # Session cache settings
        self.session_cache_ttl = 3600  # 1 hour default TTL
        self.session_cache_prefix = "conv_workflow_session"

        # Use the unified workflow generation graph
        self.workflow_generator = WorkflowGraph()
        
        # Initialize user service for context
        self.user_service = UserService()

    async def process_conversational_message(
        self,
        message: str,
        session_id: str,
        user_id: str,
        correlation_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a conversational message with session state management.
        
        Args:
            message: User's message content
            session_id: Chat session identifier
            user_id: User identifier
            correlation_id: Request correlation ID
            
        Yields:
            Stream of conversation updates and assistant responses
        """
        try:
            logger.info(f"[{correlation_id}] [CONV_SERVICE] Starting message processing for session {session_id}")
            logger.debug(f"[{correlation_id}] [CONV_SERVICE] Message: {message}")
            logger.debug(f"[{correlation_id}] [CONV_SERVICE] User ID: {user_id}")
            
            # Get existing session state for debugging
            existing_state = await self._get_session_state(session_id)
            logger.debug(f"[{correlation_id}] [CONV_SERVICE] Existing session state: {existing_state}")
            
            # Validate inputs
            if not message.strip():
                raise ValidationException(
                    message="Message content cannot be empty",
                    correlation_id=correlation_id
                )
            
            if not session_id:
                raise ValidationException(
                    message="Session ID is required",
                    correlation_id=correlation_id
                )
                
            if not user_id:
                raise ValidationException(
                    message="User ID is required",
                    correlation_id=correlation_id
                )
            
            # Get existing session state or initialize new one
            existing_state = await self._get_session_state(session_id)
            
            # Initialize session state if it doesn't exist or ensure user_id is set
            if not existing_state:
                existing_state = await self._initialize_session_state(session_id, user_id)
            elif not existing_state.get("user_id"):
                # Ensure user_id is set in existing state
                existing_state["user_id"] = user_id
                await self._update_session_state(session_id, {"user_id": user_id})

            # Get user context and available tools
            # user_context = await self.user_service.get_user_context(user_id, correlation_id)
            available_servers = await self.user_service.get_user_available_servers(user_id)
            
            # Delegate to the unified workflow generation graph
            async for conversation_event in self.workflow_generator.stream_workflow_response(
                message=message,
                session_id=session_id,
                user_id=user_id,
                correlation_id=correlation_id,
                existing_state=existing_state,
                available_servers=available_servers
            ):
                
                # with open("workflow_events_processed", "a") as f:
                #         f.write("--------------------------------\n")
                #         f.write("--------------------------------\n")
                #         f.write("--------------------------------\n")
                #         f.write(str(conversation_event) + "\n")

                # Store updated state after each significant update
                if conversation_event.get("type") == "assistant":
                    output = conversation_event.get("output", {})
                    if isinstance(output, dict):
                        # Ensure user_id is always in the output
                        output["user_id"] = user_id
                        await self._update_session_state(session_id, output)
                
                # Yield the event to the client
                yield conversation_event
                
                # Store final state on completion
                # if conversation_event.get("type") == "complete":
                #     final_state = conversation_event.get("final_state", {})
                #     # Ensure user_id is always in the final state
                #     final_state["user_id"] = user_id
                #     await self._store_session_state(session_id, final_state)

        except ValidationException as e:
            logger.warning(f"Validation error in conversational message: {e.message}")
            yield {
                "type": "conversation_error",
                "error": e.message,
                "error_code": e.code,
                "session_id": session_id,
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in conversational message processing: {str(e)}")
            yield {
                "type": "conversation_error", 
                "error": "An unexpected error occurred during conversation processing",
                "session_id": session_id,
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat()
            }

    async def get_conversation_history(
        self,
        session_id: str,
        user_id: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Get conversation history for a session.
        
        Args:
            session_id: Chat session identifier
            user_id: User identifier
            correlation_id: Request correlation ID
            
        Returns:
            Conversation history and current state
        """
        try:
            logger.info(f"Retrieving conversation history for session {session_id}")
            
            # Get session state
            session_state = await self._get_session_state(session_id)
            
            if not session_state:
                raise NotFoundException(
                    message=f"Conversation session not found: {session_id}",
                    correlation_id=correlation_id
                )
            
            # Extract conversation history and metadata
            message_history = session_state.get("message_history", [])
            conversation_phase = session_state.get("conversation_phase", ConversationPhase.GREETING.value)
            collected_requirements = session_state.get("collected_requirements", {})
            workflow_draft = session_state.get("workflow_draft", {})
            
            return {
                "session_id": session_id,
                "user_id": user_id,
                "conversation_phase": conversation_phase,
                "message_history": message_history,
                "collected_requirements": collected_requirements,
                "workflow_draft": workflow_draft,
                "message_count": len(message_history),
                "created_at": session_state.get("created_at"),
                "updated_at": session_state.get("updated_at"),
                "correlation_id": correlation_id
            }
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            raise WorkflowGenerationError(
                message="Failed to retrieve conversation history",
                error_code="HISTORY_RETRIEVAL_ERROR",
                correlation_id=correlation_id
            )

    async def reset_conversation_session(
        self,
        session_id: str,
        user_id: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Reset a conversation session to start fresh.
        
        Args:
            session_id: Chat session identifier
            user_id: User identifier
            correlation_id: Request correlation ID
            
        Returns:
            Confirmation of session reset
        """
        try:
            logger.info(f"Resetting conversation session {session_id}")
            
            # Clear session state from cache
            await self._clear_session_state(session_id)
            
            # Archive conversation in database if it exists
            await self._archive_conversation_session(session_id, user_id)
            
            return {
                "session_id": session_id,
                "status": "reset",
                "message": "Conversation session has been reset",
                "timestamp": datetime.utcnow().isoformat(),
                "correlation_id": correlation_id
            }
            
        except Exception as e:
            logger.error(f"Error resetting conversation session: {str(e)}")
            raise WorkflowGenerationError(
                message="Failed to reset conversation session",
                error_code="SESSION_RESET_ERROR",
                correlation_id=correlation_id
            )

    async def get_session_summary(
        self,
        session_id: str,
        user_id: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Get a summary of the conversation session.
        
        Args:
            session_id: Chat session identifier
            user_id: User identifier
            correlation_id: Request correlation ID
            
        Returns:
            Session summary with key metrics and status
        """
        try:
            session_state = await self._get_session_state(session_id)
            
            if not session_state:
                raise NotFoundException(
                    message=f"Session not found: {session_id}",
                    correlation_id=correlation_id
                )
            
            message_history = session_state.get("message_history", [])
            conversation_phase = session_state.get("conversation_phase", "")
            collected_requirements = session_state.get("collected_requirements", {})
            workflow_draft = session_state.get("workflow_draft", {})
            
            # Calculate summary metrics
            user_messages = [msg for msg in message_history if msg.get("role") == "user"]
            assistant_messages = [msg for msg in message_history if msg.get("role") == "assistant"]
            
            requirements_count = len([k for k, v in collected_requirements.items() if v])
            workflow_steps = len(workflow_draft.get("steps", [])) if workflow_draft else 0
            
            return {
                "session_id": session_id,
                "conversation_phase": conversation_phase,
                "progress": {
                    "message_count": len(message_history),
                    "user_messages": len(user_messages),
                    "assistant_responses": len(assistant_messages),
                    "requirements_collected": requirements_count,
                    "workflow_steps_generated": workflow_steps
                },
                "status": {
                    "has_requirements": bool(collected_requirements),
                    "has_workflow": bool(workflow_draft),
                    "needs_clarification": session_state.get("needs_clarification", False),
                    "can_proceed": session_state.get("can_proceed", False)
                },
                "timestamps": {
                    "created_at": session_state.get("created_at"),
                    "updated_at": session_state.get("updated_at")
                },
                "correlation_id": correlation_id
            }
            
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"Error getting session summary: {str(e)}")
            raise WorkflowGenerationError(
                message="Failed to get session summary",
                error_code="SESSION_SUMMARY_ERROR",
                correlation_id=correlation_id
            )

    # Private helper methods

    async def _get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation session state from cache or database."""
        try:
            # Try cache first
            cache_key = f"{self.session_cache_prefix}:{session_id}"
            try:
                cached_state = await self.cache_provider.get(cache_key)
                
                if cached_state:
                    if isinstance(cached_state, str):
                        return json.loads(cached_state)
                    elif isinstance(cached_state, dict):
                        return cached_state
                    else:
                        logger.warning(f"Unexpected cached state type for session {session_id}: {type(cached_state)}")
                        # Continue to database fallback
                        
            except Exception as cache_error:
                logger.warning(f"Cache get operation failed for session {session_id}: {str(cache_error)}")
                # Continue to database fallback
            
            # Fall back to database if cache miss or cache error
            db_state = await self._get_session_from_database(session_id)
            
            # Cache the database result if successful
            if db_state:
                try:
                    await self.cache_provider.set(
                        cache_key, 
                        json.dumps(db_state), 
                        ttl=self.session_cache_ttl
                    )
                except Exception as cache_set_error:
                    logger.warning(f"Failed to cache session state for {session_id}: {str(cache_set_error)}")
                    # Don't fail the entire operation due to cache issues
            
            return db_state
            
        except Exception as e:
            logger.error(f"Error getting session state for {session_id}: {str(e)}")
            return None

    async def _store_session_state(self, session_id: str, state: Dict[str, Any]) -> None:
        """Store conversation session state to cache and database."""
        try:
            # Serialize state data to handle complex objects
            serializable_state = self._make_serializable(state)
            
            # Update cache
            cache_key = f"{self.session_cache_prefix}:{session_id}"
            await self.cache_provider.set(
                cache_key,
                json.dumps(serializable_state),
                ttl=self.session_cache_ttl
            )
            
            # Update database asynchronously
            await self._store_session_to_database(session_id, serializable_state)
            
        except Exception as e:
            logger.error(f"Error storing session state: {str(e)}")

    async def _update_session_state(self, session_id: str, updates: Dict[str, Any]) -> None:
        """Update specific fields in session state."""
        try:
            # Validate updates is a dictionary
            if not isinstance(updates, dict):
                logger.warning(f"Updates must be a dictionary, got {type(updates)}: {updates}")
                return
                
            current_state = await self._get_session_state(session_id) or {}
            
            # Ensure current_state is a dictionary
            if not isinstance(current_state, dict):
                current_state = {}
            
            # Merge updates
            updated_state = {**current_state, **updates}
            updated_state["updated_at"] = datetime.utcnow().isoformat()
            
            # Ensure user_id is preserved (should never be None after initialization)
            if current_state.get("user_id") and not updated_state.get("user_id"):
                updated_state["user_id"] = current_state["user_id"]
                logger.warning(f"Restored user_id {current_state['user_id']} for session {session_id} during update")
            
            await self._store_session_state(session_id, updated_state)
            
        except Exception as e:
            logger.error(f"Error updating session state for {session_id}: {str(e)}")
            raise

    async def _clear_session_state(self, session_id: str) -> None:
        """Clear session state from cache."""
        try:
            cache_key = f"{self.session_cache_prefix}:{session_id}"
            await self.cache_provider.delete(cache_key)
            
        except Exception as e:
            logger.warning(f"Error clearing session state: {str(e)}")

    async def _get_session_from_database(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session state from database."""
        try:
            # Implementation depends on your database schema
            # This is a placeholder for your specific database operations
            
            result = await self.db_provider.select(
                "conversational_sessions", 
                filters={"session_id": session_id}
            )
            
            if result.get("data"):
                # Handle multiple rows by taking the most recent one
                if len(result["data"]) > 1:
                    logger.warning(f"Multiple sessions found for session_id {session_id}, using the most recent")
                    # Sort by updated_at descending and take the first one
                    session_data = sorted(
                        result["data"], 
                        key=lambda x: x.get("updated_at", ""), 
                        reverse=True
                    )[0]
                else:
                    session_data = result["data"][0]
                
                # Extract conversation state and merge with session metadata
                conversation_state = session_data.get("conversation_state", {})
                
                # Ensure conversation_state is a dictionary
                if not isinstance(conversation_state, dict):
                    conversation_state = {}
                
                # Create the full session state
                full_state = {
                    "session_id": session_data.get("session_id"),
                    "user_id": session_data.get("user_id"),
                    "created_at": session_data.get("created_at"),
                    "updated_at": session_data.get("updated_at"),
                    **conversation_state  # Merge the conversation state
                }
                
                return full_state
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting session from database for {session_id}: {str(e)}")
            return None

    async def _store_session_to_database(self, session_id: str, state: Dict[str, Any]) -> None:
        """Store session state to database."""
        try:
            # Ensure user_id is present in the state
            user_id = state.get("user_id")
            if not user_id:
                logger.error(f"Cannot store session {session_id}: user_id is missing from state")
                raise ValidationException(
                    message="User ID is required for session storage",
                    correlation_id=getattr(self, '_correlation_id', None)
                )
            
            session_record = {
                "session_id": session_id,
                "user_id": user_id,
                "conversation_state": state,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Add created_at if it's a new session
            if not state.get("created_at"):
                session_record["created_at"] = datetime.utcnow().isoformat()
            
            # Upsert session record
            await self.db_provider.upsert(
                "conversational_sessions", 
                data=session_record,
                conflict_columns=["session_id"]
            )
            
        except Exception as e:
            logger.error(f"Error storing session to database: {str(e)}")
            # Re-raise the exception to ensure the caller handles it appropriately
            raise

    async def _archive_conversation_session(self, session_id: str, user_id: str) -> None:
        """Archive a conversation session."""
        try:
            # Move to archive table or mark as archived
            self.db_provider.update("conversational_sessions", {
                "archived": True,
                "archived_at": datetime.utcnow().isoformat()},
                filters={"session_id": session_id})
            
        except Exception as e:
            logger.warning(f"Error archiving conversation session: {str(e)}")

    def _make_serializable(self, obj: Any) -> Any:
        """Convert complex objects to JSON-serializable format."""
        if hasattr(obj, '__dict__'):
            # Convert objects with __dict__ to dictionary
            return {k: self._make_serializable(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # Fallback: convert to string representation
            return str(obj)

    async def _initialize_session_state(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """Initialize a new session state with default values."""
        try:
            current_time = datetime.utcnow().isoformat()
            
            initial_state = {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": current_time,
                "updated_at": current_time,
                "message_history": [],
                "conversation_phase": "intent_classification",
                "collected_requirements": {},
                "workflow_draft": {},
                "needs_clarification": False,
                "can_proceed": False
            }
            
            # Store the initial state with duplicate prevention
            try:
                await self._store_session_state(session_id, initial_state)
                logger.info(f"Initialized new session state for session {session_id}, user {user_id}")
                return initial_state
                
            except Exception as e:
                # Check for duplicate key error
                if "duplicate key value violates unique constraint" in str(e):
                    logger.warning(f"Session already exists for user {user_id}, retrieving existing state")
                    existing_state = await self._get_session_state(session_id)
                    if existing_state:
                        return existing_state
                raise
                
        except Exception as e:
            logger.error(f"Error initializing session state: {str(e)}", exc_info=True)
            raise