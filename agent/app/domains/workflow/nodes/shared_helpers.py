"""Shared Helper Functions for Conversational Workflow Nodes

This module contains common utility functions used across multiple nodes.
"""

from typing import Dict, Any, List
from datetime import datetime

from ....shared import get_logger

logger = get_logger(__name__)


async def _get_available_mcp_servers_list(user_id: str, mcp_service) -> List[Dict[str, Any]]:
    """Fetch available MCP servers from unified MCP service.
    
    Args:
        user_id: User identifier
        mcp_service: Unified MCP service instance
        
    Returns:
        List of MCP server information for requirements analysis
    """
    try:
        # Get servers using unified service
        servers_response = await mcp_service.get_available_servers_for_user(user_id)
        
        # Convert to simplified format for requirements analysis
        servers_list = []
        
        # Process all server categories
        for category in ['system_servers', 'public_servers', 'private_servers']:
            for server in servers_response.get(category, []):
                server_info = {
                    'id': server.get('id'),
                    'name': server.get('name'),
                    'description': server.get('description'),
                    'access_level': server.get('access_level'),
                    'platforms': server.get('platforms', []),
                    'capabilities': server.get('capabilities', [])
                }
                servers_list.append(server_info)
        
        logger.debug(f"Retrieved {len(servers_list)} available MCP servers for requirements analysis")
        return servers_list
        
    except Exception as e:
        logger.error(f"Failed to fetch available MCP servers: {str(e)}")
        # Return empty list if we can't fetch servers - analysis can still proceed
        return []


def _format_available_tools(available_tools: List[Dict[str, Any]]) -> str:
    """Format available tools for prompt context."""
    if not available_tools:
        return "No specific tools context available."
    
    tool_descriptions = []
    for tool in available_tools[:10]:  # Limit to first 10 tools
        name = tool.get('name', 'unknown')
        description = tool.get('description', 'No description')
        server = tool.get('server', 'unknown')
        tool_descriptions.append(f"- {name} ({server}): {description}")
    
    return "\n".join(tool_descriptions)


async def _validate_mcp_server_availability(
    required_servers: List[Dict[str, Any]], 
    correlation_id: str
) -> List[Dict[str, Any]]:
    """Validate that required MCP servers are available and configured.
    
    Args:
        required_servers: List of required MCP server configurations
        correlation_id: Request correlation ID
        
    Returns:
        List of validated server configurations with availability status
    """
    validated_servers = []
    
    # Known MCP servers from configuration
    known_servers = {
        "slack": {"status": "configured", "capabilities": ["send_message", "get_channel_history", "list_channels"]},
        "github": {"status": "configured", "capabilities": ["create_issue", "get_repository", "list_repositories"]},
        "postgres": {"status": "configured", "capabilities": ["execute_query", "insert_data", "list_tables"]},
        "filesystem": {"status": "configured", "capabilities": ["read_file", "write_file", "list_directory"]}
    }
    
    for server_config in required_servers:
        server_name = server_config.get("server_name", "")
        
        if server_name in known_servers:
            validated_server = {
                **server_config,
                "availability_status": "available",
                "configured_capabilities": known_servers[server_name]["capabilities"],
                "validation_timestamp": datetime.utcnow().isoformat()
            }
        else:
            validated_server = {
                **server_config,
                "availability_status": "not_configured",
                "configured_capabilities": [],
                "validation_timestamp": datetime.utcnow().isoformat(),
                "validation_note": f"Server '{server_name}' not found in known configurations"
            }
        
        validated_servers.append(validated_server)
        logger.debug(f"[{correlation_id}] Validated MCP server '{server_name}': {validated_server['availability_status']}")
    
    return validated_servers 