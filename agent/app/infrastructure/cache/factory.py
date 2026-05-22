"""
Cache provider factory for creating and managing cache providers.

This factory provides centralized creation and management of cache providers
with custom exception handling and correlation tracking.
"""

from typing import Any, Dict, Optional, Type, List
from app.shared.logger import get_logger
from datetime import datetime
import copy

from .base import AbstractCacheProvider
from .supabase import SupabaseCacheProvider
from .memory import MemoryCacheProvider
from app.shared.exceptions import (
    CacheProviderException,
    ValidationException,
    ConfigurationException,
    NotFoundException,
    create_error_context
)
from app.shared.config import get_settings

logger = get_logger(__name__)


class CacheProviderFactory:
    """
    Factory class for creating cache provider instances.
    
    This factory manages the creation of different cache providers and handles
    configuration validation, error handling, and provider lifecycle management.
    """
    
    _providers: Dict[str, Type[AbstractCacheProvider]] = {}
    
    @classmethod
    def register_provider(
        cls,
        name: str,
        provider_class: Type[AbstractCacheProvider],
        correlation_id: str = None
    ) -> None:
        """
        Register a cache provider class.
        
        Args:
            name: Provider name identifier
            provider_class: Provider class to register
            correlation_id: Request correlation ID for tracking
            
        Raises:
            ValidationException: If name or provider_class is invalid
        """
        if not name or not isinstance(name, str):
            raise ValidationException(
                "Provider name must be a non-empty string",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="register_provider",
                    component="cache_factory",
                    provider=name,
                    correlation_id=correlation_id
                )
            )
        
        if not provider_class:
            raise ValidationException(
                "Provider class cannot be None",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="register_provider",
                    component="cache_factory",
                    provider=name,
                    correlation_id=correlation_id
                )
            )
        
        if not issubclass(provider_class, AbstractCacheProvider):
            raise ValidationException(
                "Provider class must be a subclass of AbstractCacheProvider",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="register_provider",
                    component="cache_factory",
                    provider=name,
                    provider_class=provider_class.__name__,
                    correlation_id=correlation_id
                )
            )
        
        cls._providers[name] = provider_class
        
        logger.info(
            "Cache provider registered",
            provider=name,
            provider_class=provider_class.__name__,
            correlation_id=correlation_id
        )
    
    @classmethod
    def create_provider(
        cls,
        provider_type: str = None,
        correlation_id: str = None,
        fallback_to_memory: bool = True,
        **kwargs
    ) -> AbstractCacheProvider:
        """
        Create a cache provider instance.
        
        Args:
            provider_type: Type of provider to create (uses environment default if None)
            correlation_id: Request correlation ID for tracking
            **kwargs: Provider-specific configuration parameters
            
        Returns:
            Configured cache provider instance
            
        Raises:
            ValidationException: If provider_type is invalid
            ConfigurationException: If required parameters are missing
            CacheProviderException: If provider creation fails
        """
        # Get provider type from environment if not specified
        if not provider_type:
            settings = get_settings()
            provider_type = settings.get_cache_provider().value
        
        # Validate provider type
        if not provider_type:
            raise ValidationException(
                "Provider type is required",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="create_provider",
                    component="cache_factory",
                    correlation_id=correlation_id
                )
            )
        
        if not isinstance(provider_type, str):
            raise ValidationException(
                "Provider type must be a string",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="create_provider",
                    component="cache_factory",
                    provider_type=type(provider_type).__name__,
                    correlation_id=correlation_id
                )
            )
        
        if not provider_type.strip():
            raise ValidationException(
                "Provider type cannot be empty",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="create_provider",
                    component="cache_factory",
                    correlation_id=correlation_id
                )
            )
        
        # Check if provider is registered
        if provider_type not in cls._providers:
            available_providers = list(cls._providers.keys())
            raise ValidationException(
                f"Unsupported provider type: {provider_type}",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="create_provider",
                    component="cache_factory",
                    provider_type=provider_type,
                    available_providers=available_providers,
                    correlation_id=correlation_id
                )
            )
        
        # Validate provider-specific parameters
        cls._validate_provider_parameters(provider_type, kwargs, correlation_id)
        
        try:
            provider_class = cls._providers[provider_type]
            provider = provider_class(correlation_id=correlation_id, **kwargs)
            
            logger.info(
                "Cache provider created successfully",
                provider_type=provider_type,
                provider_name=provider.name,
                correlation_id=correlation_id
            )
            
            return provider
            
        except Exception as e:
            # If fallback is enabled and the requested provider is not memory, try memory fallback
            if (fallback_to_memory and 
                provider_type != "memory" and 
                "memory" in cls._providers and
                ("CACHE_TABLE_MISSING" in str(e) or "Failed to connect" in str(e))):
                
                logger.warning(
                    f"Failed to create {provider_type} provider, falling back to memory cache",
                    provider_type=provider_type,
                    error=str(e),
                    correlation_id=correlation_id
                )
                
                try:
                    memory_provider = cls._providers["memory"](correlation_id=correlation_id, **kwargs)
                    logger.info(
                        "Successfully created memory cache fallback",
                        correlation_id=correlation_id
                    )
                    return memory_provider
                except Exception as fallback_error:
                    logger.error(
                        f"Memory cache fallback also failed: {str(fallback_error)}",
                        correlation_id=correlation_id
                    )
            
            error_context = create_error_context(
                operation="create_provider",
                component="cache_factory",
                provider_type=provider_type,
                error_type=type(e).__name__,
                correlation_id=correlation_id
            )
            
            logger.error(
                "Failed to create cache provider",
                error=str(e),
                **error_context
            )
            
            # Re-raise custom exceptions as-is
            if isinstance(e, (ValidationException, ConfigurationException)):
                raise
            
            # Wrap other exceptions
            raise CacheProviderException(
                f"Failed to create {provider_type} provider: {str(e)}",
                correlation_id=correlation_id,
                details=error_context
            )
    
    @classmethod
    def _validate_provider_parameters(
        cls,
        provider_type: str,
        params: Dict[str, Any],
        correlation_id: str = None
    ) -> None:
        """
        Validate provider-specific parameters.
        
        Args:
            provider_type: Type of provider
            params: Parameters to validate
            correlation_id: Request correlation ID for tracking
            
        Raises:
            ConfigurationException: If required parameters are missing
        """
        # Define required parameters for each provider type
        required_params = {
            "supabase": [],  # Supabase can auto-create client
            "memory": [],    # Memory provider has no required params
            "redis": ["host", "port"]  # Redis requires host and port
        }
        
        if provider_type in required_params:
            missing_params = []
            
            for param in required_params[provider_type]:
                if param not in params or params[param] is None:
                    missing_params.append(param)
            
            if missing_params:
                raise ConfigurationException(
                    f"Missing required parameters for {provider_type} provider: {', '.join(missing_params)}",
                    correlation_id=correlation_id,
                    details=create_error_context(
                        operation="validate_parameters",
                        component="cache_factory",
                        provider_type=provider_type,
                        missing_parameters=missing_params,
                        correlation_id=correlation_id
                    )
                )
    
    @classmethod
    def create_from_config(
        cls,
        config: Dict[str, Any],
        correlation_id: str = None
    ) -> AbstractCacheProvider:
        """
        Create a cache provider from configuration dictionary.
        
        Args:
            config: Configuration dictionary
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Configured cache provider instance
            
        Raises:
            ValidationException: If config is invalid
            ConfigurationException: If required config keys are missing
            CacheProviderException: If provider creation fails
        """
        if not config:
            raise ValidationException(
                "Configuration is required",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="create_from_config",
                    component="cache_factory",
                    correlation_id=correlation_id
                )
            )
        
        # Get provider type from config
        provider_type = config.get("provider") or config.get("type")
        
        if not provider_type:
            raise ValidationException(
                "Provider type not specified in configuration",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="create_from_config",
                    component="cache_factory",
                    config_keys=list(config.keys()),
                    correlation_id=correlation_id
                )
            )
        
        # Create a copy of config to avoid modifying the original
        provider_config = copy.deepcopy(config)
        
        # Remove provider type from config before passing to create_provider
        provider_config.pop("provider", None)
        provider_config.pop("type", None)
        
        return cls.create_provider(
            provider_type=provider_type,
            correlation_id=correlation_id,
            **provider_config
        )
    
    @classmethod
    def create_provider_from_environment(
        cls,
        correlation_id: str = None
    ) -> AbstractCacheProvider:
        """
        Create a cache provider from environment configuration.
        
        This method reads the provider type and configuration from environment
        variables and creates the appropriate provider instance automatically.
        
        Args:
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Configured cache provider instance
            
        Raises:
            ConfigurationException: If environment configuration is invalid
            CacheProviderException: If provider creation fails
        """
        try:
            settings = get_settings()
            provider_type = settings.get_cache_provider().value
            
            logger.info(
                "Creating cache provider from environment",
                provider_type=provider_type,
                correlation_id=correlation_id
            )
            
            return cls._create_provider_from_settings(
                provider_type=provider_type,
                settings=settings,
                correlation_id=correlation_id
            )
            
        except Exception as e:
            error_context = create_error_context(
                operation="create_provider_from_environment",
                component="cache_factory",
                error_type=type(e).__name__,
                correlation_id=correlation_id
            )
            
            logger.error(
                "Failed to create cache provider from environment",
                error=str(e),
                **error_context
            )
            
            # Re-raise custom exceptions as-is
            if isinstance(e, (ValidationException, ConfigurationException)):
                raise
            
            # Wrap other exceptions
            raise CacheProviderException(
                f"Failed to create cache provider from environment: {str(e)}",
                correlation_id=correlation_id,
                details=error_context
            )
    
    @classmethod
    def _create_provider_from_settings(
        cls,
        provider_type: str,
        settings,
        correlation_id: str = None
    ) -> AbstractCacheProvider:
        """
        Create a provider instance from application settings.
        
        Args:
            provider_type: Type of provider to create
            settings: Application settings instance
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Configured cache provider instance
        """
        # Check if provider is registered
        if provider_type not in cls._providers:
            available_providers = list(cls._providers.keys())
            raise ValidationException(
                f"Unsupported provider type: {provider_type}",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="_create_provider_from_settings",
                    component="cache_factory",
                    provider_type=provider_type,
                    available_providers=available_providers,
                    correlation_id=correlation_id
                )
            )
        
        # Get cache settings
        cache_settings = settings.cache
        
        # Build provider configuration
        provider_config = {
            "name": f"{provider_type}_cache",
            "key_prefix": cache_settings.key_prefix,
            "default_ttl": cache_settings.default_ttl,
            "max_connections": cache_settings.max_connections,
            "timeout": cache_settings.timeout,
            "correlation_id": correlation_id
        }
        
        # Add provider-specific configuration
        if provider_type == "supabase":
            provider_config.update({
                "auto_create": True,
                "settings": settings
            })
        elif provider_type == "memory":
            # Memory provider doesn't need additional config
            pass
        elif provider_type == "redis":
            # Redis provider would need host, port, etc.
            # For now, we'll skip Redis implementation
            raise ValidationException(
                "Redis provider not yet implemented",
                correlation_id=correlation_id
            )
        
        # Create provider
        provider_class = cls._providers[provider_type]
        provider = provider_class(**provider_config)
        
        logger.info(
            "Cache provider created from settings",
            provider_type=provider_type,
            provider_name=provider.name,
            correlation_id=correlation_id
        )
        
        return provider
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get list of available provider types.
        
        Returns:
            List of available provider type names
        """
        return list(cls._providers.keys())
    
    @classmethod
    def is_provider_available(cls, provider_type: str) -> bool:
        """
        Check if a provider type is available.
        
        Args:
            provider_type: Provider type to check
            
        Returns:
            True if provider is available
        """
        return provider_type in cls._providers


class CacheProviderManager:
    """
    Manager class for cache provider lifecycle management.
    
    This class manages multiple cache provider instances and provides
    centralized lifecycle management, health monitoring, and statistics.
    """
    
    def __init__(self, correlation_id: str = None):
        """
        Initialize the cache provider manager.
        
        Args:
            correlation_id: Request correlation ID for tracking
        """
        self._correlation_id = correlation_id
        self._providers: Dict[str, AbstractCacheProvider] = {}
        self._default_provider: Optional[str] = None
        
        logger.info(
            "Initialized cache provider manager",
            correlation_id=correlation_id
        )
    
    async def register_provider(
        self,
        name: str,
        provider: AbstractCacheProvider,
        correlation_id: str = None
    ) -> None:
        """
        Register a cache provider with the manager.
        
        Args:
            name: Provider instance name
            provider: Cache provider instance
            correlation_id: Request correlation ID for tracking
            
        Raises:
            ValidationException: If name or provider is invalid
        """
        if not name or not isinstance(name, str):
            raise ValidationException(
                "Provider name must be a non-empty string",
                correlation_id=correlation_id or self._correlation_id,
                details=create_error_context(
                    operation="register_provider",
                    component="cache_manager",
                    provider=name,
                    correlation_id=correlation_id or self._correlation_id
                )
            )
        
        if not provider or not isinstance(provider, AbstractCacheProvider):
            raise ValidationException(
                "Provider must be an instance of AbstractCacheProvider",
                correlation_id=correlation_id or self._correlation_id,
                details=create_error_context(
                    operation="register_provider",
                    component="cache_manager",
                    provider=name,
                    provider_type=type(provider).__name__ if provider else "None",
                    correlation_id=correlation_id or self._correlation_id
                )
            )
        
        self._providers[name] = provider
        
        # Set as default if it's the first provider
        if not self._default_provider:
            self._default_provider = name
        
        logger.info(
            "Cache provider registered with manager",
            provider_name=name,
            provider_class=provider.__class__.__name__,
            correlation_id=correlation_id or self._correlation_id
        )
    
    def get_provider(
        self,
        name: str = None,
        correlation_id: str = None
    ) -> Optional[AbstractCacheProvider]:
        """
        Get a cache provider by name.
        
        Args:
            name: Provider instance name (uses default if None)
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Cache provider instance or None if not found
        """
        provider_name = name or self._default_provider
        provider = self._providers.get(provider_name)
        
        if provider:
            logger.debug(
                "Cache provider retrieved",
                provider_name=provider_name,
                correlation_id=correlation_id or self._correlation_id
            )
        else:
            logger.warning(
                "Cache provider not found",
                provider_name=provider_name,
                available_providers=list(self._providers.keys()),
                correlation_id=correlation_id or self._correlation_id
            )
        
        return provider
    
    def set_default_provider(self, name: str, correlation_id: str = None) -> None:
        """
        Set the default cache provider.
        
        Args:
            name: Provider instance name
            correlation_id: Request correlation ID for tracking
            
        Raises:
            ValidationException: If provider name is invalid
        """
        if name not in self._providers:
            raise ValidationException(
                f"Provider {name} not found in manager",
                correlation_id=correlation_id or self._correlation_id,
                details=create_error_context(
                    operation="set_default_provider",
                    component="cache_manager",
                    provider=name,
                    available_providers=list(self._providers.keys()),
                    correlation_id=correlation_id or self._correlation_id
                )
            )
        
        self._default_provider = name
        
        logger.info(
            "Default cache provider set",
            provider_name=name,
            correlation_id=correlation_id or self._correlation_id
        )
    
    async def connect_all(self, correlation_id: str = None) -> None:
        """
        Connect all registered cache providers.
        
        Args:
            correlation_id: Request correlation ID for tracking
        """
        for name, provider in self._providers.items():
            try:
                await provider.connect()
                logger.info(
                    f"Connected cache provider: {name}",
                    provider_name=name,
                    correlation_id=correlation_id or self._correlation_id
                )
            except Exception as e:
                logger.error(
                    f"Failed to connect cache provider {name}: {str(e)}",
                    provider_name=name,
                    error=str(e),
                    correlation_id=correlation_id or self._correlation_id
                )
    
    async def disconnect_all(self, correlation_id: str = None) -> None:
        """
        Disconnect all registered cache providers.
        
        Args:
            correlation_id: Request correlation ID for tracking
        """
        for name, provider in self._providers.items():
            try:
                await provider.disconnect()
                logger.info(
                    f"Disconnected cache provider: {name}",
                    provider_name=name,
                    correlation_id=correlation_id or self._correlation_id
                )
            except Exception as e:
                logger.error(
                    f"Failed to disconnect cache provider {name}: {str(e)}",
                    provider_name=name,
                    error=str(e),
                    correlation_id=correlation_id or self._correlation_id
                )
    
    async def health_check_all(self, correlation_id: str = None) -> Dict[str, Any]:
        """
        Perform health check on all registered cache providers.
        
        Args:
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Dictionary mapping provider names to health check results
        """
        results = {}
        
        for name, provider in self._providers.items():
            try:
                health_result = await provider.health_check()
                results[name] = health_result
            except Exception as e:
                results[name] = {
                    "provider": name,
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
        
        return results
    
    def get_all_stats(self, correlation_id: str = None) -> Dict[str, Any]:
        """
        Get statistics from all registered cache providers.
        
        Args:
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Dictionary mapping provider names to statistics
        """
        stats = {}
        
        for name, provider in self._providers.items():
            try:
                provider_stats = provider.get_stats()
                stats[name] = provider_stats
            except Exception as e:
                stats[name] = {
                    "provider": name,
                    "error": str(e)
                }
        
        return stats
    
    def list_providers(self) -> List[str]:
        """
        Get list of registered provider names.
        
        Returns:
            List of registered provider names
        """
        return list(self._providers.keys())
    
    def get_default_provider_name(self) -> Optional[str]:
        """
        Get the name of the default provider.
        
        Returns:
            Default provider name or None if not set
        """
        return self._default_provider


# Register built-in providers
CacheProviderFactory.register_provider("supabase", SupabaseCacheProvider)
CacheProviderFactory.register_provider("memory", MemoryCacheProvider) 