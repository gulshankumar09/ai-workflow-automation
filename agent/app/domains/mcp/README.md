# MCP Domain - Model Context Protocol Operations

This document describes the MCP (Model Context Protocol) domain implementation that provides comprehensive MCP server management with user-based access control and LangGraph adapter integration.

## Overview

The MCP domain handles:

- **MCP Server Discovery**: Finding available MCP servers based on access levels
- **User Server Management**: Setting up and managing user-specific MCP server instances
- **Connection Management**: Using LangGraph MCP adapters for reliable connections
- **Tool Discovery**: Real-time tool discovery and access control
- **Access Level Control**: System, Public, and Private server access management

## Architecture

```
📦 MCP Domain
├── 🏗️ entities.py          # Domain entities (MCPServer, UserMCPServer, MCPTool)
├── 📋 value_objects.py      # Value objects and enums (AccessLevel, ServerStatus)
├── 🗄️ repositories.py       # Repository interfaces and implementations
├── ⚙️ services.py           # Business logic services
├── 🔧 __init__.py          # Domain package exports
└── 📚 README.md            # This documentation
```

## Database Schema

The implementation is based on these database tables:

### 1. `mcp_servers` - MCP Server Definitions

```sql
CREATE TABLE mcp_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    access_level VARCHAR(20) NOT NULL CHECK (access_level IN ('system', 'public', 'private')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 2. `user_mcp_servers` - User MCP Server Instances

```sql
CREATE TABLE user_mcp_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    server_id UUID NOT NULL,
    command JSONB NOT NULL,
    args JSONB,
    env JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'inactive',
    config JSONB,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, server_id)
);
```

### 3. `mcp_tools` - MCP Tools

```sql
CREATE TABLE mcp_tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    server_name VARCHAR(100) NOT NULL,
    server_id UUID NOT NULL,
    input_schema JSONB NOT NULL,
    category VARCHAR(100),
    tags JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Access Levels

### 🌐 System (`system`)

- **Who can use**: Anyone
- **Configuration**: Managed by system administrators
- **Setup required**: No user setup needed
- **Use case**: Core services like database, filesystem

### 🔓 Public (`public`)

- **Who can use**: Any user by setting up MCP connections
- **Configuration**: User-provided configuration
- **Setup required**: Users must configure their own instances
- **Use case**: Popular services like GitHub, Slack, Notion

### 🔒 Private (`private`)

- **Who can use**: Only users who have set it up
- **Configuration**: User-specific private configurations
- **Setup required**: User must have exclusive access/setup
- **Use case**: Custom or enterprise-specific servers

## Core Services

### MCPOperationsService

Handles MCP server discovery and user management:

```python
from app.domains.mcp.services import MCPOperationsService
from app.domains.mcp.value_objects import UserMCPServerInput

# Initialize service
service = MCPOperationsService()

# Get available servers for a user
servers = await service.get_available_servers_for_user(user_id="user_123")

# Setup a new server for user
server_input = UserMCPServerInput(
    server_id="github_server_id",
    command=["npx", "@modelcontextprotocol/server-github"],
    env={"GITHUB_PERSONAL_ACCESS_TOKEN": "your_token"}
)
instance_id = await service.setup_user_mcp_server(user_id, server_input)
```

### MCPConnectionService

Manages MCP connections using LangGraph adapters:

```python
from app.domains.mcp.services import MCPConnectionService

# Initialize connection service
conn_service = MCPConnectionService()

# Initialize connections for user
results = await conn_service.initialize_user_mcp_connections(user_id="user_123")

# Get connected tools
tools = await conn_service.get_connected_tools(user_id="user_123")
```

## Usage Examples

### 1. Check User's Available Servers

```python
# Get categorized list of servers available to user
servers_response = await mcp_ops_service.get_available_servers_for_user("user_123")

print(f"Private servers: {len(servers_response.private_servers)}")
print(f"System servers: {len(servers_response.system_servers)}")
print(f"Public servers: {len(servers_response.public_servers)}")
print(f"Active connections: {servers_response.active_connections}")
```

### 2. Setup Server with Access Level Control

```python
# Public server setup (user configures)
if server.access_level == AccessLevel.PUBLIC:
    server_input = UserMCPServerInput(
        server_id=server.id,
        command=["npx", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": "user_token"},
        config={"timeout": 30.0}
    )
    await service.setup_user_mcp_server(user_id, server_input)

# System server (auto-available, no setup needed)
elif server.access_level == AccessLevel.SYSTEM:
    # Automatically available via system configuration
    pass

# Private server (restricted access)
elif server.access_level == AccessLevel.PRIVATE:
    # Only available if user has been granted access
    pass
```

### 3. Initialize Connections with LangGraph

```python
# Initialize all user's MCP connections
connection_results = await conn_service.initialize_user_mcp_connections(user_id)

for server_name, result in connection_results.items():
    if result.success:
        print(f"✅ {server_name}: {result.tools_discovered} tools")
    else:
        print(f"❌ {server_name}: {result.error_message}")
```

### 4. Get User's Accessible Tools

```python
# Get tools user can access based on their server setup
accessible_tools = await service.get_accessible_tools_for_user(user_id)

# Group by category for analysis
tools_by_category = {}
for tool in accessible_tools:
    category = tool.category or 'general'
    if category not in tools_by_category:
        tools_by_category[category] = []
    tools_by_category[category].append(tool)
```

## Server Configuration Selection

The system intelligently selects server configurations based on access levels:

### System Servers

```python
# System servers use predefined configurations
system_config = {
    "command": ["npx", "@modelcontextprotocol/server-postgres"],
    "env": {"DATABASE_URL": "system_configured_url"},
    "timeout": 30.0
}
```

### Public Servers

```python
# Users provide their own configuration
user_config = {
    "command": ["npx", "@modelcontextprotocol/server-github"],
    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "user_token"},
    "args": [],
    "timeout": 30.0
}
```

### Private Servers

```python
# User-specific private configurations
private_config = {
    "command": ["custom-mcp-server"],
    "env": {"CUSTOM_API_KEY": "private_key"},
    "config": {"custom_settings": "private_value"}
}
```

## Error Handling

The implementation includes comprehensive error handling:

```python
from app.shared.exceptions import ValidationException, NotFoundException

try:
    # Setup server
    instance_id = await service.setup_user_mcp_server(user_id, server_input)
except ValidationException as e:
    # Handle validation errors (user already has server, invalid config)
    print(f"Validation error: {e.message}")
except NotFoundException as e:
    # Handle not found errors (server doesn't exist)
    print(f"Not found: {e.message}")
```

## Testing

Run the example script to see the MCP operations in action:

```bash
cd core
python examples/mcp_operations_example.py
```

This demonstrates:

- ✅ User MCP server setup checking
- ✅ Access level handling (system, public, private)
- ✅ Available server listing for users
- ✅ LangGraph MCP adapter integration
- ✅ Server configuration selection
- ✅ Tool discovery and access control
- ✅ Real-time connection management

## Integration Points

### With LangGraph Workflows

```python
# Get user's MCP client for workflow integration
mcp_client = await conn_service.get_user_mcp_client(user_id)
if mcp_client:
    tools = mcp_client.get_tools()
    # Use tools in LangGraph workflow
```

### With Workflow Generation

```python
# Get accessible tools for workflow analysis
accessible_tools = await service.get_accessible_tools_for_user(user_id)
# Use tools in workflow planning and generation
```

### With User Management

```python
# Check user's MCP setup status
user_servers = await service.get_user_mcp_servers_setup(user_id)
setup_count = len([s for s in user_servers if s.is_ready_for_connection()])
```

## Key Features

1. **🏗️ Domain-Driven Design**: Clean separation of business logic
2. **🔐 Access Control**: Three-tier access level system
3. **🔌 LangGraph Integration**: Uses official LangGraph MCP adapters
4. **⚡ Real-time Updates**: Live connection status and tool discovery
5. **🛡️ Error Handling**: Comprehensive exception management
6. **📊 Monitoring**: Connection health and performance tracking
7. **🔄 State Management**: Persistent connection and tool state
8. **🎯 User-Centric**: Personalized server and tool access

## Future Enhancements

- **Server Discovery**: Automatic discovery of new MCP servers
- **Configuration Templates**: Pre-built configurations for popular servers
- **Health Monitoring**: Advanced health checks and metrics
- **Load Balancing**: Multiple instances of the same server type
- **Caching**: Intelligent tool and configuration caching
- **Authentication**: Advanced authentication mechanisms for private servers
