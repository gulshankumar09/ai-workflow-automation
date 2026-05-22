"""
Unified MCP Service - Single Point for All MCP Operations

This service consolidates:
- External server configurations (GitHub, Slack, etc.)
- User server management (leveraging domain services)
- Circuit breaker protection
- Tool execution with monitoring

Built on top of existing domain services rather than duplicating functionality.
"""

from builtins import ValueError
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import uuid
from langchain_core.tools import BaseTool

from app.domains.mcp.services import MCPOperationsService, MCPConnectionService
from app.domains.mcp.value_objects import AccessLevel, UserMCPServerInput
from app.domains.mcp.entities import MCPServer
from app.infrastructure.monitoring import EnhancedMultiServerCircuitBreaker, CircuitBreakerConfig
from app.shared.exceptions import ExternalServiceException, ErrorSeverity


class MCPToolExecutionResult:
    """Result container for MCP tool execution"""
    
    def __init__(self, status: str, data: Any = None, error: str = None, execution_time: float = 0.0):
        self.status = status
        self.data = data
        self.error = error
        self.execution_time = execution_time


class MCPService:
    """Single service for all MCP operations using domain services"""
    
    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.logger = logging.getLogger(__name__)
        
        # Use existing domain services
        self.mcp_ops = MCPOperationsService(correlation_id=correlation_id)
        self.mcp_conn = MCPConnectionService(correlation_id=correlation_id)
        
        # Add circuit breaker for reliability
        self.circuit_breaker = EnhancedMultiServerCircuitBreaker(correlation_id=correlation_id)
        
        # Predefined server configurations
        # self.predefined_servers = {
        #     "github": {
        #         "command": ["npx", "@modelcontextprotocol/server-github"],
        #         "required_env": ["GITHUB_PERSONAL_ACCESS_TOKEN"],
        #         "tools": ["create_issue", "create_repository", "get_repository", "search_repositories"]
        #     },
        #     "slack": {
        #         "command": ["npx", "@modelcontextprotocol/server-slack"],
        #         "required_env": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
        #         "tools": ["send_message", "list_channels", "get_channel_info"]
        #     },
        #     "filesystem": {
        #         "command": ["npx", "@modelcontextprotocol/server-filesystem"],
        #         "required_env": [],
        #         "tools": ["read_file", "write_file", "list_directory", "create_directory"]
        #     }
        # }
    
    async def initialize(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Initialize service and optionally user connections"""
        try:
            results = {"service_initialized": True}
            
            if user_id:
                # Initialize user connections
                connections = await self.mcp_conn.initialize_user_mcp_connections(user_id)
                results["user_connections"] = len(connections)
            
            return results
            
        except Exception as e:
            raise ExternalServiceException(
                f"MCP service initialization failed: {str(e)}",
                correlation_id=self.correlation_id,
                severity=ErrorSeverity.CRITICAL
            )
    
    async def discover_tools(self, user_id: Optional[str] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Discover all available MCP tools across connected servers.
        
        This method is essential for the workflow generation process as it:
        1. Identifies what tools are available for building workflows
        2. Provides tool metadata needed for step generation
        3. Enables dynamic workflow creation based on available capabilities
        
        Args:
            user_id: Optional user ID to get user-specific tools
            force_refresh: Whether to bypass cache and force fresh discovery
            
        Returns:
            List of tool information dictionaries containing:
            - name: Tool name
            - description: Tool description  
            - server_name: Source MCP server
            - parameters_schema: Parameter requirements
            - category: Tool category for organization
        """
        try:
            self.logger.info(f"Discovering MCP tools (user_id={user_id}, force_refresh={force_refresh})")
            
            discovered_tools = []
            
            if user_id:
                # Get tools specific to the user
                user_tools = await self.get_user_tools(user_id)
                for tool_dict in user_tools:
                    # Get full tool details from connection service
                    tools = await self.mcp_conn.get_connected_tools(user_id)
                    for tool in tools:
                        if tool.name == tool_dict["name"]:
                            discovered_tools.append({
                                "name": tool.name,
                                "description": tool.description or f"Tool from {tool_dict.get('server_name', 'unknown')} server",
                                "server_name": tool_dict.get("server_name", "unknown"),
                                "parameters_schema": self._extract_tool_schema(tool),
                                "category": tool_dict.get("category", "general"),
                                "discovered_at": datetime.utcnow().isoformat()
                            })
            else:
                # Get all available tools from operations service
                all_tool_infos = await self.mcp_ops.get_accessible_tools_for_user("system")  # System tools
                
                for tool_info in all_tool_infos:
                    discovered_tools.append({
                        "name": tool_info.name,
                        "description": tool_info.description,
                        "server_name": tool_info.server_name,
                        "parameters_schema": tool_info.parameters_schema or {},
                        "category": tool_info.category or "general",
                        "discovered_at": datetime.utcnow().isoformat()
                    })
            
            self.logger.info(f"Discovered {len(discovered_tools)} MCP tools")
            
            # Log tool summary for debugging
            servers = set(tool.get("server_name", "unknown") for tool in discovered_tools)
            self.logger.debug(f"Tools discovered from servers: {', '.join(servers)}")
            
            return discovered_tools
            
        except Exception as e:
            self.logger.error(f"Tool discovery failed: {e}")
            # Return empty list rather than raising to allow graceful degradation
            return []
    
    async def discover_tools_by_server(self, server_names: list[str], user_id: Optional[str] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Discover required tools by server name.
        
        This method is essential for the workflow generation process as it:
        1. Identifies what tools are available for building workflows by server name
        2. Provides tool metadata needed for step generation
        3. Enables dynamic workflow creation based on available capabilities by server name
        
        Args:
            server_names: List of server names to discover tools for
            user_id: Optional user ID to get user-specific tools
            force_refresh: Whether to bypass cache and force fresh discovery
            
        Returns:
            List of tool information dictionaries containing:
            - name: Tool name
            - description: Tool description  
            - server_name: Source MCP server
            - parameters_schema: Parameter requirements
            - category: Tool category for organization
        """
        try:
            self.logger.info(f"Discovering MCP tools for servers {server_names} (user_id={user_id}, force_refresh={force_refresh})")
            
            if not server_names:
                self.logger.warning("No server names provided for tool discovery")
                return []
            
            discovered_tools = []
            if user_id:
                tools = await self.mcp_conn.get_required_server_tools(user_id, server_names)
                
                # Extract tools from successful connections
                for tool in tools:
                    discovered_tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "parameters_schema": self._extract_tool_schema(tool),
                        "category": self._categorize_tool(tool.name),
                        "discovered_at": datetime.utcnow().isoformat(),
                        "connection_status": "connected"
                    })
            else:
                # For system-level discovery, get tools from operations service and filter by server names
                # TODO: we need to get the tools from the system MCP client tools
                # all_tool_infos = await self.mcp_ops.get_accessible_tools_for_user("system")
                
                # # Filter tools by requested server names
                # for tool_info in all_tool_infos:
                #     if tool_info.server_name in server_names:
                #         discovered_tools.append({
                #             "name": tool_info.name,
                #             "description": tool_info.description,
                #             "server_name": tool_info.server_name,
                #             "parameters_schema": tool_info.input_schema or {},
                #             "category": tool_info.category or "general",
                #             "discovered_at": datetime.utcnow().isoformat(),
                #             "connection_status": "system"
                #         })
                pass
            
            self.logger.info(f"Discovered {len(discovered_tools)} MCP tools from {len(server_names)} requested servers")

            return discovered_tools
            
        except Exception as e:
            self.logger.error(f"Tool discovery by server failed: {e}")
            return []
    
    async def validate_tool(self, tool_name: str, server_name: str, user_id: Optional[str] = None) -> bool:
        """
        Validate that a specific tool is available and functional.
        
        This is crucial for workflow reliability as it:
        1. Ensures tools exist before workflow execution
        2. Validates tool accessibility and permissions
        3. Prevents workflow failures due to missing tools
        
        Args:
            tool_name: Name of the tool to validate
            server_name: Server hosting the tool
            user_id: Optional user ID for user-specific validation
            
        Returns:
            True if tool is valid and accessible, False otherwise
        """
        try:
            self.logger.debug(f"Validating tool: {tool_name} on server: {server_name}")
            
            if user_id:
                # Validate user-specific tool access
                user_tools = await self.mcp_conn.get_connected_tools(user_id)
                tool_exists = any(tool.name == tool_name for tool in user_tools)
                
                if tool_exists:
                    # Try to get the tool and check if it's callable
                    tool = next((t for t in user_tools if t.name == tool_name), None)
                    if tool and hasattr(tool, 'args_schema'):
                        self.logger.debug(f"Tool {tool_name} validated successfully")
                        return True
                        
            else:
                # Validate system-level tool
                all_tools = await self.discover_tools()
                tool_exists = any(
                    tool["name"] == tool_name and tool["server_name"] == server_name 
                    for tool in all_tools
                )
                
                if tool_exists:
                    self.logger.debug(f"System tool {tool_name} validated successfully")
                    return True
            
            self.logger.warning(f"Tool validation failed: {tool_name} not found on {server_name}")
            return False
            
        except Exception as e:
            self.logger.error(f"Tool validation error for {tool_name}: {e}")
            return False
    
    async def execute_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any], 
        user_id: str,
        timeout: float = 30.0
    ) -> MCPToolExecutionResult:
        """
        Execute a specific MCP tool with given parameters.
        
        This is the core execution method that:
        1. Executes individual workflow steps
        2. Provides standardized result format
        3. Handles errors and timeouts gracefully
        4. Enables workflow automation
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            user_id: User executing the tool
            timeout: Execution timeout in seconds
            
        Returns:
            MCPToolExecutionResult with execution details
        """
        start_time = datetime.now()
        
        try:
            self.logger.info(f"Executing tool: {tool_name} for user: {user_id}")
            
            # Use the existing circuit breaker method
            result = await self.execute_tool_with_circuit_breaker(
                user_id=user_id,
                tool_name=tool_name,
                parameters=parameters
            )
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            if result.get("status") == "success":
                self.logger.info(f"Tool {tool_name} executed successfully in {execution_time:.2f}s")
                return MCPToolExecutionResult(
                    status="success",
                    data=result.get("data"),
                    execution_time=execution_time
                )
            else:
                self.logger.warning(f"Tool {tool_name} execution failed: {result.get('error')}")
                return MCPToolExecutionResult(
                    status="error",
                    error=result.get("error", "Unknown error"),
                    execution_time=execution_time
                )
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Tool execution failed: {str(e)}"
            self.logger.error(f"Tool {tool_name} execution error: {error_msg}")
            
            return MCPToolExecutionResult(
                status="error", 
                error=error_msg,
                execution_time=execution_time
            )
    
    def _extract_tool_schema(self, tool: BaseTool) -> Dict[str, Any]:
        """Extract parameter schema from a tool object."""
        try:
            # Handle different types of args_schema
            if hasattr(tool, 'args_schema') and tool.args_schema is not None:
                
                # Case 1: args_schema is already a dictionary (JSON schema)
                if isinstance(tool.args_schema, dict):
                    return tool.args_schema
                
                # Case 2: args_schema is a Pydantic model (BaseModel subclass)
                elif hasattr(tool.args_schema, 'model_json_schema'):
                    # Pydantic v2
                    return tool.args_schema.model_json_schema()
                elif hasattr(tool.args_schema, 'schema'):
                    # Pydantic v1
                    return tool.args_schema.schema()
                
                # Case 3: args_schema is a class type (need to get schema from tool)
                elif hasattr(tool, 'get_input_schema'):
                    input_schema = tool.get_input_schema()
                    if hasattr(input_schema, 'model_json_schema'):
                        return input_schema.model_json_schema()
                    elif hasattr(input_schema, 'schema'):
                        return input_schema.schema()
            
            # Case 4: Use tool's args property as fallback
            elif hasattr(tool, 'args') and tool.args:
                return {
                    "type": "object",
                    "properties": tool.args,
                    "required": []
                }
            
            # Case 5: Use tool's get_input_schema method as final fallback
            elif hasattr(tool, 'get_input_schema'):
                try:
                    input_schema = tool.get_input_schema()
                    if hasattr(input_schema, 'model_json_schema'):
                        return input_schema.model_json_schema()
                    elif hasattr(input_schema, 'schema'):
                        return input_schema.schema()
                except Exception as schema_error:
                    self.logger.warning(f"Failed to get input schema for tool {getattr(tool, 'name', 'unknown')}: {schema_error}")
            
            # Default empty schema
            return {"type": "object", "properties": {}}
            
        except Exception as e:
            self.logger.warning(f"Failed to extract schema from tool {getattr(tool, 'name', 'unknown')}: {e}")
            return {"type": "object", "properties": {}}

    async def get_available_servers_for_user(self, user_id: str) -> Dict[str, Any]:
        """Get servers available to user with predefined info"""
        servers_response = await self.mcp_ops.get_available_servers_for_user(user_id)
        
        # Enhance with predefined server information
        # for server_list in [servers_response.system_servers, servers_response.public_servers]:
        #     for server in server_list:
        #         if server.name in self.predefined_servers:
        #             predefined = self.predefined_servers[server.name]
        #             server.tools = predefined["tools"]
        #             server.required_env = predefined.get("required_env", [])
        
        return servers_response.dict()
    
    # async def setup_predefined_server(
    #     self, 
    #     user_id: str, 
    #     server_name: str, 
    #     env_vars: Dict[str, str]
    # ) -> str:
    #     """Setup a predefined server for user"""
    #     if server_name not in self.predefined_servers:
    #         raise ValueError(f"Unknown predefined server: {server_name}")
        
    #     predefined = self.predefined_servers[server_name]
        
    #     # Validate required environment variables
    #     missing = [var for var in predefined.get("required_env", []) if var not in env_vars]
    #     if missing:
    #         raise ValueError(f"Missing required environment variables: {missing}")
        
    #     # Create server input
    #     server_input = UserMCPServerInput(
    #         server_id=server_name,  # Will be resolved by domain service
    #         command=" ".join(predefined["command"]),
    #         env=env_vars
    #     )
        
    #     return await self.mcp_ops.setup_user_mcp_server(user_id, server_input)
    
    async def get_user_tools(self, user_id: str) -> List[Dict[str, Any]]:
        """Get tools available to user"""
        tools = await self.mcp_conn.get_connected_tools(user_id)
        
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "server_name": getattr(tool, 'server_name', 'unknown'),
                "category": self._categorize_tool(tool.name)
            }
            for tool in tools
        ]
    
    async def get_tools_by_server(self, server_names: list[str], user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tools available to user"""
        tools = await self.mcp_conn.get_connected_tools(user_id)
        
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "server_name": getattr(tool, 'server_name', 'unknown'),
                "category": self._categorize_tool(tool.name)
            }
            for tool in tools
            if tool.server_name in server_names
        ]
    
    async def execute_tool_with_circuit_breaker(
        self,
        user_id: str,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute tool with circuit breaker protection"""
        client = await self.mcp_conn.get_user_mcp_client(user_id)
        if not client:
            raise ValueError(f"No MCP client for user {user_id}")
        
        tools = client.get_tools()
        tool = next((t for t in tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")
        
        server_name = getattr(tool, 'server_name', 'unknown')
        
        async def execute_func():
            return await tool.ainvoke(parameters)
        
        try:
            result = await self.circuit_breaker.execute_with_fallback(server_name, execute_func)
            return {"status": "success", "data": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _categorize_tool(self, tool_name: str) -> str:
        """Categorize tool by name"""
        name_lower = tool_name.lower()
        if any(word in name_lower for word in ["file", "directory"]):
            return "filesystem"
        elif any(word in name_lower for word in ["github", "repo"]):
            return "version_control"
        elif any(word in name_lower for word in ["slack", "message"]):
            return "communication"
        return "general"