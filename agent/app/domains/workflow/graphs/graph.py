"""Workflow Generation LangGraph

Main LangGraph implementation for generating workflows from natural language.
Orchestrates intent parsing, tool discovery, step generation, and workflow optimization.
Supports both direct generation and conversational multi-turn interactions.
"""

from ....shared import get_logger
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime, timezone

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import InMemorySaver
from ..nodes import (
    classify_intent_node,
    generate_greeting_node,
    analyze_requirements_node,
    discover_mcp_tools_node,
    request_user_input_node,
    generate_workflow_node,
    workflow_review_node,
    handle_modification_node,
    execute_workflow_node,
    handle_question_node,

    route_after_intent_classification,
    route_after_requirements_analysis,
    route_after_mcp_tool_discovery,
)

from .states import WorkflowState, ConversationPhase
logger = get_logger(__name__)


class WorkflowGraph:
    """Unified LangGraph for workflow generation supporting both direct and conversational modes.
    
    This graph orchestrates the complete workflow generation process:

    **Conversational Mode:**
    1. Classify user intent from each message
    2. Gather requirements through clarifying questions
    3. Discover and validate MCP tools
    4. Generate workflows using MCP tools
    5. Handle modifications and approval cycles
    6. Execute workflows with MCP integration
    """

    def __init__(self):
        """Initialize the workflow generation graph with MCP integration."""
        self.checkpointer = InMemorySaver()
        
        # Build the graph
        self.conversational_graph = self._build_graph()

    def _build_graph(self):
        """Build the conversational workflow generation LangGraph with MCP integration."""
        graph = StateGraph(WorkflowState)

        # Add conversational nodes
        graph.add_node("classify_intent", classify_intent_node)
        graph.add_node("generate_greeting", generate_greeting_node)
        graph.add_node("analyze_requirements", analyze_requirements_node)
        graph.add_node("discover_mcp_tools", discover_mcp_tools_node)  
        # graph.add_node("validate_mcp_tools", validate_mcp_tools_node)
        graph.add_node("generate_workflow", generate_workflow_node)
        graph.add_node("workflow_review", workflow_review_node)
        graph.add_node("handle_modification", handle_modification_node)
        graph.add_node("execute_workflow", execute_workflow_node)
        graph.add_node("request_user_input", request_user_input_node)
        graph.add_node("handle_question", handle_question_node)

        # Set the entry point
        graph.set_entry_point("classify_intent")

        # Define conditional routing logic
        graph.add_conditional_edges(
            "classify_intent",
            route_after_intent_classification,
            {
                "analyze_requirements": "analyze_requirements",
                "generate_greeting": "generate_greeting",
                "handle_modification": "handle_modification",
                "execute_workflow": "execute_workflow",
                "handle_question": "handle_question",
            },
        )

        # Updated routing to include MCP tool discovery
        graph.add_conditional_edges(
            "analyze_requirements",
            route_after_requirements_analysis,
            {
                "request_user_input": "request_user_input",
                "discover_mcp_tools": "discover_mcp_tools",  # NEW ROUTE
                "generate_workflow": "generate_workflow",
                "handle_question": "handle_question",
            },
        )

        # Add MCP tool discovery conditional routing
        graph.add_conditional_edges(
            "discover_mcp_tools",
            route_after_mcp_tool_discovery,
            {
                "request_user_input": "request_user_input",  # When tool parameters are needed
                "generate_workflow": "generate_workflow",    # When tools are ready
                "handle_question": "handle_question",        # When errors occur
            },
        )
        # graph.add_edge("validate_mcp_tools", "generate_workflow")

        # Define standard edges
        graph.add_edge("generate_workflow", "workflow_review")

        # Define terminal nodes for user-facing responses
        graph.add_edge("generate_greeting", END)
        graph.add_edge("request_user_input", END)
        graph.add_edge("workflow_review", END)
        graph.add_edge("handle_modification", END)
        graph.add_edge("execute_workflow", END)
        graph.add_edge("handle_question", END)

        # Compile the graph
        return graph.compile(
            checkpointer=self.checkpointer,
            interrupt_after=["request_user_input"],
        )

    async def stream_workflow_response(
        self, 
        message: str,
        session_id: str,
        user_id: str,
        correlation_id: str,
        existing_state: Optional[WorkflowState] = None,
        user_context: Optional[Dict[str, Any]] = None,
        available_servers: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a user message in conversational workflow generation mode.
        
        Args:and if anything happens to him, then I can't do it
            message: User's message
            session_id: Chat session identifier
            user_id: User identifier
            correlation_id: Request correlation ID
            existing_state: Optional existing conversation state
            user_context: Optional user context
            available_tools: Optional list of available tools
            
        Yields:
            Stream of conversation updates and responses
        """
        try:
            logger.info(f"[{correlation_id}] [WORKFLOW_GRAPH] Starting message processing for user {user_id}")
            
            # Prepare or update conversation state
            current_time = datetime.now(timezone.utc).isoformat()
            
            if existing_state and isinstance(existing_state, dict):
                # Update existing conversation
                logger.debug("[WORKFLOW_GRAPH] Updating existing conversation state", correlation_id=correlation_id)

                conversation_state: WorkflowState = {
                    **existing_state, 
                    "current_message": message,
                    "user_input": message,
                    "correlation_id": correlation_id,
                    "updated_at": current_time,
                    "conversation_phase": ConversationPhase.INTENT_DISCOVERY.value,
                    "available_servers": available_servers or [],
                    "errors": existing_state.get("errors", []),
                    "warnings": existing_state.get("warnings", []),
                    "message_history": [
                        *existing_state.get("message_history", []),
                        {
                            "role": "user",
                            "content": message,
                            "timestamp": current_time
                        }
                    ]
                }

            # Configure execution with proper error handling
            execution_config = {
                "configurable": {
                    "thread_id": f"session_{session_id}"
                }
            }

            # Stream conversation processing with event-based streaming
            logger.info("Starting graph stream with state", correlation_id=correlation_id)
            
            # Process the graph output with streaming support
            async for chunk in self.conversational_graph.astream(
                conversation_state,
                config=execution_config,
                stream_mode="updates"
            ):
                try:
                    # Debug: Write to file for analysis
                    # with open("workflow_events", "a") as f:
                    #     f.write("--------------------------------\n")
                    #     f.write("--------------------------------\n")
                    #     f.write("--------------------------------\n")
                    #     f.write(str(chunk) + "\n")

                    # Parse the chunk to extract node responses
                    if isinstance(chunk, dict):
                        # Handle different types of chunk structures
                        node_data = None
                        node_name = None
                        
                        # Extract node name and data from chunk
                        if "classify_intent" in chunk:
                            node_name = "classify_intent"
                            node_data = chunk["classify_intent"]
                        elif "generate_greeting" in chunk:
                            node_name = "generate_greeting"
                            node_data = chunk["generate_greeting"]
                        elif "analyze_requirements" in chunk:
                            node_name = "analyze_requirements"
                            node_data = chunk["analyze_requirements"]
                        elif "discover_mcp_tools" in chunk:
                            node_name = "discover_mcp_tools"
                            node_data = chunk["discover_mcp_tools"]
                        # elif "request_user_input" in chunk:
                        #     node_name = "request_user_input"
                        #     node_data = chunk["request_user_input"]
                        # elif "__interrupt__" in chunk:
                        #     node_name = "__interrupt__"
                        #     node_data = chunk["__interrupt__"]
                        elif "generate_workflow" in chunk:
                            node_name = "generate_workflow"
                            node_data = chunk["generate_workflow"]
                        elif "workflow_review" in chunk:
                            node_name = "workflow_review"
                            node_data = chunk["workflow_review"]
                        
                        if node_data and node_name:
                            logger.info(f"[{correlation_id}] [WORKFLOW_GRAPH] Processing node: {node_name}")
                            
                            # Handle different node types
                            if node_name == "classify_intent":
                                # Intent classification - internal reasoning
                                reasoning = node_data.get("conversation_context", {}).get("intent_reasoning", "")
                                if reasoning:
                                    yield {
                                        "type": "thinking",
                                        "content": reasoning,
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                            
                            elif node_name == "generate_greeting":
                                # Assistant greeting response
                                yield {
                                    "type": "assistant",
                                    "content": node_data.get("assistant_response", ""),
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                            
                            elif node_name == "analyze_requirements":
                                # Requirements analysis
                                requirements = node_data.get("collected_requirements", {})
                                missing_params = node_data.get("missing_parameters", [])
                                can_proceed = node_data.get("can_proceed", False)
                                needs_clarification = node_data.get("needs_clarification", False)
                                
                                if needs_clarification or not can_proceed:
                                    # Need user input for missing parameters
                                    form_fields = self._generate_form_fields(missing_params, requirements)
                                    yield {
                                        "type": "user_input",
                                        "content": {
                                            "form_fields": form_fields,
                                            "missing_parameters": missing_params
                                        },
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                                else:
                                    # Requirements complete - internal thinking
                                    analysis_reasoning = requirements.get("analysis_reasoning", "")
                                    if analysis_reasoning:
                                        yield {
                                            "type": "thinking",
                                            "content": analysis_reasoning,
                                            "timestamp": datetime.now(timezone.utc).isoformat()
                                        }
                            
                            elif node_name == "discover_mcp_tools":
                                # MCP tool discovery
                                assistant_response = node_data.get("assistant_response", "")
                                form_fields = node_data.get("form_fields", [])
                                form_metadata = node_data.get("form_metadata", {})
                                
                                # Check if we need user input for tool configuration
                                if form_fields:
                                    yield {
                                        "type": "user_input",
                                        "content": {
                                            "assistant_message": assistant_response,
                                            "form_fields": form_fields,
                                            "form_metadata": form_metadata
                                        },
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                                else:
                                    # Tools discovered - show assistant response
                                    if assistant_response:
                                        yield {
                                            "type": "assistant",
                                            "content": assistant_response,
                                            "timestamp": datetime.now(timezone.utc).isoformat()
                                        }
                            
                            # elif node_name == "request_user_input":
                            #     # Explicit user input request
                            #     form_fields = node_data.get("form_fields", [])
                            #     yield {
                            #         "type": "user_input",
                            #         "content": {
                            #             "form_fields": form_fields,
                            #             "form_metadata": node_data.get("form_metadata", {})
                            #         },
                            #         "timestamp": datetime.now(timezone.utc).isoformat()
                            #     }
                            
                            # elif node_name == "__interrupt__":
                            #     # Graph interrupted, waiting for user input
                            #     yield {
                            #         "type": "user_input",
                            #         "content": {
                            #             "form_fields": [],
                            #             "message": "Please provide additional information to continue."
                            #         },
                            #         "timestamp": datetime.now(timezone.utc).isoformat()
                            #     }
                        
                            # Handle other potential node types that might appear
                            elif "generate_workflow" in chunk:
                                workflow_data = chunk["generate_workflow"]
                                workflow_draft = workflow_data.get("workflow_draft", {})
                                assistant_response = workflow_data.get("assistant_response", "")
                                
                                if assistant_response:
                                    yield {
                                        "type": "assistant",
                                        "content": assistant_response,
                                        "workflow_draft": workflow_draft,
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                                else:
                                    # Show workflow generation as thinking
                                    yield {
                                        "type": "thinking",
                                        "content": f"Generated workflow with {len(workflow_draft.get('steps', []))} steps",
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                            
                            elif "workflow_review" in chunk:
                                review_data = chunk["workflow_review"]
                                assistant_response = review_data.get("assistant_response", "")
                                requires_approval = review_data.get("requires_approval", False)
                                
                                if assistant_response:
                                    yield {
                                        "type": "assistant",
                                        "content": assistant_response,
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                                
                                if requires_approval:
                                    yield {
                                        "type": "user_input",
                                        "content": {
                                            "form_fields": [
                                                {
                                                    "name": "approval",
                                                    "label": "Approve Workflow",
                                                    "type": "checkbox",
                                                    "required": True
                                                }
                                            ],
                                            "message": "Please review and approve the generated workflow."
                                        },
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                            
                            elif "execute_workflow" in chunk:
                                execution_data = chunk["execute_workflow"]
                                assistant_response = execution_data.get("assistant_response", "")
                                execution_results = execution_data.get("execution_results", {})
                                
                                if assistant_response:
                                    yield {
                                        "type": "assistant",
                                        "content": assistant_response,
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                                else:
                                    # Show execution progress as thinking
                                    yield {
                                        "type": "thinking",
                                        "content": "Executing workflow...",
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                            
                            elif "handle_question" in chunk:
                                question_data = chunk["handle_question"]
                                yield {
                                    "type": "assistant",
                                    "content": question_data.get("assistant_response", ""),
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                            
                            elif "handle_modification" in chunk:
                                modification_data = chunk["handle_modification"]
                                assistant_response = modification_data.get("assistant_response", "")
                                
                                if assistant_response:
                                    yield {
                                        "type": "assistant",
                                        "content": assistant_response,
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                except Exception as e:
                    logger.error(f"[{correlation_id}] [WORKFLOW_GRAPH] Error processing chunk: {e}", exc_info=True)
                    yield {
                        "type": "assistant",
                        "content": "An error occurred while processing your message. Please try again.",
                        "timestamp": datetime.utcnow().isoformat()
                    }

            # Get final state and send completion message
            try:
                final_state = await self.conversational_graph.aget_state(execution_config)
                
                # Send final completion message
                yield {
                    "type": "thinking",
                    "content": "Processing complete.",
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.warning(f"[{correlation_id}] [WORKFLOW_GRAPH] Could not get final state: {e}")
                # Send completion without final state
                yield {
                    "type": "thinking",
                    "content": "Processing complete.",
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"Conversational message processing failed: {error_msg}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            yield {
                "type": "assistant",
                "content": f"An error occurred: {error_msg}",
                "timestamp": datetime.utcnow().isoformat()
            }

    def _generate_form_fields(self, missing_parameters: List[str], requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate form fields for missing parameters based on requirements analysis."""
        form_fields = []
        
        for param in missing_parameters:
            field = {
                "name": param,
                "label": param.replace("_", " ").title(),
                "type": "text",
                "required": True,
                "placeholder": f"Enter {param.replace('_', ' ')}"
            }
            
            # Add specific field types based on parameter name
            if "email" in param.lower():
                field["type"] = "email"
            elif "url" in param.lower() or "webhook" in param.lower():
                field["type"] = "url"
            elif "password" in param.lower() or "token" in param.lower() or "key" in param.lower():
                field["type"] = "password"
            elif "number" in param.lower() or "count" in param.lower():
                field["type"] = "number"
            elif "date" in param.lower() or "time" in param.lower():
                field["type"] = "datetime-local"
            
            form_fields.append(field)
        
        return form_fields

    def _generate_tool_config_form_fields(self, discovered_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate form fields for tool configuration based on discovered tools."""
        form_fields = []
        
        for tool in discovered_tools:
            tool_name = tool.get("name", "")
            params_schema = tool.get("parameters_schema", {})
            required_params = params_schema.get("required", [])
            properties = params_schema.get("properties", {})
            
            # Add tool name as a section header
            form_fields.append({
                "name": f"tool_{tool_name}_header",
                "type": "section_header",
                "label": f"Configure {tool_name}",
                "description": tool.get("description", "")
            })
            
            # Add fields for each required parameter
            for param_name in required_params:
                param_schema = properties.get(param_name, {})
                field = {
                    "name": f"{tool_name}_{param_name}",
                    "label": param_schema.get("description", param_name.replace("_", " ").title()),
                    "type": "text",
                    "required": True,
                    "placeholder": f"Enter {param_name.replace('_', ' ')}",
                    "tool_name": tool_name,
                    "param_name": param_name
                }
                
                # Set field type based on schema
                param_type = param_schema.get("type", "string")
                if param_type == "number":
                    field["type"] = "number"
                elif param_type == "boolean":
                    field["type"] = "checkbox"
                elif param_type == "array":
                    field["type"] = "textarea"
                    field["placeholder"] = "Enter values separated by commas"
                
                form_fields.append(field)
        
        return form_fields
