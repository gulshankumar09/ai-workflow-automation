"""
Memory cache provider implementation.

This module provides a simple in-memory cache provider for development
and testing environments. It stores cache data in process memory with
TTL support.
"""

import asyncio
import time
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import json
from collections import OrderedDict

from .base import AbstractCacheProvider
from app.shared.logger import get_logger
from app.shared.exceptions import (
    CacheProviderException,
    ValidationException,
    create_error_context
)

logger = get_logger(__name__)


class MemoryCacheProvider(AbstractCacheProvider):
    """
    In-memory cache provider implementation.
    
    This provider stores cache data in process memory with TTL support.
    It's suitable for development and testing environments but not for
    production use due to data loss on process restart.
    """
    
    def __init__(
        self,
        name: str = "memory_cache",
        key_prefix: str = "ai-workflow-automation:",
        default_ttl: int = 300,
        max_connections: int = 10,
        timeout: int = 5,
        correlation_id: Optional[str] = None,
        max_size: int = 1000
    ):
        """
        Initialize the memory cache provider.
        
        Args:
            name: Human-readable name for this provider instance
            key_prefix: Prefix for all cache keys
            default_ttl: Default time-to-live in seconds
            max_connections: Maximum number of connections (not used for memory cache)
            timeout: Operation timeout in seconds (not used for memory cache)
            correlation_id: Request correlation ID for tracking
            max_size: Maximum number of cache entries
        """
        super().__init__(
            name=name,
            key_prefix=key_prefix,
            default_ttl=default_ttl,
            max_connections=max_connections,
            timeout=timeout,
            correlation_id=correlation_id
        )
        
        # Memory storage
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._connected = False
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info(
            f"Initialized memory cache provider: {name}",
            provider=name,
            max_size=max_size,
            correlation_id=correlation_id
        )
    
    async def connect(self) -> None:
        """
        Connect to memory cache (no-op for memory provider).
        
        Raises:
            CacheProviderException: If connection fails
        """
        self._connected = True
        logger.info(
            "Connected to memory cache",
            provider=self.name,
            correlation_id=self.correlation_id
        )
    
    async def disconnect(self) -> None:
        """Disconnect from memory cache."""
        self._connected = False
        # Clear cache on disconnect
        self._cache.clear()
        logger.info(
            "Disconnected from memory cache",
            provider=self.name,
            correlation_id=self.correlation_id
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
            async with self._lock:
                if normalized_key not in self._cache:
                    self._update_stats("get", success=False)
                    return None
                
                entry = self._cache[normalized_key]
                expires_at = entry.get("expires_at")
                
                # Check if expired
                if expires_at and time.time() > expires_at:
                    # Remove expired entry
                    del self._cache[normalized_key]
                    self._update_stats("get", success=False)
                    return None
                
                # Move to end (LRU behavior)
                self._cache.move_to_end(normalized_key)
                
                # Deserialize and return value
                value = self._deserialize_value(entry.get("value"))
                self._update_stats("get", success=True)
                
                return value
                
        except Exception as e:
            self._update_stats("get", success=False)
            raise CacheProviderException(
                f"Failed to get cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="get",
                    component="memory_cache_provider",
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
        expires_at = time.time() + ttl if ttl > 0 else None
        
        try:
            async with self._lock:
                # Serialize value
                serialized_value = self._serialize_value(value)
                
                # Create cache entry
                cache_entry = {
                    "value": serialized_value,
                    "expires_at": expires_at,
                    "created_at": time.time(),
                    "updated_at": time.time()
                }
                
                # Check if key already exists
                if normalized_key in self._cache:
                    # Update existing entry
                    self._cache[normalized_key].update(cache_entry)
                    self._cache.move_to_end(normalized_key)
                else:
                    # Add new entry
                    self._cache[normalized_key] = cache_entry
                    
                    # Check if we need to evict entries
                    if len(self._cache) > self._max_size:
                        await self._evict_entries()
                
                self._update_stats("set", success=True)
                return True
                
        except Exception as e:
            self._update_stats("set", success=False)
            raise CacheProviderException(
                f"Failed to set cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="set",
                    component="memory_cache_provider",
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
            async with self._lock:
                if normalized_key in self._cache:
                    del self._cache[normalized_key]
                
                self._update_stats("delete", success=True)
                return True
                
        except Exception as e:
            self._update_stats("delete", success=False)
            raise CacheProviderException(
                f"Failed to delete cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="delete",
                    component="memory_cache_provider",
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
            async with self._lock:
                if normalized_key not in self._cache:
                    return False
                
                entry = self._cache[normalized_key]
                expires_at = entry.get("expires_at")
                
                # Check if expired
                if expires_at and time.time() > expires_at:
                    # Remove expired entry
                    del self._cache[normalized_key]
                    return False
                
                return True
                
        except Exception as e:
            raise CacheProviderException(
                f"Failed to check existence of cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="exists",
                    component="memory_cache_provider",
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
        expires_at = time.time() + ttl if ttl > 0 else None
        
        try:
            async with self._lock:
                if normalized_key not in self._cache:
                    return False
                
                self._cache[normalized_key]["expires_at"] = expires_at
                self._cache[normalized_key]["updated_at"] = time.time()
                
                return True
                
        except Exception as e:
            raise CacheProviderException(
                f"Failed to set expiration for cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="expire",
                    component="memory_cache_provider",
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
            async with self._lock:
                if normalized_key not in self._cache:
                    return None
                
                entry = self._cache[normalized_key]
                expires_at = entry.get("expires_at")
                
                if not expires_at:
                    return -1  # No expiration
                
                remaining = int(expires_at - time.time())
                
                if remaining <= 0:
                    # Expired, delete and return None
                    del self._cache[normalized_key]
                    return None
                
                return remaining
                
        except Exception as e:
            raise CacheProviderException(
                f"Failed to get TTL for cache key {key}: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="ttl",
                    component="memory_cache_provider",
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
            async with self._lock:
                self._cache.clear()
                return True
                
        except Exception as e:
            raise CacheProviderException(
                f"Failed to clear cache: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="clear",
                    component="memory_cache_provider",
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
            async with self._lock:
                # Clean up expired entries first
                await self._cleanup_expired()
                
                keys = list(self._cache.keys())
                
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
                    component="memory_cache_provider",
                    pattern=pattern,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    correlation_id=self.correlation_id
                )
            )
    
    async def _evict_entries(self) -> None:
        """
        Evict entries when cache is full (LRU eviction).
        """
        # Remove oldest entries (LRU)
        while len(self._cache) > self._max_size:
            # Remove the oldest entry (first in OrderedDict)
            self._cache.popitem(last=False)
    
    async def _cleanup_expired(self) -> int:
        """
        Clean up expired cache entries.
        
        Returns:
            Number of expired entries removed
        """
        if not self._connected:
            return 0
        
        try:
            async with self._lock:
                current_time = time.time()
                expired_keys = []
                
                for key, entry in self._cache.items():
                    expires_at = entry.get("expires_at")
                    if expires_at and current_time > expires_at:
                        expired_keys.append(key)
                
                # Remove expired entries
                for key in expired_keys:
                    del self._cache[key]
                
                if expired_keys:
                    logger.info(
                        f"Cleaned up {len(expired_keys)} expired cache entries",
                        provider=self.name,
                        removed_count=len(expired_keys),
                        correlation_id=self.correlation_id
                    )
                
                return len(expired_keys)
                
        except Exception as e:
            logger.warning(
                f"Failed to cleanup expired cache entries: {str(e)}",
                provider=self.name,
                correlation_id=self.correlation_id
            )
            return 0
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get memory usage statistics.
        
        Returns:
            Memory usage statistics dictionary
        """
        try:
            # Note: This method is synchronous, so we can't use the async lock
            # In a real implementation, you might want to make this async
            total_entries = len(self._cache)
            total_size = sum(
                len(str(entry.get("value", ""))) 
                for entry in self._cache.values()
            )
            
            return {
                "provider": self.name,
                "total_entries": total_entries,
                "max_entries": self._max_size,
                "memory_usage_bytes": total_size,
                "memory_usage_mb": round(total_size / (1024 * 1024), 2),
                "utilization_percent": round((total_entries / self._max_size) * 100, 2)
            }
        except Exception as e:
            logger.warning(
                f"Failed to get memory usage: {str(e)}",
                provider=self.name,
                correlation_id=self.correlation_id
            )
            return {
                "provider": self.name,
                "error": str(e)
            } 