"""
Chat REST API Endpoints for ai-workflow-automation Core Microservice.

This module provides REST API endpoints for chat functionality,
mirroring the gRPC ChatService interface with Auth0 authentication.
"""

import json
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Query, Body, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.shared.logger import get_logger
from app.shared.dependency_injection import get_dependency_container
from app.application.user_service import UserService
from app.application.conversational_workflow_service import ConversationalWorkflowService
from app.shared.exceptions import BaseAppException, NotFoundException, ValidationException
from app.shared.auth import Auth0User, get_current_user, get_current_user_optional, require_user_in_db

logger = get_logger(__name__)


# Request/Response Models

class StartChatSessionRequest(BaseModel):
    """Request model for starting a chat session."""
    session_type: str = Field(default="CHAT", description="Type of session (CHAT, WORKFLOW, etc.)")
    context: Dict[str, Any] = Field(default_factory=dict, description="Initial session context")
    capabilities: List[str] = Field(default_factory=list, description="Requested capabilities")


class StartChatSessionResponse(BaseModel):
    """Response model for starting a chat session."""
    session_id: str = Field(..., description="Unique session identifier")
    status: str = Field(..., description="Session status")
    context: Dict[str, Any] = Field(..., description="Session context")
    available_tools: List[str] = Field(..., description="Available tools for the user")
    message: str = Field(..., description="Success message")


class SendMessageRequest(BaseModel):
    """Request model for sending a message."""
    message: str = Field(..., description="Message content")
    message_type: str = Field(default="USER", description="Type of message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    # Note: streaming is now always enabled for better UX


class ChatMessageResponse(BaseModel):
    """Response model for chat messages."""
    session_id: str = Field(..., description="Session identifier")
    message_id: str = Field(..., description="Message identifier")
    content: str = Field(..., description="Message content")
    message_type: str = Field(..., description="Type of message")
    status: str = Field(..., description="Response status")
    timestamp: datetime = Field(..., description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    is_final: bool = Field(default=False, description="Whether this is the final message chunk")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Tool calls made")


class GetChatHistoryRequest(BaseModel):
    """Request model for getting chat history."""
    session_id: str = Field(..., description="Session identifier")
    limit: int = Field(default=50, le=100, description="Maximum number of messages to return")
    cursor: Optional[str] = Field(None, description="Pagination cursor")
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")


class GetChatHistoryResponse(BaseModel):
    """Response model for chat history."""
    messages: List[Dict[str, Any]] = Field(..., description="Chat messages")
    next_cursor: Optional[str] = Field(None, description="Next pagination cursor")
    has_more: bool = Field(..., description="Whether there are more messages")
    total_count: int = Field(..., description="Total message count")


class EndChatSessionRequest(BaseModel):
    """Request model for ending a chat session."""
    session_id: str = Field(..., description="Session identifier")
    reason: Optional[str] = Field(None, description="Reason for ending session")


class EndChatSessionResponse(BaseModel):
    """Response model for ending a chat session."""
    session_id: str = Field(..., description="Session identifier")
    status: str = Field(..., description="Final session status")
    message: str = Field(..., description="Confirmation message")
    ended_at: datetime = Field(..., description="Session end time")


class GetSessionContextResponse(BaseModel):
    """Response model for session context."""
    session_id: str = Field(..., description="Session identifier")
    status: str = Field(..., description="Session status")
    context: Dict[str, Any] = Field(..., description="Session context")
    active_tools: List[str] = Field(..., description="Currently active tools")
    last_activity: datetime = Field(..., description="Last activity timestamp")


def create_chat_router() -> APIRouter:
    """
    Create FastAPI router for chat endpoints.
    
    Returns:
        APIRouter configured with chat endpoints
    """
    router = APIRouter(prefix="/chat", tags=["chat"])
    
    # In-memory storage for active sessions (replace with proper storage in production)
    active_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def get_dependency_services():
        """Get dependency services."""
        return {
            'user_service': UserService(),
            'conversation_service': ConversationalWorkflowService()
        }

    @router.post("/sessions", 
                 response_model=StartChatSessionResponse,
                 summary="Start Chat Session",
                 description="Start a new chat session for the authenticated user")
    async def start_chat_session(
        request: StartChatSessionRequest,
        current_user: Auth0User = Depends(get_current_user),
        services: Dict = Depends(get_dependency_services)
    ) -> StartChatSessionResponse:
        """Start a new chat session."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Starting chat session for user: {current_user.auth_id}")
            
            # Use authenticated user's ID - prefer database ID if available
            user_id = current_user.db_user_id if current_user.exists_in_db else current_user.auth_id

            # Create session
            session_id = str(uuid4())
            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "auth_user_id": current_user.auth_id,
                "session_type": request.session_type,
                "context": request.context,
                "capabilities": request.capabilities,
                "created_at": datetime.utcnow(),
                "message_history": [],
                "active_tools": [],
                "metrics": {
                    "message_count": 0,
                    "tool_calls_count": 0,
                    "tokens_used": 0
                }
            }
            
            # Store session
            active_sessions[session_id] = session_data
            
            # Get available tools for user
            try:
                if current_user.exists_in_db:
                    available_tools = await services['user_service'].get_user_available_tools(user_id)
                else:
                    available_tools = []  # No tools for users not in database
            except Exception as e:
                logger.warning(f"[{correlation_id}] Could not get user tools: {e}")
                available_tools = []
            
            response = StartChatSessionResponse(
                session_id=session_id,
                status="ACTIVE",
                context=session_data["context"],
                available_tools=available_tools,
                message="Chat session started successfully"
            )

            logger.info(f"[{correlation_id}] Chat session started: {session_id}")
            return response

        except HTTPException:
            raise
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e.message
            )
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred"
            )

    @router.post("/sessions/messages",
                 summary="Send Message",
                 description="Send a message to a chat session and get streaming response")
    async def send_message(
        request: SendMessageRequest,
        session_id: str = Query(..., description="Session identifier"),
        current_user: Auth0User = Depends(get_current_user),
        services: Dict = Depends(get_dependency_services)
    ):
        """Send a message and get response."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Processing message for session: {session_id}")
            
            # Validate session exists
            session = active_sessions.get(session_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Session not found: {session_id}"
                )

            # Verify session ownership
            session_auth_user_id = session.get("auth_user_id", session.get("user_id"))
            user_id = current_user.db_user_id if current_user.exists_in_db else current_user.auth_id
            
            if session_auth_user_id != current_user.auth_id and session.get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only send messages to your own sessions"
                )

            # Validate message
            if not request.message:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Message is required"
                )

            # Create message ID and timestamp
            message_id = str(uuid4())
            timestamp = datetime.utcnow()
            
            # Add user message to history
            user_message = {
                "message_id": message_id,
                "session_id": session_id,
                "content": request.message,
                "message_type": request.message_type,
                "timestamp": timestamp,
                "metadata": request.metadata,
                "user_id": user_id,
                "auth_user_id": current_user.auth_id
            }
            session["message_history"].append(user_message)
            session["metrics"]["message_count"] += 1

            # Always return streaming response for better user experience
            async def generate_response():
                try:
                    # Process message through conversational workflow service
                    conversational_workflow_service = ConversationalWorkflowService()

                    async for conversation_event in conversational_workflow_service.process_conversational_message(
                        message=request.message,
                        session_id=session_id,
                        user_id=user_id,
                        correlation_id=correlation_id
                    ):
                        
                        event_type = conversation_event.get("type", "")
                        response_message_id = str(uuid4())
                        
                        if event_type in ["assistant", "user_input", "thinking"]:
                            # Stream assistant response to client
                            content = json.dumps(conversation_event)
                            conversation_phase = conversation_event.get("conversation_phase", "")
                            
                            logger.info(f"[{correlation_id}] [REST_ENDPOINT] Sending assistant response to client")
                            
                            response = ChatMessageResponse(
                                session_id=session_id,
                                message_id=response_message_id,
                                content=content,
                                message_type="ASSISTANT",
                                status="STREAMING",
                                timestamp=datetime.utcnow(),
                                metadata={
                                    "conversation_phase": conversation_phase,
                                    "correlation_id": correlation_id,
                                    "event_type": event_type
                                },
                                is_final=False,
                                tool_calls=[]
                            )
                            
                            yield response.model_dump_json() + "\n\n"
                            
                            # Update in memory session with assistant response
                            assistant_message = {
                                "message_id": response_message_id,
                                "session_id": session_id,
                                "content": content,  # This is now JSON string
                                "message_type": "ASSISTANT",
                                "timestamp": datetime.utcnow().isoformat(),
                                "metadata": {
                                    "conversation_phase": conversation_phase,
                                    "correlation_id": correlation_id,
                                    "original_event": conversation_event  # Store original dict for reference
                                }
                            }
                            session["message_history"].append(assistant_message)
                            session["metrics"]["message_count"] += 1
                        
                        elif event_type == "error":
                            # Handle conversation errors
                            error_message = conversation_event.get("errors", "An error occurred during conversation processing")
                            logger.error(f"[{correlation_id}] [REST_ENDPOINT] Conversation error: {error_message}")

                            error_response = ChatMessageResponse(
                                session_id=session_id,
                                message_id=response_message_id,
                                content=str(error_message),
                                message_type="ASSISTANT",
                                status="ERROR",
                                timestamp=datetime.utcnow(),
                                metadata={"correlation_id": correlation_id},
                                is_final=True,
                                tool_calls=[]
                            )

                            yield error_response.model_dump_json() + "\n\n"
                            break
                        
                        elif event_type == "complete":
                            # Handle conversation completion
                            final_state = conversation_event.get("final_state", {})
                            
                            # Update session metrics
                            if final_state:
                                session["metrics"]["tokens_used"] += len(request.message)
                                if "workflow_draft" in final_state:
                                    session["last_generated_workflow"] = final_state["workflow_draft"]
                            
                            logger.info(f"[{correlation_id}] Conversational message processing completed")
                            
                            # Send completion event
                            completion_response = ChatMessageResponse(
                                session_id=session_id,
                                message_id=response_message_id,
                                content="",
                                message_type="ASSISTANT",
                                status="COMPLETED",
                                timestamp=datetime.utcnow(),
                                metadata={"correlation_id": correlation_id, "final_state": final_state},
                                is_final=True,
                                tool_calls=[]
                            )
                            
                            yield completion_response.model_dump_json() + "\n\n"
                            break
                        
                        # Add small delay to prevent overwhelming the client
                        import asyncio
                        await asyncio.sleep(0.05)
                    
                except Exception as e:
                    logger.error(f"[{correlation_id}] Critical error in conversational message processing: {str(e)}", exc_info=True)
                    
                    # Send error response
                    error_message = "❌ I encountered a technical issue while processing your message. Please try again or contact support if the problem persists."
                    
                    error_response = {
                        "error": error_message,
                        "details": str(e),
                        "session_id": session_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    yield json.dumps(error_response) + "\n\n"
                    
            return StreamingResponse(
                generate_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/event-stream",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control"
                }
            )

        except HTTPException:
            raise
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e.message
            )
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred"
            )

    @router.get("/sessions/history",
                response_model=GetChatHistoryResponse,
                summary="Get Chat History",
                description="Get message history for a chat session")
    async def get_chat_history(
        session_id: str = Query(..., description="Session identifier"),
        current_user: Auth0User = Depends(get_current_user),
        limit: int = Query(50, le=100, description="Maximum number of messages"),
        cursor: Optional[str] = Query(None, description="Pagination cursor"),
        start_time: Optional[datetime] = Query(None, description="Start time filter"),
        end_time: Optional[datetime] = Query(None, description="End time filter")
    ) -> GetChatHistoryResponse:
        """Get chat history for a session."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting chat history for session: {session_id}")
            
            # Validate session exists
            session = active_sessions.get(session_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Session not found: {session_id}"
                )

            # Verify session ownership
            session_auth_user_id = session.get("auth_user_id", session.get("user_id"))
            user_id = current_user.db_user_id if current_user.exists_in_db else current_user.auth_id
            
            if session_auth_user_id != current_user.auth_id and session.get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only access your own session history"
                )

            # Get message history
            messages = session.get("message_history", [])
            
            # Apply filters
            if start_time:
                messages = [m for m in messages if m.get("timestamp", datetime.min) >= start_time]
            if end_time:
                messages = [m for m in messages if m.get("timestamp", datetime.max) <= end_time]
            
            # Apply pagination
            total_count = len(messages)
            start_index = 0
            if cursor:
                try:
                    start_index = int(cursor)
                except ValueError:
                    start_index = 0
            
            end_index = start_index + limit
            paginated_messages = messages[start_index:end_index]
            
            # Calculate next cursor
            next_cursor = None
            has_more = end_index < total_count
            if has_more:
                next_cursor = str(end_index)
            
            response = GetChatHistoryResponse(
                messages=paginated_messages,
                next_cursor=next_cursor,
                has_more=has_more,
                total_count=total_count
            )

            logger.info(f"[{correlation_id}] Chat history retrieved: {len(paginated_messages)} messages")
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred"
            )

    @router.delete("/sessions",
                   response_model=EndChatSessionResponse,
                   summary="End Chat Session",
                   description="End an active chat session")
    async def end_chat_session(
        session_id: str = Query(..., description="Session identifier"),
        current_user: Auth0User = Depends(get_current_user),
        request: EndChatSessionRequest = Body(...)
    ) -> EndChatSessionResponse:
        """End a chat session."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Ending chat session: {session_id}")
            
            # Validate session exists
            session = active_sessions.get(session_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Session not found: {session_id}"
                )

            # Verify session ownership
            session_auth_user_id = session.get("auth_user_id", session.get("user_id"))
            user_id = current_user.db_user_id if current_user.exists_in_db else current_user.auth_id
            
            if session_auth_user_id != current_user.auth_id and session.get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only end your own sessions"
                )

            # Update session status
            session["status"] = "ENDED"
            session["ended_at"] = datetime.utcnow()
            session["end_reason"] = request.reason or "User requested"
            session["ended_by"] = current_user.auth_id
            
            # Remove from active sessions
            del active_sessions[session_id]
            
            response = EndChatSessionResponse(
                session_id=session_id,
                status="ENDED",
                message="Chat session ended successfully",
                ended_at=datetime.utcnow()
            )

            logger.info(f"[{correlation_id}] Chat session ended: {session_id}")
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred"
            )

    @router.get("/sessions/context",
                response_model=GetSessionContextResponse,
                summary="Get Session Context",
                description="Get current context and status for a chat session")
    async def get_session_context(
        session_id: str = Query(..., description="Session identifier"),
        current_user: Auth0User = Depends(get_current_user)
    ) -> GetSessionContextResponse:
        """Get session context and status."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting session context: {session_id}")
            
            # Validate session exists
            session = active_sessions.get(session_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Session not found: {session_id}"
                )

            # Verify session ownership
            session_auth_user_id = session.get("auth_user_id", session.get("user_id"))
            user_id = current_user.db_user_id if current_user.exists_in_db else current_user.auth_id
            
            if session_auth_user_id != current_user.auth_id and session.get("user_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only access your own session context"
                )

            response = GetSessionContextResponse(
                session_id=session_id,
                status=session.get("status", "ACTIVE"),
                context=session.get("context", {}),
                active_tools=session.get("active_tools", []),
                last_activity=session.get("last_activity", session.get("created_at", datetime.utcnow()))
            )

            logger.info(f"[{correlation_id}] Session context retrieved: {session_id}")
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred"
            )

    return router
