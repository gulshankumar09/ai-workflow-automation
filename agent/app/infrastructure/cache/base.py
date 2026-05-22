"""
Abstract base class for cache providers.

This module defines the interface that all cache providers must implement,
ensuring consistent behavior across different caching backends.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import json
import hashlib
from app.shared.logger import get_logger
from app.shared.exceptions import (
    CacheProviderException,
    ValidationException,
    create_error_context
)

logger = get_logger(__name__)


class AbstractCacheProvider(ABC):
    """
    Abstract base class for cache providers.
    
    This class defines the interface that all cache providers must implement.
    It provides common functionality and ensures consistent behavior across
    different caching backends.
    """
    
    def __init__(
        self,
        name: str,
        key_prefix: str = "ai-workflow-automation:",
        default_ttl: int = 300,
        max_connections: int = 10,
        timeout: int = 5,
        correlation_id: Optional[str] = None
    ):
        """
        Initialize the cache provider.
        
        Args:
            name: Human-readable name for this provider instance
            key_prefix: Prefix for all cache keys
            default_ttl: Default time-to-live in seconds
            max_connections: Maximum number of connections
            timeout: Operation timeout in seconds
            correlation_id: Request correlation ID for tracking
        """
        self.name = name
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        self.timeout = timeout
        self.correlation_id = correlation_id
        
        # Statistics tracking
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
            "total_operations": 0
        }
        
        logger.info(
            f"Initialized cache provider: {name}",
            provider=name,
            key_prefix=key_prefix,
            default_ttl=default_ttl,
            correlation_id=correlation_id
        )
    
    def _normalize_key(self, key: str) -> str:
        """
        Normalize cache key with prefix.
        
        Args:
            key: Original cache key
            
        Returns:
            Normalized cache key with prefix
        """
        if not key:
            raise ValidationException(
                "Cache key cannot be empty",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="_normalize_key",
                    component="cache_provider",
                    key=key,
                    correlation_id=self.correlation_id
                )
            )
        
        # Remove any existing prefix to avoid double-prefixing
        if key.startswith(self.key_prefix):
            return key
        
        return f"{self.key_prefix}{key}"
    
    def _serialize_value(self, value: Any) -> str:
        """
        Serialize value for storage.
        
        Args:
            value: Value to serialize
            
        Returns:
            Serialized value as string
        """
        try:
            if isinstance(value, str):
                return value
            return json.dumps(value, default=str)
        except Exception as e:
            raise CacheProviderException(
                f"Failed to serialize value: {str(e)}",
                correlation_id=self.correlation_id,
                details=create_error_context(
                    operation="_serialize_value",
                    component="cache_provider",
                    value_type=type(value).__name__,
                    error_type=type(e).__name__,
                    correlation_id=self.correlation_id
                )
            )
    
    def _deserialize_value(self, value: str) -> Any:
        """
        Deserialize value from storage.
        
        Args:
            value: Serialized value string
            
        Returns:
            Deserialized value
        """
        try:
            if not value:
                return None
            
            # Try to parse as JSON first
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # If not JSON, return as string
                return value
        except Exception as e:
            logger.warning(
                f"Failed to deserialize value: {str(e)}",
                value_preview=value[:100] if value else None,
                correlation_id=self.correlation_id
            )
            return value
    
    def _update_stats(self, operation: str, success: bool = True) -> None:
        """
        Update operation statistics.
        
        Args:
            operation: Operation type (get, set, delete, etc.)
            success: Whether operation was successful
        """
        self._stats["total_operations"] += 1
        
        if success:
            if operation == "get":
                self._stats["hits"] += 1
            elif operation == "set":
                self._stats["sets"] += 1
            elif operation == "delete":
                self._stats["deletes"] += 1
        else:
            self._stats["errors"] += 1
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Connect to the cache backend.
        
        Raises:
            CacheProviderException: If connection fails
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the cache backend.
        """
        pass
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
            
        Raises:
            CacheProviderException: If operation fails
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
            
        Raises:
            CacheProviderException: If operation fails
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary mapping keys to values (missing keys omitted)
            
        Raises:
            CacheProviderException: If operation fails
        """
        result = {}
        for key in keys:
            try:
                value = await self.get(key)
                if value is not None:
                    result[key] = value
            except Exception as e:
                logger.warning(
                    f"Failed to get key {key}: {str(e)}",
                    key=key,
                    correlation_id=self.correlation_id
                )
        return result
    
    async def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Set multiple values in cache.
        
        Args:
            data: Dictionary mapping keys to values
            ttl: Time-to-live in seconds (uses default if None)
            
        Returns:
            True if all operations were successful
            
        Raises:
            CacheProviderException: If operation fails
        """
        success = True
        for key, value in data.items():
            try:
                result = await self.set(key, value, ttl)
                if not result:
                    success = False
            except Exception as e:
                logger.warning(
                    f"Failed to set key {key}: {str(e)}",
                    key=key,
                    correlation_id=self.correlation_id
                )
                success = False
        return success
    
    async def delete_many(self, keys: List[str]) -> bool:
        """
        Delete multiple values from cache.
        
        Args:
            keys: List of cache keys to delete
            
        Returns:
            True if all operations were successful
            
        Raises:
            CacheProviderException: If operation fails
        """
        success = True
        for key in keys:
            try:
                result = await self.delete(key)
                if not result:
                    success = False
            except Exception as e:
                logger.warning(
                    f"Failed to delete key {key}: {str(e)}",
                    key=key,
                    correlation_id=self.correlation_id
                )
                success = False
        return success
    
    async def clear(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if operation was successful
            
        Raises:
            CacheProviderException: If operation fails
        """
        raise NotImplementedError("clear() method not implemented for this provider")
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """
        Get keys matching a pattern.
        
        Args:
            pattern: Key pattern to match
            
        Returns:
            List of matching keys
            
        Raises:
            CacheProviderException: If operation fails
        """
        raise NotImplementedError("keys() method not implemented for this provider")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on cache provider.
        
        Returns:
            Health check result dictionary
        """
        try:
            # Test basic operations
            test_key = f"{self.key_prefix}health_check_{datetime.now().timestamp()}"
            test_value = {"test": True, "timestamp": datetime.now().isoformat()}
            
            # Test set
            set_result = await self.set(test_key, test_value, ttl=60)
            
            # Test get
            get_result = await self.get(test_key)
            
            # Test exists
            exists_result = await self.exists(test_key)
            
            # Test delete
            delete_result = await self.delete(test_key)
            
            return {
                "provider": self.name,
                "status": "healthy" if all([set_result, get_result, exists_result, delete_result]) else "unhealthy",
                "operations": {
                    "set": set_result,
                    "get": get_result is not None,
                    "exists": exists_result,
                    "delete": delete_result
                },
                "stats": self.get_stats(),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "provider": self.name,
                "status": "unhealthy",
                "error": str(e),
                "stats": self.get_stats(),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache provider statistics.
        
        Returns:
            Statistics dictionary
        """
        total_ops = self._stats["total_operations"]
        hit_rate = (
            (self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])) * 100
            if (self._stats["hits"] + self._stats["misses"]) > 0 else 0.0
        )
        
        return {
            "provider": self.name,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "deletes": self._stats["deletes"],
            "errors": self._stats["errors"],
            "total_operations": total_ops,
            "hit_rate_percent": round(hit_rate, 2),
            "error_rate_percent": round((self._stats["errors"] / total_ops) * 100, 2) if total_ops > 0 else 0.0
        }
    
    def reset_stats(self) -> None:
        """Reset cache provider statistics."""
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0,
            "total_operations": 0
        } 