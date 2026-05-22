"""
Supabase cache provider implementation.

This module provides a cache provider that uses Supabase database tables
for storing cache data with TTL (Time-To-Live) support.
"""

import asyncio
import time
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import json
import hashlib
from supabase import create_client, Client

from .base import AbstractCacheProvider
from app.shared.logger import get_logger
from app.shared.exceptions import (
    CacheProviderException,
    ValidationException,
    ConfigurationException,
    create_error_context
)
from app.shared.config import get_settings

logger = get_logger(__name__)


class SupabaseCacheProvider(AbstractCacheProvider):
    """
    Supabase-based cache provider implementation.
    
    This provider uses Supabase database tables to store cache data with
    automatic TTL expiration. It creates a dedicated cache table and
    manages cache entries with proper indexing and cleanup.
    """
    
    def __init__(
        self,
        supabase_client: Optional[Client] = None,
        name: str = "supabase_cache",
        key_prefix: str = "ai-workflow-automation:",
        default_ttl: int = 300,
        max_connections: int = 10,
        timeout: int = 5,
        correlation_id: Optional[str] = None,
        auto_create: bool = False,
        settings = None
    ):
        """
        Initialize the Supabase cache provider.
        
        Args:
            supabase_client: Initialized Supabase client instance
            name: Human-readable name for this provider instance
            key_prefix: Prefix for all cache keys
            default_ttl: Default time-to-live in seconds
            max_connections: Maximum number of connections (not used for Supabase)
            timeout: Operation timeout in seconds
            correlation_id: Request correlation ID for tracking
            auto_create: Whether to auto-create client from environment/settings
            settings: Application settings instance (required if auto_create=True)
            
        Raises:
            ValidationException: If required parameters are missing
            ConfigurationException: If auto-creation fails
        """
        super().__init__(
            name=name,
            key_prefix=key_prefix,
            default_ttl=default_ttl,
            max_connections=max_connections,
            timeout=timeout,
            correlation_id=correlation_id
        )
        
        # Auto-create client from environment/settings if requested
        if auto_create:
            if not settings:
                raise ValidationException(
                    "Settings are required for auto-creation",
                    correlation_id=correlation_id
                )
            self.supabase_client = self._create_client_from_settings(settings, correlation_id)
        else:
            if not supabase_client:
                raise ValidationException(
                    "Supabase client is required when auto_create=False",
                    correlation_id=correlation_id
                )
            self.supabase_client = supabase_client
        
        # Cache table configuration
        self.cache_table = "cache_storage"
        self._connected = False
        self._table_created = False
        
        # Connection pool for request management
        self._semaphore = asyncio.Semaphore(max_connections)
        
        logger.info(
            f"Initialized Supabase cache provider: {name}",
            provider=name,
            cache_table=self.cache_table,
            correlation_id=correlation_id
        )
    
    def _create_client_from_settings(self, settings, correlation_id: str = None) -> Client:
        """
        Create Supabase client from application settings.
        
        Args:
            settings: Application settings instance
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Initialized Supabase client
            
        Raises:
            ConfigurationException: If client creation fails
        """
        try:
            supabase_url = settings.supabase.url
            supabase_key = settings.supabase.api_key
            
            if not supabase_url or not supabase_key:
                raise ConfigurationException(
                    "Supabase URL and API key are required",
                    correlation_id=correlation_id,
                    details=create_error_context(
                        operation="_create_client_from_settings",
                        component="supabase_cache_provider",
                        supabase_url_provided=bool(supabase_url),
                        supabase_key_provided=bool(supabase_key),
                        correlation_id=correlation_id
                    )
                )
            
            client = create_client(supabase_url, supabase_key)
            
            logger.info(
                "Created Supabase client from settings",
                supabase_url=supabase_url,
                correlation_id=correlation_id
            )
            
            return client
            
        except Exception as e:
            raise ConfigurationException(
                f"Failed to create Supabase client: {str(e)}",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="_create_client_from_settings",
                    component="supabase_cache_provider",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=correlation_id
                )
            )
    
    async def connect(self) -> None:
        """
        Connect to Supabase and ensure cache table exists.
        
        Raises:
            CacheProviderException: If connection fails
        """
        if self._connected:
            return
        
        try:
            async with self._semaphore:
                # Test connection with a simple query
                await self._execute_supabase_operation(
                    lambda: self.supabase_client.table("cache_storage").select("key").limit(1).execute()
                )
                
                # Ensure cache table exists
                await self._ensure_cache_table()
                
                self._connected = True
                
                logger.info(
                    "Connected to Supabase cache",
                    provider=self.name,
                    cache_table=self.cache_table,
                    correlation_id=self.correlation_id
                )
                
        except Exception as e:
            self._connected = False
            raise CacheProviderException(
                f"Failed to connect to Supabase cache: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="connect",
                    component="supabase_cache_provider",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=self.correlation_id
                )
            )
    
    async def disconnect(self) -> None:
        """Disconnect from Supabase cache."""
        self._connected = False
        logger.info(
            "Disconnected from Supabase cache",
            provider=self.name,
            correlation_id=self.correlation_id
        )
    
    async def _ensure_cache_table(self) -> None:
        """
        Ensure the cache table exists with proper schema.
        
        This method creates the cache table if it doesn't exist.
        Note: In production, this should be handled by migrations.
        """
        if self._table_created:
            return
        
        try:
            # Try to create the table (this will fail if it already exists)
            # In a real implementation, you'd use proper migrations
            # For now, we'll just test if the table exists
            
            # Test if table exists by trying to select from it
            await self._execute_supabase_operation(
                lambda: self.supabase_client.table(self.cache_table).select("key").limit(1).execute()
            )
            
            self._table_created = True
            logger.info(
                f"Cache table {self.cache_table} is ready",
                provider=self.name,
                correlation_id=self.correlation_id
            )
            
        except Exception as e:
            logger.warning(
                f"Cache table {self.cache_table} may not exist: {str(e)}",
                provider=self.name,
                correlation_id=self.correlation_id
            )
            # In production, you'd create the table here or fail
            # For now, we'll assume it exists and continue
    
    async def _execute_supabase_operation(self, operation_func, *args, **kwargs):
        """
        Execute a Supabase operation with timeout and error handling.
        
        Args:
            operation_func: Function to execute (synchronous Supabase operation)
            *args, **kwargs: Function arguments
            
        Returns:
            Operation result
            
        Raises:
            CacheProviderException: If operation fails
        """
        try:
            # Run synchronous Supabase operation in thread pool
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, operation_func, *args, **kwargs),
                timeout=self.timeout
            )
            return result
            
        except asyncio.TimeoutError:
            raise CacheProviderException(
                f"Supabase operation timeout after {self.timeout}s",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="_execute_supabase_operation",
                    component="supabase_cache_provider",
                    timeout=self.timeout,
                    correlation_id=self.correlation_id
                )
            )
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a missing table error
            if "relation" in error_msg.lower() and "does not exist" in error_msg.lower():
                logger.error(f"Cache table 'cache_storage' does not exist: {error_msg}")
                logger.error("Please ensure the cache_storage table exists in your Supabase database")
                logger.error("The table should have columns: key (varchar), value (jsonb), expires_at (timestamp)")
                
                raise CacheProviderException(
                    f"Cache table 'cache_storage' does not exist: {error_msg}",
                    correlation_id=self.correlation_id,
                    code="CACHE_TABLE_MISSING",
                    details=create_error_context(
                        operation="_execute_supabase_operation",
                        component="supabase_cache_provider",
                        error_type=type(e).__name__,
                        error_message=error_msg,
                        table_requirements={
                            "table_name": "cache_storage",
                            "columns": {
                                "key": "character varying",
                                "value": "jsonb", 
                                "expires_at": "timestamp with time zone"
                            }
                        },
                        correlation_id=self.correlation_id
                    )
                )
            
            raise CacheProviderException(
                f"Supabase operation failed: {error_msg}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="_execute_supabase_operation",
                    component="supabase_cache_provider",
                    error_type=type(e).__name__,
                    error_message=error_msg,
                    correlation_id=self.correlation_id
                )
            )
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
            
        Raises:
            CacheProviderException: If operation fails
        """
        if not self._connected:
            await self.connect()
        
        normalized_key = self._normalize_key(key)
        
        try:
            async with self._semaphore:
                # Get cache entry
                result = await self._execute_supabase_operation(
                    lambda: self.supabase_client.table(self.cache_table)
                    .select("value, expires_at")
                    .eq("key", normalized_key)
                    .execute()
                )
                
                if not result.data:
                    self._update_stats("get", success=False)
                    return None
                
                entry = result.data[0]
                expires_at = entry.get("expires_at")
                
                # Check if expired
                if expires_at:
                    expires_at_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if datetime.now(expires_at_dt.tzinfo) > expires_at_dt:
                        # Delete expired entry
                        await self.delete(key)
                        self._update_stats("get", success=False)
                        return None
                
                # Return value directly since it's stored as JSONB
                value = entry.get("value")
                self._update_stats("get", success=True)
                
                return value
                
        except Exception as e:
            self._update_stats("get", success=False)
            raise CacheProviderException(
                f"Failed to get cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="get",
                    component="supabase_cache_provider",
                    key=key,
                    normalized_key=normalized_key,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=self.correlation_id
                )
            )
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
            
        Returns:
            True if operation was successful
            
        Raises:
            CacheProviderException: If operation fails
        """
        if not self._connected:
            await self.connect()
        
        normalized_key = self._normalize_key(key)
        ttl = ttl or self.default_ttl
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        
        try:
            async with self._semaphore:
                # Upsert cache entry - adapted for cache_storage table structure
                cache_data = {
                    "key": normalized_key,
                    "value": value,  # Store as JSONB directly
                    "expires_at": expires_at.isoformat()
                }
                
                result = await self._execute_supabase_operation(
                    lambda: self.supabase_client.table(self.cache_table)
                    .upsert(cache_data, on_conflict="key")
                    .execute()
                )
                
                success = len(result.data) > 0
                self._update_stats("set", success=success)
                
                return success
                
        except Exception as e:
            self._update_stats("set", success=False)
            raise CacheProviderException(
                f"Failed to set cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="set",
                    component="supabase_cache_provider",
                    key=key,
                    normalized_key=normalized_key,
                    ttl=ttl,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=self.correlation_id
                )
            )
    
    async def delete(self, key: str) -> bool:
        """
        Delete a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if operation was successful
            
        Raises:
            CacheProviderException: If operation fails
        """
        if not self._connected:
            await self.connect()
        
        normalized_key = self._normalize_key(key)
        
        try:
            async with self._semaphore:
                result = await self._execute_supabase_operation(
                    lambda: self.supabase_client.table(self.cache_table)
                    .delete()
                    .eq("key", normalized_key)
                    .execute()
                )
                
                success = True  # Delete operation always succeeds if key exists or not
                self._update_stats("delete", success=success)
                
                return success
                
        except Exception as e:
            self._update_stats("delete", success=False)
            raise CacheProviderException(
                f"Failed to delete cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="delete",
                    component="supabase_cache_provider",
                    key=key,
                    normalized_key=normalized_key,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=self.correlation_id
                )
            )
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is not expired
            
        Raises:
            CacheProviderException: If operation fails
        """
        if not self._connected:
            await self.connect()
        
        normalized_key = self._normalize_key(key)
        
        try:
            async with self._semaphore:
                result = await self._execute_supabase_operation(
                    lambda: self.supabase_client.table(self.cache_table)
                    .select("expires_at")
                    .eq("key", normalized_key)
                    .execute()
                )
                
                if not result.data:
                    return False
                
                entry = result.data[0]
                expires_at = entry.get("expires_at")
                
                # Check if expired
                if expires_at:
                    expires_at_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if datetime.now(expires_at_dt.tzinfo) > expires_at_dt:
                        # Delete expired entry
                        await self.delete(key)
                        return False
                
                return True
                
        except Exception as e:
            raise CacheProviderException(
                f"Failed to check existence of cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="exists",
                    component="supabase_cache_provider",
                    key=key,
                    normalized_key=normalized_key,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=self.correlation_id
                )
            )
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for a key.
        
        Args:
            key: Cache key
            ttl: Time-to-live in seconds
            
        Returns:
            True if operation was successful
            
        Raises:
            CacheProviderException: If operation fails
        """
        if not self._connected:
            await self.connect()
        
        normalized_key = self._normalize_key(key)
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)
        
        try:
            async with self._semaphore:
                result = await self._execute_supabase_operation(
                    lambda: self.supabase_client.table(self.cache_table)
                    .update({"expires_at": expires_at.isoformat()})
                    .eq("key", normalized_key)
                    .execute()
                )
                
                return len(result.data) > 0
                
        except Exception as e:
            raise CacheProviderException(
                f"Failed to set expiration for cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="expire",
                    component="supabase_cache_provider",
                    key=key,
                    normalized_key=normalized_key,
                    ttl=ttl,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=self.correlation_id
                )
            )
    
    async def ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            Remaining TTL in seconds, -1 if no expiration, None if key doesn't exist
            
        Raises:
            CacheProviderException: If operation fails
        """
        if not self._connected:
            await self.connect()
        
        normalized_key = self._normalize_key(key)
        
        try:
            async with self._semaphore:
                result = await self._execute_supabase_operation(
                    lambda: self.supabase_client.table(self.cache_table)
                    .select("expires_at")
                    .eq("key", normalized_key)
                    .execute()
                )
                
                if not result.data:
                    return None
                
                entry = result.data[0]
                expires_at = entry.get("expires_at")
                
                if not expires_at:
                    return -1  # No expiration
                
                expires_at_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                now = datetime.now(expires_at_dt.tzinfo)
                
                if now > expires_at_dt:
                    # Expired, delete and return None
                    await self.delete(key)
                    return None
                
                remaining = int((expires_at_dt - now).total_seconds())
                return max(0, remaining)
                
        except Exception as e:
            raise CacheProviderException(
                f"Failed to get TTL for cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="ttl",
                    component="supabase_cache_provider",
                    key=key,
                    normalized_key=normalized_key,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=self.correlation_id
                )
            )
    
    async def clear(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if operation was successful
            
        Raises:
            CacheProviderException: If operation fails
        """
        if not self._connected:
            await self.connect()
        
        try:
            async with self._semaphore:
                await self._execute_supabase_operation(
                    lambda: self.supabase_client.table(self.cache_table)
                    .delete()
                    .neq("key", "")  # Delete all entries
                    .execute()
                )
                
                return True
                
        except Exception as e:
            raise CacheProviderException(
                f"Failed to clear cache: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="clear",
                    component="supabase_cache_provider",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=self.correlation_id
                )
            )
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """
        Get keys matching a pattern.
        
        Args:
            pattern: Key pattern to match (supports basic wildcards)
            
        Returns:
            List of matching keys
            
        Raises:
            CacheProviderException: If operation fails
        """
        if not self._connected:
            await self.connect()
        
        try:
            async with self._semaphore:
                # For now, return all keys (pattern matching can be implemented later)
                result = await self._execute_supabase_operation(
                    lambda: self.supabase_client.table(self.cache_table)
                    .select("key")
                    .execute()
                )
                
                keys = [entry["key"] for entry in result.data]
                
                # Basic pattern matching
                if pattern == "*":
                    return keys
                elif pattern.startswith("*") and pattern.endswith("*"):
                    # *pattern*
                    substr = pattern[1:-1]
                    return [key for key in keys if substr in key]
                elif pattern.startswith("*"):
                    # *pattern
                    suffix = pattern[1:]
                    return [key for key in keys if key.endswith(suffix)]
                elif pattern.endswith("*"):
                    # pattern*
                    prefix = pattern[:-1]
                    return [key for key in keys if key.startswith(prefix)]
                else:
                    # exact match
                    return [key for key in keys if key == pattern]
                
        except Exception as e:
            raise CacheProviderException(
                f"Failed to get keys with pattern {pattern}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="keys",
                    component="supabase_cache_provider",
                    pattern=pattern,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=self.correlation_id
                )
            )
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired cache entries.
        
        Returns:
            Number of expired entries removed
        """
        if not self._connected:
            await self.connect()
        
        try:
            async with self._semaphore:
                now = datetime.utcnow().isoformat()
                
                result = await self._execute_supabase_operation(
                    lambda: self.supabase_client.table(self.cache_table)
                    .delete()
                    .lt("expires_at", now)
                    .execute()
                )
                
                removed_count = len(result.data) if result.data else 0
                
                logger.info(
                    f"Cleaned up {removed_count} expired cache entries",
                    provider=self.name,
                    removed_count=removed_count,
                    correlation_id=self.correlation_id
                )
                
                return removed_count
                
        except Exception as e:
            logger.warning(
                f"Failed to cleanup expired cache entries: {str(e)}",
                provider=self.name,
                correlation_id=self.correlation_id
            )
            return 0 