"""
Dependency Injection Container for ai-workflow-automation Core

This module provides a centralized dependency injection container for managing
shared resources like database clients, cache providers, and other services.
"""

import asyncio
from typing import Dict, Any, Optional, Type, TypeVar, Generic
from contextlib import asynccontextmanager
from app.shared.logger import get_logger
from functools import lru_cache

from app.shared.config import get_settings
from app.shared.exceptions import (
    ConfigurationException,
    DependencyException,
    create_error_context
)

logger = get_logger(__name__)

T = TypeVar('T')


class Singleton(type):
    """Metaclass for singleton pattern"""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class SharedClientManager(metaclass=Singleton):
    """
    Manages shared client instances across the application.
    
    This singleton ensures that Supabase clients and other shared resources
    are created once and reused across all providers and services.
    """
    
    def __init__(self):
        self._clients: Dict[str, Any] = {}
        self._settings = get_settings()
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize all shared clients"""
        if self._initialized:
            return
            
        try:
            logger.info("Initializing shared client manager...")
            
            # Initialize Supabase client if configured
            if self._should_create_supabase_client():
                await self._create_supabase_client()
            
            self._initialized = True
            logger.info("Shared client manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize shared client manager: {str(e)}")
            raise DependencyException(
                f"Failed to initialize shared client manager: {str(e)}",
                details=create_error_context(
                    operation="initialize",
                    component="SharedClientManager",
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
            )
    
    def _should_create_supabase_client(self) -> bool:
        """Check if Supabase client should be created based on configuration"""
        # Create if any provider uses Supabase
        return (
            self._settings.database.provider.value == "supabase" or
            self._settings.cache.provider.value == "supabase" or
            self._settings.storage.provider.value == "supabase"
        )
    
    async def _create_supabase_client(self):
        """Create shared Supabase client instance"""
        try:
            from supabase import create_client
            
            url = self._settings.supabase.url
            key = self._settings.supabase.api_key
            
            if not url:
                raise ConfigurationException(
                    "Supabase URL is required (SUPABASE_URL environment variable)",
                    details=create_error_context(
                        operation="_create_supabase_client",
                        component="SharedClientManager",
                        missing_setting="supabase_url"
                    )
                )
                
            if not key:
                raise ConfigurationException(
                    "Supabase API key is required (SUPABASE_API_KEY environment variable)",
                    details=create_error_context(
                        operation="_create_supabase_client",
                        component="SharedClientManager",
                        missing_setting="supabase_key"
                    )
                )
            
            client = create_client(url, key)
            self._clients["supabase"] = client
            
            logger.info(
                "Shared Supabase client created",
                url_preview=url[:30] + "..." if len(url) > 30 else url
            )
            
        except ImportError as e:
            raise ConfigurationException(
                "Supabase client library not installed. Run: uv add supabase",
                details=create_error_context(
                    operation="_create_supabase_client",
                    component="SharedClientManager",
                    error_type="ImportError",
                    error_message=str(e)
                )
            )
    
    def get_supabase_client(self):
        """Get shared Supabase client instance"""
        if not self._initialized:
            raise DependencyException(
                "SharedClientManager not initialized. Call initialize() first.",
                details=create_error_context(
                    operation="get_supabase_client",
                    component="SharedClientManager",
                    state="not_initialized"
                )
            )
        
        if "supabase" not in self._clients:
            raise DependencyException(
                "Supabase client not available. Check configuration.",
                details=create_error_context(
                    operation="get_supabase_client",
                    component="SharedClientManager",
                    available_clients=list(self._clients.keys())
                )
            )
        
        return self._clients["supabase"]
    
    def has_client(self, client_type: str) -> bool:
        """Check if a client type is available"""
        return client_type in self._clients
    
    async def cleanup(self) -> None:
        """Cleanup all managed clients"""
        logger.info("Cleaning up shared clients...")
        
        # For now, just clear the clients dict
        # In the future, we might need specific cleanup for each client type
        self._clients.clear()
        self._initialized = False
        
        logger.info("Shared clients cleaned up")


class DependencyContainer:
    """
    Dependency injection container for the application.
    
    Provides factory methods and manages the lifecycle of application dependencies.
    """
    
    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id
        self._client_manager = SharedClientManager()
        
    async def initialize(self) -> None:
        """Initialize the dependency container"""
        await self._client_manager.initialize()
    
    async def cleanup(self) -> None:
        """Cleanup the dependency container"""
        await self._client_manager.cleanup()
    
    def create_database_provider(self, **kwargs):
        """Create database provider with automatic dependency injection"""
        from app.infrastructure.database.providers.factory import DatabaseProviderFactory
        
        # The factory reads from settings automatically, so we just need to initialize first
        return DatabaseProviderFactory.create_provider(
            correlation_id=self.correlation_id
        )
    
    def create_cache_provider(self, provider_type: str = None, **kwargs):
        """Create cache provider with automatic dependency injection"""
        from app.infrastructure.cache.factory import CacheProviderFactory
        
        settings = get_settings()
        provider_type = provider_type or settings.cache.provider.value
        
        # Inject Supabase client if needed
        if provider_type == "supabase" and "supabase_client" not in kwargs:
            if self._client_manager.has_client("supabase"):
                kwargs["supabase_client"] = self._client_manager.get_supabase_client()
            else:
                kwargs["auto_create"] = True
                kwargs["settings"] = settings
        
        return CacheProviderFactory.create_provider(
            provider_type=provider_type,
            correlation_id=self.correlation_id,
            **kwargs
        )
    
    async def create_llm_provider(self, provider_type: str = None, **kwargs):
        """Create LLM provider with automatic dependency injection"""
        from app.ai.llm import get_llm
        
        # Return the centralized LLM instance (provider_type is ignored for now)
        return get_llm()


@lru_cache()
def get_dependency_container(correlation_id: Optional[str] = None) -> DependencyContainer:
    """Get or create dependency container instance"""
    return DependencyContainer(correlation_id=correlation_id)


@asynccontextmanager
async def managed_dependencies(correlation_id: Optional[str] = None):
    """Context manager for dependency lifecycle management"""
    container = get_dependency_container(correlation_id)
    
    try:
        await container.initialize()
        yield container
    finally:
        await container.cleanup() 