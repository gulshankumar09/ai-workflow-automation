"""
gRPC Chat Handler for ai-workflow-automation Core Microservice.

This module implements the ChatService gRPC interface,
providing conversational AI capabilities with real-time streaming.
"""

import asyncio
import json
from typing import AsyncGenerator, TYPE_CHECKING
from uuid import uuid4
from datetime import datetime

import grpc
import grpc.aio as aio

from app.shared.exceptions import BaseAppException, NotFoundException, ValidationException, WorkflowGenerationError
from app.shared.logger import get_logger
from app.application.user_service import UserService
from app.application.conversational_workflow_service import ConversationalWorkflowService

# Setup logger
logger = get_logger(__name__)

# Import generated protobuf modules
try:
    from app.interfaces.grpc.protos import chat_pb2, chat_pb2_grpc
except ImportError as e:
    logger.error(f"Failed to import protobuf modules: {e}")
    raise ImportError("Protobuf modules not available. Run 'make generate-protos' first.")


class ChatHandler(chat_pb2_grpc.ChatServiceServicer):
    """
    gRPC handler for chat operations.
    
    Implements the ChatService interface defined in chat.proto.
    """

    def __init__(self, dependency_container=None):
        # Initialize with basic setup - services will be lazy-loaded
        self.dependency_container = dependency_container
        self.active_sessions: dict[str, dict] = {}
        self.active_streams: dict[str, bool] = {}
        
        # Initialize services - with fallback for missing dependencies
        try:
            if self.dependency_container:
                self.user_service = UserService(dependency_container=self.dependency_container)
            else:
                self.user_service = UserService()
        except Exception as e:
            logger.warning(f"Failed to initialize UserService with container: {e}")
            
        try:
            if self.dependency_container:
                self.conversational_workflow_service = ConversationalWorkflowService(dependency_container=self.dependency_container)
            else:
                self.conversational_workflow_service = ConversationalWorkflowService()
        except Exception as e:
            logger.warning(f"Failed to initialize WorkflowService with container: {e}")

    async def StartChatSession(
        self,
        request: chat_pb2.StartChatSessionRequest,
        context: aio.ServicerContext
    ) -> chat_pb2.StartChatSessionResponse:
        """Start a new chat session."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Starting chat session for user: {request.user_id}")
            
            # Validate request
            if not request.user_id:
                raise ValidationException(
                    message="User ID is required",
                    code="MISSING_USER_ID",
                    correlation_id=correlation_id
                )

            # Create session
            session_id = str(uuid4())
            session_data = {
                "session_id": session_id,
                "user_id": request.user_id,
                "session_type": chat_pb2.SessionType.Name(request.session_type),
                "context": dict(request.context) if request.context else {},
                "capabilities": list(request.capabilities) if request.capabilities else [],
                "created_at": datetime.utcnow().isoformat(),
                "message_history": [],
                "active_tools": [],
                "metrics": {
                    "message_count": 0,
                    "tool_calls_count": 0,
                    "tokens_used": 0
                }
            }
            
            # Store session
            self.active_sessions[session_id] = session_data
            
            # Get available tools for user
            user_context = await self.user_service.get_user_context(
                request.user_id,
                correlation_id=correlation_id
            )
            
            # Get available tools for user from the user service
            available_tools = await self.user_service.get_user_available_tools(request.user_id)
            
            # Convert response to protobuf
            response = chat_pb2.StartChatSessionResponse(
                session_id=session_id,
                status=chat_pb2.SessionStatus.SESSION_STATUS_ACTIVE,
                context=session_data["context"],
                available_tools=available_tools,
                message="Chat session started successfully"
            )

            logger.info(f"[{correlation_id}] Chat session started: {session_id}")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    async def SendMessage(
        self,
        request: chat_pb2.SendMessageRequest,
        context: aio.ServicerContext
    ) -> AsyncGenerator[chat_pb2.ChatMessageResponse, None]:
        """Send a message and get streaming response."""
        correlation_id = str(uuid4())
        stream_id = str(uuid4())
        self.active_streams[stream_id] = True
        
        try:
            logger.info(f"[{correlation_id}] Processing message for session: {request.session_id}")
            
            # Validate request
            if not request.session_id:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Session ID is required")
                return
                
            if not request.message:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Message is required")
                return

            # Get session
            session = self.active_sessions.get(request.session_id)
            if not session:
                await context.abort(grpc.StatusCode.NOT_FOUND, f"Session not found: {request.session_id}")
                return

            # Create message ID
            message_id = str(uuid4())
            timestamp = datetime.utcnow().isoformat()
            metadata = dict(request.metadata) if request.metadata else {}
            metadata["correlation_id"] = correlation_id
            
            # Add user message to history
            user_message = {
                "message_id": message_id,
                "session_id": request.session_id,
                "content": request.message,
                "message_type": chat_pb2.MessageType.Name(request.message_type),
                "timestamp": timestamp,
                "metadata": metadata
            }
            session["message_history"].append(user_message)
            session["metrics"]["message_count"] += 1

            # Process message with AI (simulated for now)
            async for response_chunk in self._process_message_stream(
                session, request.message, correlation_id, stream_id
            ):
                if not self.active_streams.get(stream_id, False):
                    logger.info(f"[{correlation_id}] Stream cancelled by client")
                    break
                    
                yield response_chunk
                
                # Add small delay to prevent overwhelming the client
                await asyncio.sleep(0.05)

            logger.info(f"[{correlation_id}] Message processing completed for session: {request.session_id}")
            
        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")
            
        finally:
            # Clean up stream
            self.active_streams.pop(stream_id, None)

    async def GetChatHistory(
        self,
        request: chat_pb2.GetChatHistoryRequest,
        context: aio.ServicerContext
    ) -> chat_pb2.GetChatHistoryResponse:
        """Get chat history for a session."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting chat history for session: {request.session_id}")
            
            # Validate request
            if not request.session_id:
                raise ValidationException(
                    message="Session ID is required",
                    code="MISSING_SESSION_ID",
                    correlation_id=correlation_id
                )

            # Get session
            session = self.active_sessions.get(request.session_id)
            if not session:
                raise NotFoundException(
                    message=f"Session not found: {request.session_id}",
                    code="SESSION_NOT_FOUND",
                    correlation_id=correlation_id
                )

            # Get message history with pagination
            messages = session["message_history"]
            limit = request.limit or 50
            
            # Apply time filters if specified
            filtered_messages = messages
            if request.start_time or request.end_time:
                # Apply time filtering logic here
                pass
            
            # Apply pagination
            start_idx = 0
            if request.cursor:
                # Find cursor position
                for i, msg in enumerate(filtered_messages):
                    if msg["message_id"] == request.cursor:
                        start_idx = i + 1
                        break
            
            page_messages = filtered_messages[start_idx:start_idx + limit]
            has_more = len(filtered_messages) > start_idx + limit
            next_cursor = page_messages[-1]["message_id"] if page_messages and has_more else ""

            # Convert to protobuf
            chat_messages = [
                self._convert_to_chat_message_proto(msg)
                for msg in page_messages
            ]
            
            response = chat_pb2.GetChatHistoryResponse(
                messages=chat_messages,
                next_cursor=next_cursor,
                has_more=has_more,
                total_count=len(filtered_messages)
            )

            logger.info(f"[{correlation_id}] Retrieved {len(chat_messages)} messages")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except NotFoundException as e:
            logger.warning(f"[{correlation_id}] Resource not found: {e.message}")
            await context.abort(grpc.StatusCode.NOT_FOUND, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    async def EndChatSession(
        self,
        request: chat_pb2.EndChatSessionRequest,
        context: aio.ServicerContext
    ) -> chat_pb2.EndChatSessionResponse:
        """End a chat session."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Ending chat session: {request.session_id}")
            
            # Validate request
            if not request.session_id:
                raise ValidationException(
                    message="Session ID is required",
                    code="MISSING_SESSION_ID",
                    correlation_id=correlation_id
                )

            # Get and remove session
            session = self.active_sessions.pop(request.session_id, None)
            if not session:
                raise NotFoundException(
                    message=f"Session not found: {request.session_id}",
                    code="SESSION_NOT_FOUND",
                    correlation_id=correlation_id
                )

            ended_at = datetime.utcnow().isoformat()
            
            response = chat_pb2.EndChatSessionResponse(
                session_id=request.session_id,
                status=chat_pb2.SessionStatus.SESSION_STATUS_ENDED,
                message="Chat session ended successfully",
                ended_at=ended_at
            )

            logger.info(f"[{correlation_id}] Chat session ended: {request.session_id}")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except NotFoundException as e:
            logger.warning(f"[{correlation_id}] Resource not found: {e.message}")
            await context.abort(grpc.StatusCode.NOT_FOUND, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    async def GetSessionContext(
        self,
        request: chat_pb2.GetSessionContextRequest,
        context: aio.ServicerContext
    ) -> chat_pb2.GetSessionContextResponse:
        """Get session context and metrics."""
        correlation_id = str(uuid4())
        
        try:
            logger.info(f"[{correlation_id}] Getting session context: {request.session_id}")
            
            # Validate request
            if not request.session_id:
                raise ValidationException(
                    message="Session ID is required",
                    code="MISSING_SESSION_ID",
                    correlation_id=correlation_id
                )

            # Get session
            session = self.active_sessions.get(request.session_id)
            if not session:
                raise NotFoundException(
                    message=f"Session not found: {request.session_id}",
                    code="SESSION_NOT_FOUND",
                    correlation_id=correlation_id
                )

            # Convert metrics to protobuf
            metrics = chat_pb2.SessionMetrics(
                message_count=session["metrics"]["message_count"],
                tool_calls_count=session["metrics"]["tool_calls_count"],
                tokens_used=session["metrics"]["tokens_used"]
            )
            
            response = chat_pb2.GetSessionContextResponse(
                session_id=request.session_id,
                status=chat_pb2.SessionStatus.SESSION_STATUS_ACTIVE,
                context=session["context"],
                active_tools=session["active_tools"],
                metrics=metrics
            )

            logger.info(f"[{correlation_id}] Session context retrieved: {request.session_id}")
            return response

        except ValidationException as e:
            logger.warning(f"[{correlation_id}] Validation error: {e.message}")
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, e.message)
            
        except NotFoundException as e:
            logger.warning(f"[{correlation_id}] Resource not found: {e.message}")
            await context.abort(grpc.StatusCode.NOT_FOUND, e.message)
            
        except BaseAppException as e:
            logger.error(f"[{correlation_id}] Application error: {e.to_dict()}")
            await context.abort(grpc.StatusCode.INTERNAL, e.message)
            
        except Exception as e:
            logger.error(f"[{correlation_id}] Unexpected error: {str(e)}", exc_info=True)
            await context.abort(grpc.StatusCode.INTERNAL, "An unexpected error occurred")

    async def _process_message_stream(
        self, 
        session: dict, 
        message: str, 
        correlation_id: str,
        stream_id: str
    ) -> AsyncGenerator[chat_pb2.ChatMessageResponse, None]:
        """Process user message with conversational workflow generation and stream response."""
        
        try:
            logger.info(f"[{correlation_id}] [CHAT_HANDLER] Starting message processing for session: {session['session_id']}")
            logger.debug(f"[{correlation_id}] [CHAT_HANDLER] Message content: {message}")
            logger.debug(f"[{correlation_id}] [CHAT_HANDLER] Session state: {session}")
            
            # Process message through conversational workflow service
            async for conversation_event in self.conversational_workflow_service.process_conversational_message(
                message=message,
                session_id=session["session_id"],
                user_id=session["user_id"],
                correlation_id=correlation_id
            ):
                # Check if stream is still active
                if not self.active_streams.get(stream_id, False):
                    logger.info(f"[{correlation_id}] Stream cancelled by client")
                    break
                
                event_type = conversation_event.get("type", "")
                response_message_id = str(uuid4())
                
                if event_type in ["assistant", "user_input", "thinking"]:
                    # Stream assistant response to client
                    content = json.dumps(conversation_event)
                    conversation_phase = conversation_event.get("conversation_phase", "")
                    
                    logger.info(f"[{correlation_id}] [CHAT_HANDLER] Sending assistant response to client")
                   
                    yield chat_pb2.ChatMessageResponse(
                        session_id=session["session_id"],
                        message_id=response_message_id,
                        content=content,
                        message_type=chat_pb2.MessageType.MESSAGE_TYPE_ASSISTANT,
                        status=chat_pb2.ResponseStatus.RESPONSE_STATUS_SUCCESS,
                        timestamp=datetime.utcnow(),
                        is_final=False
                    )
                    
                    # Update in memory session with assistant response
                    assistant_message = {
                        "message_id": response_message_id,
                        "session_id": session["session_id"],
                        "content": content,  # This is now JSON string
                        "message_type": "MESSAGE_TYPE_ASSISTANT",
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
                    logger.error(f"[{correlation_id}] [CHAT_HANDLER] Conversation error: {error_message}")

                    yield chat_pb2.ChatMessageResponse(
                        session_id=session["session_id"],
                        message_id=response_message_id,
                        content=f"{error_message}",
                        message_type=chat_pb2.MessageType.MESSAGE_TYPE_ASSISTANT,
                        status=chat_pb2.ResponseStatus.RESPONSE_STATUS_ERROR,
                        timestamp=datetime.utcnow(),
                        is_final=True
                    )
                    break
                
                elif event_type == "complete":
                    # Handle conversation completion
                    final_state = conversation_event.get("final_state", {})
                    
                    # Update session metrics
                    if final_state:
                        session["metrics"]["tokens_used"] += len(message)
                        if "workflow_draft" in final_state:
                            session["last_generated_workflow"] = final_state["workflow_draft"]
                    
                    logger.info(f"[{correlation_id}] Conversational message processing completed")
                
        except Exception as e:
            logger.error(f"[{correlation_id}] Critical error in conversational message processing: {str(e)}", exc_info=True)
            
            # Send error response if stream is still active
            if self.active_streams.get(stream_id, False):
                error_message = "❌ I encountered a technical issue while processing your message. Please try again or contact support if the problem persists."
                
                yield chat_pb2.ChatMessageResponse(
                    session_id=session["session_id"],
                    message_id=response_message_id,
                    content=error_message,
                    message_type=chat_pb2.MessageType.MESSAGE_TYPE_ASSISTANT,
                    status=chat_pb2.ResponseStatus.RESPONSE_STATUS_ERROR,
                    timestamp=datetime.utcnow(),
                    is_final=True
                )

    def _convert_to_chat_message_proto(self, message: dict) -> chat_pb2.ChatMessage:
        """Convert domain message to protobuf message."""
        if chat_pb2 is None:
            return None
        
        # Convert timestamp string back to datetime if needed
        timestamp = message["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
            
        return chat_pb2.ChatMessage(
            message_id=message["message_id"],
            session_id=message["session_id"],
            content=message["content"],
            message_type=chat_pb2.MessageType.Value(message["message_type"]),
            timestamp=timestamp,
            metadata=message.get("metadata", {}),
            tool_calls=[]  # Add tool calls conversion if needed
        ) 