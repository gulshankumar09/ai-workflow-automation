# Cache Infrastructure

This module provides a comprehensive caching solution for the ai-workflow-automation Core system with support for multiple cache backends including Supabase and in-memory caching.

## Overview

The cache infrastructure consists of:

- **AbstractCacheProvider**: Base interface for all cache providers
- **SupabaseCacheProvider**: Database-based caching using Supabase
- **MemoryCacheProvider**: In-memory caching for development/testing
- **CacheProviderFactory**: Factory for creating and managing cache providers
- **CacheProviderManager**: Manager for multiple cache provider instances

## Features

- **TTL Support**: Automatic expiration of cache entries
- **Multiple Backends**: Supabase and in-memory providers
- **Statistics**: Hit/miss rates, operation counts, and performance metrics
- **Health Monitoring**: Built-in health checks for all providers
- **Pattern Matching**: Key pattern matching for bulk operations
- **Bulk Operations**: Set/get/delete multiple keys efficiently
- **Error Handling**: Comprehensive error handling with correlation tracking
- **Thread Safety**: Async-safe operations with proper locking

## Quick Start

### Basic Usage

```python
from app.infrastructure.cache.factory import CacheProviderFactory

# Create a cache provider (uses environment configuration)
cache = CacheProviderFactory.create_provider()

# Connect to cache
await cache.connect()

# Set a value
await cache.set("user:123", {"name": "John", "email": "john@example.com"}, ttl=300)

# Get a value
user_data = await cache.get("user:123")

# Check if key exists
exists = await cache.exists("user:123")

# Delete a value
await cache.delete("user:123")

# Disconnect
await cache.disconnect()
```

### Using Specific Providers

```python
# Memory cache (for development/testing)
memory_cache = CacheProviderFactory.create_provider(
    provider_type="memory",
    name="dev_cache",
    default_ttl=300,
    max_size=1000
)

# Supabase cache (for production)
supabase_cache = CacheProviderFactory.create_provider(
    provider_type="supabase",
    name="prod_cache",
    default_ttl=300,
    auto_create=True,
    settings=settings
)
```

### Bulk Operations

```python
# Set multiple values
data = {
    "user:1": {"name": "Alice"},
    "user:2": {"name": "Bob"},
    "user:3": {"name": "Charlie"}
}
await cache.set_many(data, ttl=600)

# Get multiple values
users = await cache.get_many(["user:1", "user:2", "user:3"])

# Delete multiple values
await cache.delete_many(["user:1", "user:2", "user:3"])
```

### Pattern Matching

```python
# Get all keys matching a pattern
user_keys = await cache.keys("user:*")
session_keys = await cache.keys("session:*")

# Pattern examples:
# "user:*" - all keys starting with "user:"
# "*:123" - all keys ending with ":123"
# "*admin*" - all keys containing "admin"
```

## Configuration

### Environment Variables

```bash
# Cache Configuration
CACHE_PROVIDER="supabase"  # or "memory"
CACHE_URL="redis://localhost:6379/0"  # for Redis (future)
CACHE_DEFAULT_TTL=300
CACHE_MAX_CONNECTIONS=10
CACHE_TIMEOUT=5
CACHE_KEY_PREFIX="ai-workflow-automation:"

# Supabase Configuration (for Supabase cache)
SUPABASE_URL="your-supabase-url"
SUPABASE_KEY="your-supabase-key"
```

### Provider-Specific Configuration

#### Memory Cache

```python
memory_cache = CacheProviderFactory.create_provider(
    provider_type="memory",
    name="memory_cache",
    key_prefix="ai-workflow-automation:",
    default_ttl=300,
    max_size=1000,  # Maximum number of entries
    correlation_id="request-123"
)
```

#### Supabase Cache

```python
supabase_cache = CacheProviderFactory.create_provider(
    provider_type="supabase",
    name="supabase_cache",
    key_prefix="ai-workflow-automation:",
    default_ttl=300,
    max_connections=10,
    timeout=5,
    auto_create=True,  # Auto-create client from settings
    settings=settings,
    correlation_id="request-123"
)
```

## Database Schema

The Supabase cache provider uses a `cache_entries` table with the following schema:

```sql
CREATE TABLE cache_entries (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

Run the schema file `core/database/cache_schema.sql` to set up the required tables and functions.

## Monitoring and Statistics

### Health Checks

```python
# Check provider health
health = await cache.health_check()
print(f"Status: {health['status']}")
print(f"Operations: {health['operations']}")
```

### Statistics

```python
# Get cache statistics
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate_percent']}%")
print(f"Total operations: {stats['total_operations']}")
print(f"Errors: {stats['errors']}")
```

### Memory Usage (Memory Provider Only)

```python
if hasattr(cache, 'get_memory_usage'):
    usage = cache.get_memory_usage()
    print(f"Memory usage: {usage['memory_usage_mb']} MB")
    print(f"Utilization: {usage['utilization_percent']}%")
```

## Cache Provider Manager

The `CacheProviderManager` allows you to manage multiple cache providers:

```python
from app.infrastructure.cache.factory import CacheProviderManager

# Create manager
manager = CacheProviderManager(correlation_id="request-123")

# Register providers
memory_cache = CacheProviderFactory.create_provider("memory", name="memory")
supabase_cache = CacheProviderFactory.create_provider("supabase", name="supabase")

await manager.register_provider("memory", memory_cache)
await manager.register_provider("supabase", supabase_cache)

# Set default provider
manager.set_default_provider("supabase")

# Get provider
cache = manager.get_provider("memory")  # or manager.get_provider() for default

# Health check all providers
health_results = await manager.health_check_all()

# Get statistics from all providers
stats = manager.get_all_stats()

# Connect/disconnect all providers
await manager.connect_all()
await manager.disconnect_all()
```

## Error Handling

The cache providers use comprehensive error handling with correlation tracking:

```python
try:
    await cache.set("key", "value")
except CacheProviderException as e:
    print(f"Cache error: {e.message}")
    print(f"Correlation ID: {e.correlation_id}")
    print(f"Details: {e.details}")
```

## Performance Considerations

### Memory Cache

- **Pros**: Fast, no network latency, simple setup
- **Cons**: Data lost on restart, not shared between processes
- **Use Case**: Development, testing, single-process applications

### Supabase Cache

- **Pros**: Persistent, shared across processes, scalable
- **Cons**: Network latency, requires database setup
- **Use Case**: Production, multi-process applications

### Best Practices

1. **Use appropriate TTL**: Set reasonable expiration times based on data volatility
2. **Monitor hit rates**: Aim for >80% hit rate for optimal performance
3. **Use bulk operations**: Prefer `set_many`/`get_many` over individual operations
4. **Handle cache misses**: Always have fallback logic for cache misses
5. **Monitor memory usage**: For memory cache, monitor utilization and adjust `max_size`

## Testing

Run the test script to verify the cache implementation:

```bash
cd core
python test_cache.py
```

The test script covers:

- Basic operations (get, set, delete, exists)
- TTL and expiration
- Bulk operations
- Pattern matching
- Health checks and statistics
- Performance testing

## Integration with Services

The cache is integrated with various services in the ai-workflow-automation Core system:

### User Service

```python
# Cache user context
cache_key = f"user_context:{user_id}"
cached_context = await self.cache.get(cache_key)

if cached_context:
    return UserContext(**cached_context)

# Load from database and cache
context = await self._load_context_from_database(user_id)
await self.cache.set(cache_key, context.model_dump(), ttl=1800)
```

### Session Service

```python
# Cache session data
cache_key = f"session:{session_id}"
await self.cache.set(cache_key, session_data, ttl=session_ttl)

# Retrieve session
session_data = await self.cache.get(cache_key)
```

### Workflow Service

```python
# Cache workflow state
cache_key = f"workflow_session:{session_id}"
await self.cache.set(cache_key, workflow_state, ttl=3600)

# Get workflow state
workflow_state = await self.cache.get(cache_key)
```

## Future Enhancements

- **Redis Provider**: High-performance Redis caching
- **Distributed Caching**: Multi-node cache coordination
- **Cache Warming**: Pre-load frequently accessed data
- **Cache Invalidation**: Advanced invalidation strategies
- **Metrics Integration**: Prometheus/Grafana integration
- **Cache Compression**: Compress large cache values
- **Cache Partitioning**: Partition cache by data type or user

## Troubleshooting

### Common Issues

1. **Connection Errors**: Check Supabase credentials and network connectivity
2. **Performance Issues**: Monitor hit rates and adjust TTL values
3. **Memory Issues**: For memory cache, reduce `max_size` or increase TTL
4. **Data Loss**: Ensure proper error handling and fallback mechanisms

### Debug Mode

Enable debug logging to troubleshoot cache issues:

```python
import logging
logging.getLogger("app.infrastructure.cache").setLevel(logging.DEBUG)
```

### Health Monitoring

Regular health checks help identify issues early:

```python
# Scheduled health check
health = await cache.health_check()
if health['status'] != 'healthy':
    logger.warning(f"Cache health check failed: {health}")
```
