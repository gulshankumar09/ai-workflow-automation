"""
MCP Domain Entities

This module defines the domain entities for MCP servers, user MCP server instances,
and MCP tools based on the database schema.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

from app.shared.CustomBaseModel import CustomBaseModel
from .value_objects import AccessLevel, ServerStatus


class MCPServer(CustomBaseModel):
    """
    MCP Server entity representing the mcp_servers table
    """
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    access_level: AccessLevel
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def is_accessible_by_user(self, user_id: str, user_has_setup: bool = False) -> bool:
        """
        Check if this server is accessible by a user
        
        Args:
            user_id: User identifier
            user_has_setup: Whether user has setup this server
            
        Returns:
            True if accessible
        """
        if self.access_level == AccessLevel.SYSTEM:
            return True  # System servers can be used by anyone
        elif self.access_level == AccessLevel.PUBLIC:
            return True  # Public servers can be used by anyone by setting up
        elif self.access_level == AccessLevel.PRIVATE:
            return user_has_setup  # Private servers only for users who set them up
        
        return False
    
    def get_system_config(self) -> Optional[Dict[str, Any]]:
        """
        Get system configuration for system-level servers
        Only applicable for SYSTEM access level servers
        """
        if self.access_level != AccessLevel.SYSTEM:
            return None
        
        # This would typically come from a configuration service
        # For now, return a placeholder
        return {
            "command": ["npx", f"@modelcontextprotocol/server-{self.name}"],
            "args": [],
            "env": {},
            "timeout": 30.0,
            "max_retries": 3,
            "transport": "stdio"
        }
    
    class Config:
        use_enum_values = True


class UserMCPServer(CustomBaseModel):
    """
    User MCP Server instance entity representing the user_mcp_servers table
    """
    id: Optional[str] = None
    user_id: str
    server_id: str
    command: str
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    status: ServerStatus = ServerStatus.INACTIVE
    config: Optional[Dict[str, Any]] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Relations
    server: Optional[MCPServer] = None
    
    def get_connection_config(self) -> Dict[str, Any]:
        """
        Get configuration for MCP connection
        
        Returns:
            Configuration dictionary for LangGraph MCP adapter
        """
        return {
            "command": self.command,
            "args": self.args or [],
            "env": self.env or {},
            "timeout": self.config.get("timeout", 30.0) if self.config else 30.0,
            "max_retries": self.config.get("max_retries", 3) if self.config else 3,
            "transport": self.config.get("transport", "stdio") if self.config else "stdio",
        }
    
    def is_ready_for_connection(self) -> bool:
        """Check if this server instance is ready for connection"""
        return (
            self.is_active and 
            self.command and 
            len(self.command) > 0 and
            self.status in [ServerStatus.ACTIVE, ServerStatus.CONNECTED]
        )
    
    def update_status(self, new_status: ServerStatus, error_message: Optional[str] = None):
        """Update server status with timestamp"""
        self.status = new_status
        self.updated_at = datetime.utcnow()
        
        if error_message and self.config:
            self.config["last_error"] = error_message
            self.config["last_error_time"] = datetime.utcnow().isoformat()
    
    class Config:
        use_enum_values = True


class MCPTool(CustomBaseModel):
    """
    MCP Tool entity representing the mcp_tools table
    """
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    server_name: str
    server_id: str
    input_schema: Dict[str, Any]
    category: Optional[str] = None
    tags: List[str] = []
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Relations
    server: Optional[MCPServer] = None
    
    def is_accessible_by_user(self, user_id: str, user_server_instances: List[UserMCPServer]) -> bool:
        """
        Check if this tool is accessible by a user
        
        Args:
            user_id: User identifier
            user_server_instances: User's MCP server instances
            
        Returns:
            True if accessible
        """
        if not self.server:
            return False
        
        # Check if user has access to the server this tool belongs to
        if self.server.access_level == AccessLevel.SYSTEM:
            return True
        
        # For public and private servers, check if user has an active instance
        user_instance = next(
            (instance for instance in user_server_instances 
             if instance.server_id == self.server_id and instance.is_ready_for_connection()),
            None
        )
        
        return user_instance is not None
    
    def get_langchain_tool_schema(self) -> Dict[str, Any]:
        """
        Get tool schema in LangChain format
        
        Returns:
            Tool schema for LangChain integration
        """
        return {
            "name": self.name,
            "description": self.description or f"Tool from {self.server_name} server",
            "parameters": self.input_schema,
            "server_name": self.server_name,
            "category": self.category,
            "tags": self.tags
        }
    
    class Config:
        use_enum_values = True 