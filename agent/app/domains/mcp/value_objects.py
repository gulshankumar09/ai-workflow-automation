"""
MCP Domain Value Objects

This module defines value objects for the MCP domain, including access levels,
server status, and configuration objects.
"""

from builtins import ValueError
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field, validator
from langchain_core.tools import BaseTool


class AccessLevel(str, Enum):
    """Access levels for MCP servers"""
    SYSTEM = "system"    # Can be used by anyone using system config
    PUBLIC = "public"    # Can be used by any user by setting up MCP connections
    PRIVATE = "private"  # Can only be used by users who have set it up


class ServerStatus(str, Enum):
    """Status of MCP server instances"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    CONNECTED = "connected"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration for MCP server initialization"""
    command: List[str]
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    timeout: float = 30.0
    max_retries: int = 3
    transport: str = "stdio"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LangGraph MCP adapter"""
        return {
            "command": self.command,
            "args": self.args or [],
            "env": self.env or {},
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "transport": self.transport,
        }


class UserMCPServerInput(BaseModel):
    """Input model for creating user MCP server instances"""
    server_id: str = Field(..., description="MCP server ID")
    command: List[str] = Field(..., description="Command to run the server")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    config: Optional[Dict[str, Any]] = Field(None, description="Additional configuration")
    
    @validator('command')
    def validate_command(cls, v):
        if not v or len(v) == 0:
            raise ValueError("Command cannot be empty")
        return v


class MCPServerInfo(BaseModel):
    """Information about available MCP servers for a user"""
    id: str
    name: str
    description: Optional[str]
    access_level: AccessLevel
    is_setup: bool = False  # Whether user has setup this server
    is_active: bool = False  # Whether server instance is active
    status: Optional[ServerStatus] = None
    tools_count: int = 0
    required_config: Optional[Dict[str, Any]] = None
    
    class Config:
        use_enum_values = True


class MCPConnectionResult(BaseModel):
    """Result of MCP connection attempt"""
    server_name: str
    success: bool
    error_message: Optional[str] = None
    tools_discovered: int = 0
    tools: List[BaseTool] = Field(default_factory=list)
    connection_time: Optional[float] = None
    status: ServerStatus = ServerStatus.INACTIVE
    
    class Config:
        use_enum_values = True


class UserMCPServersResponse(BaseModel):
    """Response containing user's available MCP servers"""
    user_id: str
    servers: List[MCPServerInfo] = Field(default_factory=list)
    total_count: int = 0
    active_connections: int = 0
    
    def model_post_init(self, __context: Any) -> None:
        """Calculate totals after initialization"""
        self.total_count = len(self.servers)
        self.active_connections = sum(
            1 for servers in [self.servers]
            for server in servers if server.is_active
        )


class MCPToolInfo(BaseModel):
    """Information about MCP tools"""
    id: str
    name: str
    description: Optional[str]
    server_name: str
    server_id: str
    input_schema: Dict[str, Any]
    category: Optional[str]
    tags: List[str] = Field(default_factory=list)
    is_active: bool = True 