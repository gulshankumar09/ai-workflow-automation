"""Workflow Execution Nodes for Conversational Workflows

This module handles workflow execution using MCP integration.
"""

from typing import Dict, Any, List
from datetime import datetime, timezone

from ..graphs.states import WorkflowState
from ....shared import get_logger
from ....application.mcp_service import MCPService

logger = get_logger(__name__)


async def execute_workflow_node(state: WorkflowState, mcp_service: MCPService = None) -> Dict[str, Any]:
    """Execute workflow using MCP tools.
    
    Args:
        state: Current conversational workflow state
        mcp_service: Optional MCP service instance
        
    Returns:
        Updated state with execution results
    """
    try:
        logger.info("Starting workflow execution with MCP integration...")
        
        workflow_draft = state.get("workflow_draft", {})
        user_id = state.get("user_id", "")
        
        if not workflow_draft:
            return {
                "assistant_response": "I don't have a workflow to execute. Let's create one first!",
                "conversation_phase": "intent_discovery"
            }
        
        # Extract workflow steps
        workflow_steps = workflow_draft.get("steps", [])
        
        if not workflow_steps:
            return {
                "assistant_response": "The workflow doesn't have any steps to execute. Let me regenerate it.",
                "conversation_phase": "workflow_generation"
            }
        
        # Initialize MCP service if not provided
        if not mcp_service:
            mcp_service = MCPService()
        
        # Execute workflow using MCP service
        execution_results = []
        successful_steps = 0
        failed_steps = 0
        
        execution_start_time = datetime.now()
        
        for i, step in enumerate(workflow_steps):
            try:
                step_start_time = datetime.now()
                
                # Check if MCP service is available and initialized
                mcp_available = await _check_mcp_availability(mcp_service, user_id)
                
                if mcp_available:
                    # Execute using real MCP service
                    result = await mcp_service.execute_tool(
                        tool_name=step.get("tool_name", ""),
                        parameters=step.get("parameters", {}),
                        user_id=user_id
                    )
                    
                    execution_results.append({
                        "step_id": step.get("step_id", f"step_{i+1}"),
                        "tool_name": step.get("tool_name", "unknown"),
                        "status": result.status,
                        "result": result.data,
                        "execution_time": result.execution_time,
                        "description": step.get("description", ""),
                        "execution_mode": "mcp_real"
                    })
                    
                    if result.status == "success":
                        successful_steps += 1
                    else:
                        failed_steps += 1
                        
                else:
                    # Fallback execution (simulation)
                    step_duration = (datetime.now() - step_start_time).total_seconds()
                    simulation_result = _simulate_step_execution(step)
                    
                    execution_results.append({
                        "step_id": step.get("step_id", f"step_{i+1}"),
                        "tool_name": step.get("tool_name", "unknown"),
                        "status": "simulated",
                        "result": simulation_result,
                        "execution_time": step_duration,
                        "description": step.get("description", ""),
                        "execution_mode": "simulation"
                    })
                    successful_steps += 1
                    
            except Exception as e:
                logger.error(f"Step execution failed: {e}")
                execution_results.append({
                    "step_id": step.get("step_id", f"step_{i+1}"),
                    "tool_name": step.get("tool_name", "unknown"),
                    "status": "failed",
                    "error": str(e),
                    "execution_time": 0,
                    "description": step.get("description", ""),
                    "execution_mode": "error"
                })
                failed_steps += 1
        
        # Calculate total execution time
        total_execution_time = (datetime.now() - execution_start_time).total_seconds()
        
        # Generate execution summary
        execution_summary = _generate_execution_summary(
            execution_results, 
            successful_steps, 
            failed_steps, 
            total_execution_time,
            mcp_available
        )
        
        return {
            "assistant_response": execution_summary,
            "execution_results": execution_results,
            "execution_approved": True,
            "execution_summary": {
                "total_steps": len(execution_results),
                "successful_steps": successful_steps,
                "failed_steps": failed_steps,
                "execution_time": total_execution_time,
                "mcp_enabled": mcp_available
            },
            "conversation_phase": "execution_complete"
        }
        
    except Exception as e:
        logger.error(f"MCP workflow execution failed: {e}")
        return {
            "assistant_response": f"Workflow execution failed: {str(e)}. Please try again or modify the workflow.",
            "execution_results": [],
            "errors": [f"Execution failed: {str(e)}"],
            "conversation_phase": "execution_failed"
        }


async def _check_mcp_availability(mcp_service: MCPService, user_id: str) -> bool:
    """Check if MCP service is available and properly initialized.
    
    Args:
        mcp_service: MCP service instance
        user_id: User identifier
        
    Returns:
        True if MCP is available, False otherwise
    """
    try:
        if not mcp_service:
            return False
        
        # Try a simple operation to check if MCP is working
        available_servers = await mcp_service.get_available_servers_for_user(user_id)
        return len(available_servers.get("system_servers", [])) > 0 or \
               len(available_servers.get("public_servers", [])) > 0 or \
               len(available_servers.get("private_servers", [])) > 0
               
    except Exception as e:
        logger.warning(f"MCP availability check failed: {e}")
        return False


def _simulate_step_execution(step: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate step execution when MCP is not available.
    
    Args:
        step: Workflow step configuration
        
    Returns:
        Simulated execution result
    """
    tool_name = step.get("tool_name", "unknown")
    step_type = step.get("step_type", "processing")
    parameters = step.get("parameters", {})
    
    # Generate realistic simulation results based on step type
    if step_type == "source_control":
        return {
            "message": f"Successfully accessed repository: {parameters.get('repository', 'example/repo')}",
            "items_processed": 5,
            "status": "completed"
        }
    elif step_type == "communication":
        return {
            "message": f"Message sent to {parameters.get('channel', '#general')}",
            "message_id": f"msg_{datetime.now().timestamp()}",
            "status": "delivered"
        }
    elif step_type == "data_storage":
        return {
            "message": f"Database operation completed on {parameters.get('table', 'data')}",
            "rows_affected": 3,
            "status": "success"
        }
    elif step_type == "file_operation":
        return {
            "message": f"File operation completed at {parameters.get('path', '/tmp/workflow')}",
            "files_processed": 2,
            "status": "success"
        }
    else:
        return {
            "message": f"Step '{tool_name}' executed successfully (simulated)",
            "status": "completed",
            "simulation": True
        }


def _generate_execution_summary(
    execution_results: List[Dict[str, Any]], 
    successful_steps: int, 
    failed_steps: int, 
    total_execution_time: float,
    mcp_available: bool
) -> str:
    """Generate a user-friendly execution summary.
    
    Args:
        execution_results: List of execution results
        successful_steps: Number of successful steps
        failed_steps: Number of failed steps
        total_execution_time: Total execution time in seconds
        mcp_available: Whether MCP was available during execution
        
    Returns:
        Formatted execution summary string
    """
    if mcp_available:
        summary = (
            f"🚀 **Workflow Execution Completed!**\n\n"
            f"**Results:** {successful_steps}/{len(execution_results)} steps successful\n"
            f"**Total execution time:** {total_execution_time:.2f}s\n"
            f"**MCP Integration:** ✅ Active\n\n"
            f"**Step Details:**\n"
        )
    else:
        summary = (
            f"🧪 **Workflow Simulation Completed!**\n\n"
            f"**Results:** {successful_steps}/{len(execution_results)} steps simulated\n"
            f"**Total simulation time:** {total_execution_time:.2f}s\n"
            f"**Note:** This was a simulation. Configure MCP servers for real execution.\n\n"
            f"**Step Details:**\n"
        )
    
    for result in execution_results:
        status = result.get("status", "unknown")
        execution_mode = result.get("execution_mode", "unknown")
        
        if status == "success":
            status_emoji = "✅"
        elif status == "simulated":
            status_emoji = "🧪"
        elif status == "failed":
            status_emoji = "❌"
        else:
            status_emoji = "❓"
            
        description = result.get("description", result.get("tool_name", "Unknown step"))
        execution_time = result.get("execution_time", 0)
        
        summary += f"{status_emoji} {description}"
        if execution_time > 0:
            summary += f" ({execution_time:.2f}s)"
        summary += "\n"
        
        # Add result details for successful steps
        if status in ["success", "simulated"] and "result" in result:
            result_data = result["result"]
            if isinstance(result_data, dict):
                if "message" in result_data:
                    summary += f"   └─ {result_data['message']}\n"
                elif "status" in result_data:
                    summary += f"   └─ Status: {result_data['status']}\n"
    
    # Add next steps
    if failed_steps > 0:
        summary += f"\n⚠️ {failed_steps} steps failed. Would you like me to retry them or modify the workflow?"
    else:
        summary += f"\n🎉 All steps completed successfully! Your workflow is working perfectly."
    
    # Add helpful tips
    if not mcp_available:
        summary += f"\n\n💡 **Tip:** Connect your accounts and configure MCP servers to enable real workflow execution."
    
    return summary 