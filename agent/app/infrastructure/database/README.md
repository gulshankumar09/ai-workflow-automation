# Database Provider System

This module provides a flexible database provider system for the ai-workflow-automation application, supporting multiple database backends with environment-based configuration.

## Features

- **Environment-Based Configuration**: Automatically configure database providers from environment variables
- **Multiple Provider Support**: Supabase, PostgreSQL, SQLite support
- **Connection Pooling**: Built-in connection pooling and health monitoring
- **Error Handling**: Comprehensive error handling with custom exceptions
- **Backward Compatibility**: Supports both automatic and manual provider creation

## Quick Start

### 1. Environment-Based Setup (Recommended)

Set your environment variables:

```bash
# Database Configuration
export DATABASE_PROVIDER=supabase
export DATABASE_PROVIDER_NAME=default

# Supabase Configuration
export SUPABASE_URL=https://your-project-id.supabase.co
export SUPABASE_API_KEY=your-supabase-anon-key
```

Create a database provider:

```python
from app.infrastructure.database.providers.factory import DatabaseProviderFactory

# Create provider from environment
provider = DatabaseProviderFactory.create_provider_from_environment()

# Connect and use
await provider.connect()
result = await provider.select("users", columns=["id", "name"])
await provider.disconnect()
```

### 2. Manual Setup (Legacy)

```python
from supabase import create_client
from app.infrastructure.database.providers.factory import DatabaseProviderFactory

# Create client manually
supabase_client = create_client(
    "https://your-project-id.supabase.co",
    "your-supabase-anon-key"
)

# Create provider manually
provider = DatabaseProviderFactory.create_provider(
    provider_type="supabase",
    supabase_client=supabase_client
)
```

## Environment Variables

### Required Variables

| Variable           | Description               | Example                   |
| ------------------ | ------------------------- | ------------------------- |
| `SUPABASE_URL`     | Your Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_API_KEY` | Supabase anon key         | `eyJhbGciOiJIUzI1NiIs...` |

### Optional Variables

| Variable                        | Default    | Description                  |
| ------------------------------- | ---------- | ---------------------------- |
| `DATABASE_PROVIDER`             | `supabase` | Database provider type       |
| `DATABASE_PROVIDER_NAME`        | `default`  | Provider instance name       |
| `DATABASE_AUTO_CREATE_PROVIDER` | `true`     | Enable auto-creation         |
| `DATABASE_MAX_CONNECTIONS`      | `20`       | Max database connections     |
| `DATABASE_CONNECTION_TIMEOUT`   | `30`       | Connection timeout (seconds) |

## Supported Providers

### Supabase (Primary)

- PostgreSQL-based managed database
- Real-time capabilities
- Built-in authentication
- Automatic scaling

### PostgreSQL

- Direct PostgreSQL connections
- Full SQL support
- Custom connection parameters

### SQLite

- Local file-based database
- Development and testing
- No external dependencies

## Usage Examples

### Basic Operations

```python
# Create provider
provider = DatabaseProviderFactory.create_provider_from_environment()
await provider.connect()

# Insert data
result = await provider.insert(
    "users",
    {"name": "John Doe", "email": "john@example.com"},
    returning=["id", "created_at"]
)

# Select data
users = await provider.select(
    "users",
    columns=["id", "name", "email"],
    filters={"active": True},
    limit=10
)

# Update data
updated = await provider.update(
    "users",
    {"last_login": "2024-01-01T00:00:00Z"},
    {"id": 123}
)

# Delete data
deleted = await provider.delete(
    "users",
    {"id": 123}
)

await provider.disconnect()
```

### Health Monitoring

```python
# Check health
health = await provider.health_check()
print(f"Status: {health['status']}")
print(f"Response time: {health['response_time']}ms")

# Get statistics
stats = provider.get_stats()
print(f"Total queries: {stats['total_queries']}")
print(f"Success rate: {stats['success_rate']}")
```

### Transaction Support

```python
# Start transaction
tx = await provider.begin_transaction()

try:
    await provider.insert("orders", {"user_id": 1, "amount": 100})
    await provider.update("users", {"balance": 500}, {"id": 1})
    await provider.commit_transaction(tx)
except Exception:
    await provider.rollback_transaction(tx)
```

## Error Handling

The system uses custom exception hierarchy:

- `DatabaseException`: General database errors
- `ValidationException`: Invalid parameters or data
- `ConfigurationException`: Missing or invalid configuration
- `NotFoundException`: Resource not found

```python
from app.shared.exceptions import DatabaseException, ConfigurationException

try:
    provider = DatabaseProviderFactory.create_provider_from_environment()
    await provider.connect()
except ConfigurationException as e:
    print(f"Configuration error: {e}")
except DatabaseException as e:
    print(f"Database error: {e}")
```

## Testing

Run the test script to verify your configuration:

```bash
cd core
python test_database_provider.py
```

This will test:

- Environment variable configuration
- Provider creation and connection
- Basic database operations
- Health checks and cleanup

## Configuration Files

Example environment configuration:

- `core/configs/database.env.example` - Environment variable examples

## Architecture

```
DatabaseProviderFactory
├── create_provider_from_environment()  # New: Auto-creation
├── create_default_provider()           # New: Convenience method
├── create_provider()                   # Legacy: Manual creation
└── create_from_config()               # Config-based creation

SupabaseDatabaseProvider
├── __init__(auto_create=True)         # New: Auto-creation support
├── _create_client_from_settings()     # New: Client creation from env
└── [all existing methods]            # Existing functionality
```

## Migration Guide

### From Manual to Environment-Based

**Before:**

```python
from supabase import create_client

supabase_client = create_client(url, key)
provider = DatabaseProviderFactory.create_provider(
    "supabase",
    supabase_client=supabase_client
)
```

**After:**

```python
# Set environment variables first
provider = DatabaseProviderFactory.create_provider_from_environment()
```

### Benefits of Environment-Based Approach

1. **Configuration Management**: Environment variables separate config from code
2. **Security**: No hardcoded credentials in source code
3. **Deployment**: Easy environment-specific configuration
4. **Testing**: Simple to mock different providers
5. **Docker/K8s Ready**: Works seamlessly with container environments
