"""
MCP Domain Repositories

This module defines repository interfaces and implementations for MCP entities
using the existing database provider patterns.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from app.shared.logger import get_logger

from app.infrastructure.database.providers.factory import DatabaseProviderFactory
from app.shared.exceptions import DatabaseException, NotFoundException, ValidationException
from .entities import MCPServer, UserMCPServer, MCPTool
from .value_objects import AccessLevel, ServerStatus

logger = get_logger(__name__)


class MCPServerRepository(ABC):
    """Repository interface for MCP Server entities"""
    
    @abstractmethod
    async def find_all(self) -> List[MCPServer]:
        """Get all MCP servers"""
        pass
    
    @abstractmethod
    async def find_by_id(self, server_id: str) -> Optional[MCPServer]:
        """Find MCP server by ID"""
        pass
    
    @abstractmethod
    async def find_by_access_level(self, access_level: AccessLevel) -> List[MCPServer]:
        """Find MCP servers by access level"""
        pass
    
    @abstractmethod
    async def create(self, server: MCPServer) -> str:
        """Create a new MCP server"""
        pass


class UserMCPServerRepository(ABC):
    """Repository interface for User MCP Server entities"""
    
    @abstractmethod
    async def find_by_user_id(self, user_id: str) -> List[UserMCPServer]:
        """Find all user MCP server instances for a user"""
        pass
    
    @abstractmethod
    async def find_by_user_and_server(self, user_id: str, server_id: str) -> Optional[UserMCPServer]:
        """Find user MCP server instance by user and server"""
        pass
    
    @abstractmethod
    async def find_active_by_user(self, user_id: str) -> List[UserMCPServer]:
        """Find active user MCP server instances"""
        pass
    
    @abstractmethod
    async def create(self, user_server: UserMCPServer) -> str:
        """Create a new user MCP server instance"""
        pass
    
    @abstractmethod
    async def update(self, user_server: UserMCPServer) -> bool:
        """Update user MCP server instance"""
        pass
    
    @abstractmethod
    async def update_status(self, instance_id: str, status: ServerStatus, error_message: Optional[str] = None) -> bool:
        """Update server instance status"""
        pass


class MCPToolRepository(ABC):
    """Repository interface for MCP Tool entities"""
    
    @abstractmethod
    async def find_by_server_id(self, server_id: str) -> List[MCPTool]:
        """Find tools by server ID"""
        pass
    
    @abstractmethod
    async def find_active_tools(self) -> List[MCPTool]:
        """Find all active tools"""
        pass
    
    @abstractmethod
    async def bulk_create_or_update(self, tools: List[MCPTool]) -> bool:
        """Bulk create or update tools"""
        pass


# Supabase Implementations

class SupabaseMCPServerRepository(MCPServerRepository):
    """Supabase implementation of MCP Server repository"""
    
    def __init__(self, database_factory: DatabaseProviderFactory, correlation_id: str = None):
        self.database = database_factory.create_provider()
        self.correlation_id = correlation_id
    
    async def find_all(self) -> List[MCPServer]:
        """Get all MCP servers"""
        try:
            result = await self.database.select(
                table="mcp_servers",
                order_by={"created_at": "desc"}
            )
            
            return [MCPServer(**row) for row in result.get("data", [])]
            
        except Exception as e:
            logger.error("Failed to fetch MCP servers", error=str(e), correlation_id=self.correlation_id)
            raise DatabaseException(f"Failed to fetch MCP servers: {str(e)}")
    
    async def find_by_id(self, server_id: str) -> Optional[MCPServer]:
        """Find MCP server by ID"""
        result = await self.database.select(
            table="mcp_servers",
            filters={"id": server_id},
            limit=1
        )
        
        data = result.get("data", [])
        return MCPServer(**data[0]) if data else None
    
    async def find_by_access_level(self, access_level: AccessLevel) -> List[MCPServer]:
        """Find MCP servers by access level"""
        result = await self.database.select(
            table="mcp_servers",
            filters={"access_level": access_level.value},
            order_by= {"name": "asc"}
        )
        
        return [MCPServer(**row) for row in result.get("data", [])]
    
    async def create(self, server: MCPServer) -> str:
        """Create a new MCP server"""
        try:
            server_data = server.dict(exclude={"id", "created_at", "updated_at"})
            
            result = await self.database.insert(
                table="mcp_servers",
                data=server_data
            )
            
            data = result.get("data", [])
            if not data:
                raise DatabaseException("No data returned from server creation")
                
            return data[0]["id"]
            
        except Exception as e:
            logger.error("Failed to create MCP server", server_name=server.name, error=str(e))
            raise DatabaseException(f"Failed to create MCP server: {str(e)}")


class SupabaseUserMCPServerRepository(UserMCPServerRepository):
    """Supabase implementation of User MCP Server repository"""
    
    def __init__(self, database_factory: DatabaseProviderFactory, correlation_id: str = None):
        self.database = database_factory.create_provider()
        self.correlation_id = correlation_id
    
    async def find_by_user_id(self, user_id: str) -> List[UserMCPServer]:
        """Find all user MCP server instances for a user"""
        try:
            result = await self.database.select(
                table="user_mcp_servers",
                filters={"user_id": user_id},
                order_by={"created_at": "desc"}
            )
            
            return [UserMCPServer(**row) for row in result.get("data", [])]
            
        except Exception as e:
            logger.error("Failed to fetch user MCP servers", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to fetch user MCP servers: {str(e)}")
    
    async def find_by_user_and_server(self, user_id: str, server_id: str) -> Optional[UserMCPServer]:
        """Find user MCP server instance by user and server"""
        try:
            result = await self.database.select(
                table="user_mcp_servers",
                columns=["*"],
                filters={"user_id": user_id, "server_id": server_id},
                limit=1
            )
            
            data = result.get("data", [])
            return UserMCPServer(**data[0]) if data else None
            
        except Exception as e:
            logger.error("Failed to fetch user MCP server instance", user_id=user_id, server_id=server_id, error=str(e))
            raise DatabaseException(f"Failed to fetch user MCP server instance: {str(e)}")
    
    async def find_active_by_user(self, user_id: str) -> List[UserMCPServer]:
        """Find active user MCP server instances"""
        try:
            result = await self.database.select(
                table="user_mcp_servers",
                filters={
                    "user_id": user_id,
                    "is_active": True,
                    "status": ServerStatus.ACTIVE.value
                },
                order_by= {"updated_at": "desc"}
            )
            
            return [UserMCPServer(**row) for row in result.get("data", [])]
            
        except Exception as e:
            logger.error("Failed to fetch active user MCP servers", user_id=user_id, error=str(e))
            raise DatabaseException(f"Failed to fetch active user MCP servers: {str(e)}")
    
    async def create(self, user_server: UserMCPServer) -> str:
        """Create a new user MCP server instance"""
        try:
            server_data = user_server.dict(exclude={"id", "created_at", "updated_at", "server"})
            
            result = await self.database.insert(
                table="user_mcp_servers",
                data=server_data
            )
            
            data = result.get("data", [])
            if not data:
                raise DatabaseException("No data returned from user server creation")
                
            return data[0]["id"]
            
        except Exception as e:
            logger.error("Failed to create user MCP server", user_id=user_server.user_id, error=str(e))
            raise DatabaseException(f"Failed to create user MCP server: {str(e)}")
    
    async def update(self, user_server: UserMCPServer) -> bool:
        """Update user MCP server instance"""
        try:
            if not user_server.id:
                raise ValidationException("User server ID is required for update")
            
            update_data = user_server.dict(exclude={"id", "created_at", "server"})
            update_data["updated_at"] = "NOW()"
            
            result = await self.database.update(
                table="user_mcp_servers",
                data=update_data,
                filters={"id": user_server.id}
            )
            
            return len(result.get("data", [])) > 0
            
        except Exception as e:
            logger.error("Failed to update user MCP server", instance_id=user_server.id, error=str(e))
            raise DatabaseException(f"Failed to update user MCP server: {str(e)}")
    
    async def update_status(self, instance_id: str, status: ServerStatus, error_message: Optional[str] = None) -> bool:
        """Update server instance status"""
        try:
            update_data = {
                "status": status.value,
                "updated_at": "NOW()"
            }
            
            # Add error information to config if provided
            if error_message:
                # We need to get current config first, then update it
                current = await self.database.select(
                    table="user_mcp_servers",
                    columns=["config"],
                    filters={"id": instance_id},
                    limit=1
                )
                
                current_config = current.get("data", [{}])[0].get("config", {}) or {}
                current_config["last_error"] = error_message
                current_config["last_error_time"] = "NOW()"
                update_data["config"] = current_config
            
            result = await self.database.update(
                table="user_mcp_servers",
                data=update_data,
                filters={"id": instance_id}
            )
            
            return len(result.get("data", [])) > 0
            
        except Exception as e:
            logger.error("Failed to update server status", instance_id=instance_id, status=status, error=str(e))
            raise DatabaseException(f"Failed to update server status: {str(e)}")


class SupabaseMCPToolRepository(MCPToolRepository):
    """Supabase implementation of MCP Tool repository"""
    
    def __init__(self, database_factory: DatabaseProviderFactory, correlation_id: str = None):
        self.database = database_factory.create_provider()
        self.correlation_id = correlation_id
    
    async def find_by_server_id(self, server_id: str) -> List[MCPTool]:
        """Find tools by server ID"""
        try:
            result = await self.database.select(
                table="mcp_tools",
                columns=["*"],
                filters={"server_id": server_id, "is_active": True},
                order_by=[("name", "asc")]
            )
            
            return [MCPTool(**row) for row in result.get("data", [])]
            
        except Exception as e:
            logger.error("Failed to fetch tools by server ID", server_id=server_id, error=str(e))
            raise DatabaseException(f"Failed to fetch tools: {str(e)}")
    
    async def find_active_tools(self) -> List[MCPTool]:
        """Find all active tools"""
        try:
            result = await self.database.select(
                table="mcp_tools",
                filters={"is_active": True},
                order_by={"server_name": "asc", "name": "asc"}
            )
            
            return [MCPTool(**row) for row in result.get("data", [])]
            
        except Exception as e:
            logger.error("Failed to fetch active tools", error=str(e))
            raise DatabaseException(f"Failed to fetch active tools: {str(e)}")
    
    async def bulk_create_or_update(self, tools: List[MCPTool]) -> bool:
        """Bulk create or update tools"""
        try:
            # For simplicity, we'll delete existing tools for the servers and recreate
            # In production, you might want a more sophisticated upsert logic
            
            if not tools:
                return True
            
            server_ids = list(set(tool.server_id for tool in tools))
            
            # Delete existing tools for these servers
            for server_id in server_ids:
                await self.database.delete(
                    table="mcp_tools",
                    filters={"server_id": server_id}
                )
            
            # Insert new tools
            tools_data = [
                tool.dict(exclude={"id", "created_at", "updated_at", "server"})
                for tool in tools
            ]
            
            if tools_data:
                await self.database.insert(
                    table="mcp_tools",
                    data=tools_data
                )
            
            return True
            
        except Exception as e:
            logger.error("Failed to bulk create/update tools", tools_count=len(tools), error=str(e))
            raise DatabaseException(f"Failed to bulk create/update tools: {str(e)}")


# Factory for creating repositories
class MCPRepositoryFactory:
    """Factory for creating MCP repositories"""
    
    def __init__(self, database_factory: DatabaseProviderFactory, correlation_id: str = None):
        self.database_factory = database_factory
        self.correlation_id = correlation_id
    
    def create_server_repository(self) -> MCPServerRepository:
        """Create MCP server repository"""
        return SupabaseMCPServerRepository(self.database_factory, self.correlation_id)
    
    def create_user_server_repository(self) -> UserMCPServerRepository:
        """Create user MCP server repository"""
        return SupabaseUserMCPServerRepository(self.database_factory, self.correlation_id)
    
    def create_tool_repository(self) -> MCPToolRepository:
        """Create MCP tool repository"""
        return SupabaseMCPToolRepository(self.database_factory, self.correlation_id) 