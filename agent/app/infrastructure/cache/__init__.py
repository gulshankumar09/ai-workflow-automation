"""
Cache infrastructure module for ai-workflow-automation Core.

This module provides cache provider implementations including:
- Supabase-based caching using database tables
- Memory-based caching for development/testing
- Abstract cache provider interface
- Factory and manager classes for cache lifecycle management
"""

from .factory import CacheProviderFactory, CacheProviderManager
from .base import AbstractCacheProvider
from .supabase import SupabaseCacheProvider
from .memory import MemoryCacheProvider

__all__ = [
    "CacheProviderFactory",
    "CacheProviderManager", 
    "AbstractCacheProvider",
    "SupabaseCacheProvider",
    "MemoryCacheProvider"
] 