"""
MCP Domain Services

This module contains the business logic for MCP operations including:
- MCP server discovery and management
- User MCP server instance management  
- MCP connection management using LangGraph adapters
- Tool discovery and access control
"""

import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple
from app.shared import get_logger

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from langchain_core.tools import BaseTool

from app.shared.exceptions import (
    ValidationException,
    NotFoundException,
    ExternalServiceException,
    MCPToolError,
    ErrorSeverity
)
from app.infrastructure.database.providers.factory import DatabaseProviderFactory
from app.infrastructure.cache.factory import CacheProviderFactory

from .entities import MCPServer, UserMCPServer, MCPTool
from .repositories import MCPRepositoryFactory
from .value_objects import (
    AccessLevel, 
    ServerStatus, 
    MCPServerConfig,
    UserMCPServerInput,
    MCPServerInfo,
    MCPConnectionResult,
    UserMCPServersResponse,
    MCPToolInfo
)

logger = get_logger(__name__)


class MCPOperationsService:
    """
    Core service for MCP operations including server discovery and user management
    """
    
    def __init__(
        self,
        database_factory: Optional[DatabaseProviderFactory] = None,
        cache_factory: Optional[CacheProviderFactory] = None,
        correlation_id: Optional[str] = None
    ):
        self.database_factory = database_factory or DatabaseProviderFactory()
        self.cache_factory = cache_factory or CacheProviderFactory()
        self.correlation_id = correlation_id or str(uuid.uuid4())
        
        # Initialize repositories
        self.repo_factory = MCPRepositoryFactory(self.database_factory, self.correlation_id)
        self.server_repo = self.repo_factory.create_server_repository()
        self.user_server_repo = self.repo_factory.create_user_server_repository()
        self.tool_repo = self.repo_factory.create_tool_repository()
        
        # Cache for frequently accessed data
        self.cache = self.cache_factory.create_provider()
        self._cache_ttl = 300  # 5 minutes
    
    async def get_available_servers_for_user(self, user_id: str) -> UserMCPServersResponse:
        """
        Get all available MCP servers for a user based on access levels
        
        Requirements:
        1. Private servers: Only those setup by the user
        2. System servers: All system-level servers (available to everyone)
        3. Public servers: All public servers (user can setup)
        4. Under server: List of all the servers that are under the user's control
        
        Args:
            user_id: User identifier
            
        Returns:
            UserMCPServersResponse with categorized servers
        """
        try:
            # Get user's MCP server instances
            user_instances = await self.user_server_repo.find_by_user_id(user_id)
            user_server_map = {instance.server_id: instance for instance in user_instances}
            
            # Get all MCP servers
            all_servers = await self.server_repo.find_all()
            
            # Get tools count for each server
            tools_by_server = await self._get_tools_count_by_server()
            
            # Categorize servers
            servers = []
            
            for server in all_servers:
                tools_count = tools_by_server.get(server.id, 0)
                user_instance = user_server_map.get(server.id)
                
                server_info = MCPServerInfo(
                    id=server.id,
                    name=server.name,
                    description=server.description,
                    access_level=server.access_level,
                    is_setup=user_instance is not None,
                    is_active=user_instance.is_ready_for_connection() if user_instance else False,
                    status=user_instance.status if user_instance else None,
                    tools_count=tools_count,
                    required_config=self._get_required_config_for_server(server)
                )
                servers.append(server_info)
            
            return UserMCPServersResponse(
                user_id=user_id,
                servers=servers
            )
            
        except Exception as e:
            logger.error("Failed to get available servers for user", user_id=user_id, error=str(e))
            raise ExternalServiceException(
                f"Failed to get available servers: {str(e)}",
                correlation_id=self.correlation_id
            )
    
    async def setup_user_mcp_server(self, user_id: str, server_input: UserMCPServerInput) -> str:
        """
        Setup a new MCP server instance for a user
        
        Args:
            user_id: User identifier
            server_input: Server configuration input
            
        Returns:
            Created instance ID
        """
        try:
            # Validate server exists and is accessible
            server = await self.server_repo.find_by_id(server_input.server_id)
            if not server:
                raise NotFoundException(f"MCP server not found: {server_input.server_id}")
            
            # Check if user can setup this server
            if not server.is_accessible_by_user(user_id):
                raise ValidationException(f"User cannot setup server with access level: {server.access_level}")
            
            # Check if user already has this server setup
            existing = await self.user_server_repo.find_by_user_and_server(user_id, server_input.server_id)
            if existing:
                raise ValidationException(f"User already has server setup: {server.name}")
            
            # Create user server instance
            user_server = UserMCPServer(
                user_id=user_id,
                server_id=server_input.server_id,
                command=server_input.command,
                args=server_input.args,
                env=server_input.env,
                config=server_input.config,
                status=ServerStatus.INACTIVE,
                server=server
            )
            
            instance_id = await self.user_server_repo.create(user_server)
            
            logger.info("User MCP server setup completed", 
                       user_id=user_id, server_name=server.name, instance_id=instance_id)
            
            return instance_id
            
        except Exception as e:
            logger.error("Failed to setup user MCP server", user_id=user_id, error=str(e))
            if isinstance(e, (ValidationException, NotFoundException)):
                raise
            raise ExternalServiceException(
                f"Failed to setup MCP server: {str(e)}",
                correlation_id=self.correlation_id
            )
    
    async def get_user_mcp_servers_setup(self, user_id: str) -> List[UserMCPServer]:
        """
        Get all MCP servers setup by a user
        
        Args:
            user_id: User identifier
            
        Returns:
            List of user MCP server instances
        """
        try:
            user_instances = await self.user_server_repo.find_by_user_id(user_id)
            
            # Load server details for each instance
            for instance in user_instances:
                if not instance.server:
                    server = await self.server_repo.find_by_id(instance.server_id)
                    instance.server = server
            
            return user_instances
            
        except Exception as e:
            logger.error("Failed to get user MCP servers setup", user_id=user_id, error=str(e))
            raise ExternalServiceException(
                f"Failed to get user MCP servers: {str(e)}",
                correlation_id=self.correlation_id
            )
    
    async def update_user_server_status(
        self, 
        instance_id: str, 
        status: ServerStatus, 
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update status of a user MCP server instance
        
        Args:
            instance_id: Server instance ID
            status: New status
            error_message: Optional error message
            
        Returns:
            True if updated successfully
        """
        try:
            return await self.user_server_repo.update_status(instance_id, status, error_message)
            
        except Exception as e:
            logger.error("Failed to update user server status", instance_id=instance_id, error=str(e))
            raise ExternalServiceException(
                f"Failed to update server status: {str(e)}",
                correlation_id=self.correlation_id
            )
    
    async def get_accessible_tools_for_user(self, user_id: str) -> List[MCPToolInfo]:
        """
        Get all MCP tools accessible to a user based on their server setup
        
        Args:
            user_id: User identifier
            
        Returns:
            List of accessible tools
        """
        try:
            # Get user server instances
            user_instances = await self.user_server_repo.find_by_user_id(user_id)
            
            # Get all active tools
            all_tools = await self.tool_repo.find_active_tools()
            
            # Filter tools based on user access
            accessible_tools = []
            
            for tool in all_tools:
                if tool.is_accessible_by_user(user_id, user_instances):
                    tool_info = MCPToolInfo(
                        id=tool.id,
                        name=tool.name,
                        description=tool.description,
                        server_name=tool.server_name,
                        server_id=tool.server_id,
                        input_schema=tool.input_schema,
                        category=tool.category,
                        tags=tool.tags,
                        is_active=tool.is_active
                    )
                    accessible_tools.append(tool_info)
            
            return accessible_tools
            
        except Exception as e:
            logger.error("Failed to get accessible tools for user", user_id=user_id, error=str(e))
            raise ExternalServiceException(
                f"Failed to get accessible tools: {str(e)}",
                correlation_id=self.correlation_id
            )
    
    async def _get_tools_count_by_server(self) -> Dict[str, int]:
        """Get tools count grouped by server ID"""
        try:
            # Use cache if available
            cache_key = "mcp_tools_count_by_server"
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
            
            tools = await self.tool_repo.find_active_tools()
            tools_count = {}
            
            for tool in tools:
                tools_count[tool.server_id] = tools_count.get(tool.server_id, 0) + 1
            
            # Cache the result
            await self.cache.set(cache_key, tools_count, ttl=self._cache_ttl)
            
            return tools_count
            
        except Exception as e:
            logger.warning("Failed to get tools count by server", error=str(e))
            return {}
    
    def _get_required_config_for_server(self, server: MCPServer) -> Optional[Dict[str, Any]]:
        """Get required configuration fields for a server"""
        # This would typically come from server metadata or configuration
        # For now, return basic structure
        if server.access_level == AccessLevel.SYSTEM:
            return None  # System servers don't require user config
        
        return {
            "command": {"required": True, "type": "array", "description": "Command to run the server"},
            "args": {"required": False, "type": "array", "description": "Command arguments"},
            "env": {"required": False, "type": "object", "description": "Environment variables"},
        }


class MCPConnectionService:
    """
    Service for managing MCP connections using LangGraph adapters
    """
    
    def __init__(
        self,
        database_factory: Optional[DatabaseProviderFactory] = None,
        correlation_id: Optional[str] = None
    ):
        self.database_factory = database_factory or DatabaseProviderFactory()
        self.correlation_id = correlation_id or str(uuid.uuid4())
        
        # Initialize repositories
        self.repo_factory = MCPRepositoryFactory(self.database_factory, self.correlation_id)
        self.server_repo = self.repo_factory.create_server_repository()
        self.user_server_repo = self.repo_factory.create_user_server_repository()
        self.tool_repo = self.repo_factory.create_tool_repository()
        
        # MCP client instances
        self._mcp_clients: Dict[str, MultiServerMCPClient] = {}
        self._connection_locks: Dict[str, asyncio.Lock] = {}
    
    async def initialize_user_mcp_connections(self, user_id: str) -> Dict[str, MCPConnectionResult]:
        """
        Initialize MCP connections for a user's setup servers
        
        Uses LangGraph MCP adapter to establish connections
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary of connection results by server name
        """
        try:
            # Get user's active server instances
            user_instances = await self.user_server_repo.find_active_by_user(user_id)
            
            if not user_instances:
                logger.info("No active MCP servers found for user", user_id=user_id)
                return {}
            
            # Also get system servers that user can access
            system_servers = await self.server_repo.find_by_access_level(AccessLevel.SYSTEM)
            
            # Build server configurations
            server_configs = {}
            
            # Add user-configured servers
            for instance in user_instances:
                if not instance.server:
                    instance.server = await self.server_repo.find_by_id(instance.server_id)
                
                if instance.is_ready_for_connection():
                    server_configs[instance.server.name] = instance.get_connection_config()
            
            # Add system servers with default configs
            for server in system_servers:
                if server.name not in server_configs:  # Don't override user configs
                    system_config = server.get_system_config()
                    if system_config:
                        server_configs[server.name] = system_config
            
            if not server_configs:
                logger.warning("No valid server configurations found", user_id=user_id)
                return {}
            
            # Initialize MCP client with all configurations
            connection_results = await self._initialize_mcp_client(user_id, server_configs)
            
            # Update server statuses based on connection results
            await self._update_connection_statuses(user_instances, connection_results)
            
            # Discover and cache tools from connected servers
            await self._discover_and_cache_tools(user_id, connection_results)
            
            return connection_results
            
        except Exception as e:
            logger.error("Failed to initialize MCP connections", user_id=user_id, error=str(e))
            raise ExternalServiceException(
                f"Failed to initialize MCP connections: {str(e)}",
                correlation_id=self.correlation_id,
                severity=ErrorSeverity.HIGH
            )

    async def get_user_mcp_client(self, user_id: str) -> Optional[MultiServerMCPClient]:
        """
        Get the MCP client instance for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            MCP client instance or None
        """
        return self._mcp_clients.get(user_id)
    
    async def disconnect_user_mcp_connections(self, user_id: str) -> bool:
        """
        Disconnect MCP connections for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            True if disconnected successfully
        """
        if user_id in self._mcp_clients:
            client = self._mcp_clients[user_id]
            await client.__aexit__()
            del self._mcp_clients[user_id]
            
            if user_id in self._connection_locks:
                del self._connection_locks[user_id]
            
            logger.info("MCP connections disconnected", user_id=user_id)
            return True
        
        return False
    
    async def get_connected_tools(self, user_id: str) -> List[BaseTool]:
        """
        Get LangChain tools from connected MCP servers
        
        Args:
            user_id: User identifier
            
        Returns:
            List of LangChain BaseTool instances
        """
        try:
            client = self._mcp_clients.get(user_id)
            if not client:
                return []
            
            # Get tools from MCP client
            tools = await client.get_tools()
            return tools
            
        except Exception as e:
            logger.error("Failed to get connected tools", user_id=user_id, error=str(e))
            raise MCPToolError(
                f"Failed to get connected tools: {str(e)}",
                correlation_id=self.correlation_id
            )

    async def get_required_server_tools(
        self, 
        user_id: str, 
        required_servers: List[str]
    ) -> list[BaseTool]:
        """
        Initialize and get tools from MCP connections for only the required servers
        
        This method allows selective initialization of specific MCP servers
        instead of all available servers for a user.
        
        Args:
            user_id: User identifier
            required_servers: List of server names to initialize (e.g., ["github", "slack"])
            
        Returns:
            Dictionary of tools by server name for required servers
        """
        try:
            if not required_servers:
                logger.warning("No required servers specified", user_id=user_id)
                return {}
            
            # Get user's active server instances
            user_instances = await self.user_server_repo.find_active_by_user(user_id)
            
            # Get system servers that user can access
            system_servers = await self.server_repo.find_by_access_level(AccessLevel.SYSTEM)
            
            # Build server configurations for only required servers
            server_configs = {}
            found_servers = set()
            
            # Check user-configured servers first
            for instance in user_instances:
                if not instance.server:
                    instance.server = await self.server_repo.find_by_id(instance.server_id)
                
                if (instance.server and 
                    instance.server.name in required_servers and 
                    instance.is_ready_for_connection()):
                    server_configs[instance.server.name] = instance.get_connection_config()
                    found_servers.add(instance.server.name)
            
            # Check system servers for remaining required servers
            for server in system_servers:
                if (server.name in required_servers and 
                    server.name not in found_servers):
                    system_config = server.get_system_config()
                    if system_config:
                        server_configs[server.name] = system_config
                        found_servers.add(server.name)
            
            # Log missing servers
            missing_servers = set(required_servers) - found_servers
            if missing_servers:
                logger.warning(
                    "Some required servers not found or not configured", 
                    user_id=user_id, 
                    missing_servers=list(missing_servers),
                    found_servers=list(found_servers)
                )
            
            if not server_configs:
                logger.warning("No valid configurations found for required servers", 
                             user_id=user_id, required_servers=required_servers)
                return {}
            
            # Initialize MCP client with only required server configurations
            client = await self._initialize_mcp_client(user_id, server_configs)

            # Get tools from MCP client
            tools = await client.get_tools()
            
            # Convert to MCP tools and group by server
            mcp_tools_by_server = {}
            
            logger.info(
                "Required MCP connections initialized", 
                user_id=user_id, 
                required_servers=required_servers,
                tool_count=len(tools)
            )
            
            return tools
            
        except Exception as e:
            logger.error(
                "Failed to initialize required MCP connections", 
                user_id=user_id, 
                required_servers=required_servers, 
                error=str(e)
            )
            raise ExternalServiceException(
                f"Failed to initialize required MCP connections: {str(e)}",
                correlation_id=self.correlation_id,
                severity=ErrorSeverity.HIGH
            )

    async def _initialize_mcp_client(
        self, 
        user_id: str, 
        server_configs: Dict[str, Dict[str, Any]]
    ) -> MultiServerMCPClient:
        """Initialize MCP client with server configurations"""
        
        # Ensure thread-safe initialization
        if user_id not in self._connection_locks:
            self._connection_locks[user_id] = asyncio.Lock()
        
        async with self._connection_locks[user_id]:
            try:
                # Disconnect existing client if any
                await self.disconnect_user_mcp_connections(user_id)
                
                # Create new MCP client
                client = MultiServerMCPClient(server_configs)

                # Store client
                self._mcp_clients[user_id] = client
                
                return client
                
            except Exception as e:
                # Return error results for all servers
                return {
                    name: MCPConnectionResult(
                        server_name=name,
                        success=False,
                        error_message=str(e),
                        status=ServerStatus.ERROR
                    )
                    for name in server_configs.keys()
                }
    
    async def _update_connection_statuses(
        self, 
        user_instances: List[UserMCPServer], 
        connection_results: Dict[str, MCPConnectionResult]
    ):
        """Update server instance statuses based on connection results"""
        
        for instance in user_instances:
            if instance.server and instance.server.name in connection_results:
                result = connection_results[instance.server.name]
                await self.user_server_repo.update_status(
                    instance.id, 
                    result.status,
                    result.error_message
                )
    
    async def _discover_and_cache_tools(
        self, 
        user_id: str, 
        connection_results: Dict[str, MCPConnectionResult]
    ):
        """Discover tools from connected servers and cache them"""
        
        try:
            client = self._mcp_clients.get(user_id)
            if not client:
                return
            
            # Get all tools from connected servers
            langchain_tools = client.get_tools()
            
            # Convert to MCP tools and group by server
            mcp_tools_by_server = {}
            
            for tool in langchain_tools:
                server_name = getattr(tool, 'server_name', 'unknown')
                
                # Find server ID
                server_id = None
                for result in connection_results.values():
                    if result.server_name == server_name and result.success:
                        # We need to look up server ID from database
                        servers = await self.server_repo.find_all()
                        server = next((s for s in servers if s.name == server_name), None)
                        if server:
                            server_id = server.id
                        break
                
                if server_id:
                    if server_id not in mcp_tools_by_server:
                        mcp_tools_by_server[server_id] = []
                    
                    # Create MCP tool entity
                    mcp_tool = MCPTool(
                        name=tool.name,
                        description=tool.description,
                        server_name=server_name,
                        server_id=server_id,
                        input_schema=getattr(tool, 'args_schema', {}) or {},
                        category=self._categorize_tool(tool.name),
                        tags=getattr(tool, 'tags', []) or []
                    )
                    mcp_tools_by_server[server_id].append(mcp_tool)
            
            # Bulk update tools in database
            all_tools = []
            for tools in mcp_tools_by_server.values():
                all_tools.extend(tools)
            
            if all_tools:
                await self.tool_repo.bulk_create_or_update(all_tools)
                logger.info("Tools discovered and cached", user_id=user_id, tools_count=len(all_tools))
            
        except Exception as e:
            logger.warning("Failed to discover and cache tools", user_id=user_id, error=str(e))
    
    def _categorize_tool(self, tool_name: str) -> Optional[str]:
        """Categorize tool based on name patterns"""
        name_lower = tool_name.lower()
        
        if any(keyword in name_lower for keyword in ['file', 'read', 'write', 'directory']):
            return 'filesystem'
        elif any(keyword in name_lower for keyword in ['slack', 'message', 'channel']):
            return 'communication'
        elif any(keyword in name_lower for keyword in ['github', 'git', 'repo']):
            return 'version_control'
        elif any(keyword in name_lower for keyword in ['database', 'query', 'table']):
            return 'database'
        else:
            return 'general' 