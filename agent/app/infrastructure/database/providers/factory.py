"""
Database provider factory for creating and managing database providers.

This factory follows the same pattern as CacheProviderFactory, providing
centralized creation and management of database providers with custom
exception handling and correlation tracking.
"""

from typing import Any, Dict, Optional, Type, List
from app.shared.logger import get_logger
from datetime import datetime
import copy

from .base import AbstractDatabaseProvider
from .supabase import SupabaseDatabaseProvider
from app.shared.exceptions import (
    DatabaseException,
    ValidationException,
    ConfigurationException,
    NotFoundException,
    create_error_context
)
from app.shared.config import get_settings

logger = get_logger(__name__)


class DatabaseProviderFactory:
    """
    Factory class for creating database provider instances.
    
    This factory manages the creation of different database providers and handles
    configuration validation, error handling, and provider lifecycle management.
    """
    
    _providers: Dict[str, Type[AbstractDatabaseProvider]] = {}
    
    @classmethod
    def register_provider(
        self,
        name: str,
        provider_class: Type[AbstractDatabaseProvider],
        correlation_id: str = None
    ) -> None:
        """
        Register a database provider class.
        
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
                    component="database_factory",
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
                    component="database_factory",
                    provider=name,
                    correlation_id=correlation_id
                )
            )
        
        if not issubclass(provider_class, AbstractDatabaseProvider):
            raise ValidationException(
                "Provider class must be a subclass of AbstractDatabaseProvider",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="register_provider",
                    component="database_factory",
                    provider=name,
                    provider_class=provider_class.__name__,
                    correlation_id=correlation_id
                )
            )
        
        self._providers[name] = provider_class
        
        logger.info(
            "Database provider registered",
            provider=name,
            provider_class=provider_class.__name__,
            correlation_id=correlation_id
        )
    
    # @classmethod
    # def create_provider(
    #     cls,
    #     provider_type: str,
    #     correlation_id: str = None,
    #     **kwargs
    # ) -> AbstractDatabaseProvider:
    #     """
    #     Create a database provider instance.
        
    #     Args:
    #         provider_type: Type of provider to create
    #         correlation_id: Request correlation ID for tracking
    #         **kwargs: Provider-specific configuration parameters
            
    #     Returns:
    #         Configured database provider instance
            
    #     Raises:
    #         ValidationException: If provider_type is invalid
    #         ConfigurationException: If required parameters are missing
    #         DatabaseException: If provider creation fails
    #     """
    #     # Validate provider type
    #     if not provider_type:
    #         raise ValidationException(
    #             "Provider type is required",
    #             correlation_id=correlation_id,
    #             details=create_error_context(
    #                 operation="create_provider",
    #                 component="database_factory",
    #                 correlation_id=correlation_id
    #             )
    #         )
        
    #     if not isinstance(provider_type, str):
    #         raise ValidationException(
    #             "Provider type must be a string",
    #             correlation_id=correlation_id,
    #             details=create_error_context(
    #                 operation="create_provider",
    #                 component="database_factory",
    #                 provider_type=type(provider_type).__name__,
    #                 correlation_id=correlation_id
    #             )
    #         )
        
    #     if not provider_type.strip():
    #         raise ValidationException(
    #             "Provider type cannot be empty",
    #             correlation_id=correlation_id,
    #             details=create_error_context(
    #                 operation="create_provider",
    #                 component="database_factory",
    #                 correlation_id=correlation_id
    #             )
    #         )
        
    #     # Check if provider is registered
    #     if provider_type not in cls._providers:
    #         available_providers = list(cls._providers.keys())
    #         raise ValidationException(
    #             f"Unsupported provider type: {provider_type}",
    #             correlation_id=correlation_id,
    #             details=create_error_context(
    #                 operation="create_provider",
    #                 component="database_factory",
    #                 provider_type=provider_type,
    #                 available_providers=available_providers,
    #                 correlation_id=correlation_id
    #             )
    #         )
        
    #     # Validate provider-specific parameters
    #     cls._validate_provider_parameters(provider_type, kwargs, correlation_id)
        
    #     try:
    #         provider_class = cls._providers[provider_type]
    #         provider = provider_class(correlation_id=correlation_id, **kwargs)
            
    #         logger.info(
    #             "Database provider created successfully",
    #             provider_type=provider_type,
    #             provider_name=provider.name,
    #             correlation_id=correlation_id
    #         )
            
    #         return provider
            
    #     except Exception as e:
    #         error_context = create_error_context(
    #             operation="create_provider",
    #                 component="database_factory",
    #             provider_type=provider_type,
    #             error_type=type(e).__name__,
    #             correlation_id=correlation_id
    #         )
            
    #         logger.error(
    #             "Failed to create database provider",
    #             provider_type=provider_type,
    #             error=str(e),
    #             **error_context
    #         )
            
    #         # Re-raise custom exceptions as-is
    #         if isinstance(e, (ValidationException, ConfigurationException)):
    #             raise
            
    #         # Wrap other exceptions
    #         raise DatabaseException(
    #             f"Failed to create {provider_type} provider: {str(e)}",
    #             correlation_id=correlation_id,
    #             details=error_context
    #         )
    
    @classmethod
    def _validate_provider_parameters(
        cls,
        provider_type: str,
        params: Dict[str, Any],
        correlation_id: str = None,
        auto_create: bool = False
    ) -> None:
        """
        Validate provider-specific parameters.
        
        Args:
            provider_type: Type of provider
            params: Parameters to validate
            correlation_id: Request correlation ID for tracking
            auto_create: Whether provider is being auto-created from environment
            
        Raises:
            ConfigurationException: If required parameters are missing
        """
        # Define required parameters for manual creation
        required_params_manual = {
            "supabase": ["supabase_client"],
            "postgresql": ["host", "database", "username", "password"],
            "sqlite": ["database_path"]
        }
        
        # For auto-creation, we don't need manual parameters as they'll be created from environment
        if auto_create:
            return
        
        if provider_type in required_params_manual:
            missing_params = []
            
            for param in required_params_manual[provider_type]:
                if param not in params or params[param] is None:
                    missing_params.append(param)
            
            if missing_params:
                raise ConfigurationException(
                    f"Missing required parameters for {provider_type} provider: {', '.join(missing_params)}",
                    correlation_id=correlation_id,
                    details=create_error_context(
                        operation="validate_parameters",
                        component="database_factory",
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
    ) -> AbstractDatabaseProvider:
        """
        Create a database provider from configuration dictionary.
        
        Args:
            config: Configuration dictionary
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Configured database provider instance
            
        Raises:
            ValidationException: If config is invalid
            ConfigurationException: If required config keys are missing
            DatabaseException: If provider creation fails
        """
        if not config:
            raise ValidationException(
                "Configuration is required",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="create_from_config",
                    component="database_factory",
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
                    component="database_factory",
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
    def create_provider(
        cls,
        correlation_id: str = None
    ) -> AbstractDatabaseProvider:
        """
        Create a database provider from environment configuration.
        
        This method reads the provider type and configuration from environment
        variables and creates the appropriate provider instance automatically.
        
        Args:
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Configured database provider instance
            
        Raises:
            ConfigurationException: If environment configuration is invalid
            DatabaseException: If provider creation fails
        """
        try:
            settings = get_settings()
            provider_type = settings.database.provider.value
            
            logger.info(
                "Creating database provider from environment",
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
                component="database_factory",
                error_type=type(e).__name__,
                correlation_id=correlation_id
            )
            
            logger.error(
                "Failed to create database provider from environment",
                error=str(e),
                **error_context
            )
            
            # Re-raise custom exceptions as-is
            if isinstance(e, (ValidationException, ConfigurationException)):
                raise
            
            # Wrap other exceptions
            raise DatabaseException(
                f"Failed to create database provider from environment: {str(e)}",
                correlation_id=correlation_id,
                details=error_context
            )
    
    @classmethod
    def create_default_provider(
        cls,
        correlation_id: str = None
    ) -> AbstractDatabaseProvider:
        """
        Create the default database provider based on environment configuration.
        
        This is a convenience method that creates a provider from environment
        with sensible defaults.
        
        Args:
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Configured database provider instance
        """
        return cls.create_provider(correlation_id=correlation_id)
    
    @classmethod
    def _create_provider_from_settings(
        cls,
        provider_type: str,
        settings,
        correlation_id: str = None
    ) -> AbstractDatabaseProvider:
        """
        Create a provider instance from application settings.
        
        Args:
            provider_type: Type of provider to create
            settings: Application settings instance
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Configured database provider instance
        """
        # Check if provider is registered
        if provider_type not in cls._providers:
            available_providers = list(cls._providers.keys())
            raise ValidationException(
                f"Unsupported provider type: {provider_type}",
                correlation_id=correlation_id,
                details=create_error_context(
                    operation="_create_provider_from_settings",
                    component="database_factory",
                    provider_type=provider_type,
                    available_providers=available_providers,
                    correlation_id=correlation_id
                )
            )
        
        # Skip parameter validation for auto-creation
        try:
            provider_class = cls._providers[provider_type]
            
            # Create provider with auto-creation flag and settings
            provider = provider_class(
                correlation_id=correlation_id,
                auto_create=True,
                settings=settings,
                name=settings.database.provider_name
            )
            
            logger.info(
                "Database provider created from environment settings",
                provider_type=provider_type,
                provider_name=provider.name,
                correlation_id=correlation_id
            )
            
            return provider
            
        except Exception as e:
            error_context = create_error_context(
                operation="_create_provider_from_settings",
                component="database_factory",
                provider_type=provider_type,
                error_type=type(e).__name__,
                correlation_id=correlation_id
            )
            
            logger.error(
                "Failed to create database provider from settings",
                error=str(e),
                **error_context
            )
            
            # Re-raise custom exceptions as-is
            if isinstance(e, (ValidationException, ConfigurationException)):
                raise
            
            # Wrap other exceptions
            raise DatabaseException(
                f"Failed to create {provider_type} provider from settings: {str(e)}",
                correlation_id=correlation_id,
                details=error_context
            )
    
    @classmethod
    def get_registered_providers(cls) -> List[str]:
        """
        Get list of registered provider names.
        
        Returns:
            List of registered provider names
        """
        return list(cls._providers.keys())
    
    @classmethod
    def is_provider_registered(cls, provider_type: str) -> bool:
        """
        Check if a provider type is registered.
        
        Args:
            provider_type: Provider type to check
            
        Returns:
            True if provider is registered, False otherwise
        """
        return provider_type in cls._providers


class DatabaseProviderManager:
    """
    Manager class for database provider instances.
    
    This manager handles the lifecycle of database provider instances,
    including connection management, health monitoring, and error handling.
    """
    
    def __init__(self, correlation_id: str = "db-manager"):
        """
        Initialize the database provider manager.
        
        Args:
            correlation_id: Request correlation ID for tracking
        """
        self._providers: Dict[str, AbstractDatabaseProvider] = {}
        self._correlation_id = correlation_id
        
        logger.info(
            "Database provider manager initialized",
            correlation_id=correlation_id
        )
    
    async def register_provider(
        self,
        name: str,
        provider: AbstractDatabaseProvider,
        correlation_id: str = None
    ) -> None:
        """
        Register a database provider instance.
        
        Args:
            name: Provider instance name
            provider: Database provider instance
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
                    component="database_factory",
                    provider=name,
                    correlation_id=correlation_id or self._correlation_id
                )
            )
        
        if not provider or not isinstance(provider, AbstractDatabaseProvider):
            raise ValidationException(
                "Provider must be an instance of AbstractDatabaseProvider",
                correlation_id=correlation_id or self._correlation_id,
                details=create_error_context(
                    operation="register_provider",
                    component="database_factory",
                    provider=name,
                    provider_type=type(provider).__name__ if provider else "None",
                    correlation_id=correlation_id or self._correlation_id
                )
            )
        
        self._providers[name] = provider
        
        logger.info(
            "Database provider registered with manager",
            provider_name=name,
            provider_class=provider.__class__.__name__,
            correlation_id=correlation_id or self._correlation_id
        )
    
    def get_provider(
        self,
        name: str,
        correlation_id: str = None
    ) -> Optional[AbstractDatabaseProvider]:
        """
        Get a database provider by name.
        
        Args:
            name: Provider instance name
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Database provider instance or None if not found
        """
        provider = self._providers.get(name)
        
        if provider:
            logger.debug(
                "Database provider retrieved",
                provider_name=name,
                correlation_id=correlation_id or self._correlation_id
            )
        else:
            logger.warning(
                "Database provider not found",
                provider_name=name,
                available_providers=list(self._providers.keys()),
                correlation_id=correlation_id or self._correlation_id
            )
        
        return provider
    
    def get_provider_strict(
        self,
        name: str,
        correlation_id: str = None
    ) -> AbstractDatabaseProvider:
        """
        Get a database provider by name, raising exception if not found.
        
        Args:
            name: Provider instance name
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Database provider instance
            
        Raises:
            NotFoundException: If provider is not found
        """
        provider = self.get_provider(name, correlation_id)
        
        if not provider:
            raise NotFoundException(
                f"Database provider '{name}' not found",
                correlation_id=correlation_id or self._correlation_id,
                details=create_error_context(
                    operation="get_provider_strict",
                    provider=name,
                    available_providers=list(self._providers.keys()),
                    correlation_id=correlation_id or self._correlation_id
                )
            )
        
        return provider
    
    async def connect_all(self, correlation_id: str = None) -> Dict[str, Any]:
        """
        Connect all registered database providers.
        
        Args:
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Connection results dictionary
        """
        results = {
            "success": [],
            "failed": [],
            "total": len(self._providers)
        }
        
        for name, provider in self._providers.items():
            try:
                await provider.connect()
                results["success"].append(name)
                
                logger.info(
                    "Database provider connected",
                    provider_name=name,
                    correlation_id=correlation_id or self._correlation_id
                )
                
            except Exception as e:
                results["failed"].append({
                    "name": name,
                    "error": str(e)
                })
                
                logger.error(
                    "Failed to connect database provider",
                    provider_name=name,
                    error=str(e),
                    correlation_id=correlation_id or self._correlation_id
                )
        
        return results
    
    async def disconnect_all(self, correlation_id: str = None) -> Dict[str, Any]:
        """
        Disconnect all registered database providers.
        
        Args:
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Disconnection results dictionary
            
        Raises:
            DatabaseException: If any disconnections fail
        """
        results = {
            "success": [],
            "failed": [],
            "total": len(self._providers)
        }
        
        errors = []
        
        for name, provider in self._providers.items():
            try:
                await provider.disconnect()
                results["success"].append(name)
                
                logger.info(
                    "Database provider disconnected",
                    provider_name=name,
                    correlation_id=correlation_id or self._correlation_id
                )
                
            except Exception as e:
                error_msg = f"Failed to disconnect {name}: {str(e)}"
                results["failed"].append({
                    "name": name,
                    "error": str(e)
                })
                errors.append(error_msg)
                
                logger.error(
                    "Failed to disconnect database provider",
                    provider_name=name,
                    error=str(e),
                    correlation_id=correlation_id or self._correlation_id
                )
        
        # Raise exception if any disconnections failed
        if errors:
            raise DatabaseException(
                f"Failed to disconnect some providers: {'; '.join(errors)}",
                correlation_id=correlation_id or self._correlation_id,
                details=create_error_context(
                    operation="disconnect_all",
                    failed_providers=results["failed"],
                    correlation_id=correlation_id or self._correlation_id
                )
            )
        
        return results
    
    async def health_check_all(self, correlation_id: str = None) -> Dict[str, Any]:
        """
        Perform health checks on all registered database providers.
        
        Args:
            correlation_id: Request correlation ID for tracking
            
        Returns:
            Health check results dictionary
        """
        results = {
            "healthy": [],
            "unhealthy": [],
            "total": len(self._providers),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for name, provider in self._providers.items():
            try:
                health_status = await provider.health_check()
                
                if health_status.get("status") == "healthy":
                    results["healthy"].append({
                        "name": name,
                        "status": health_status
                    })
                else:
                    results["unhealthy"].append({
                        "name": name,
                        "status": health_status
                    })
                
            except Exception as e:
                results["unhealthy"].append({
                    "name": name,
                    "error": str(e)
                })
                
                logger.error(
                    "Health check failed for database provider",
                    provider_name=name,
                    error=str(e),
                    correlation_id=correlation_id or self._correlation_id
                )
        
        logger.info(
            "Database provider health check completed",
            healthy_count=len(results["healthy"]),
            unhealthy_count=len(results["unhealthy"]),
            correlation_id=correlation_id or self._correlation_id
        )
        
        return results
    
    def list_providers(self) -> List[str]:
        """
        List all registered provider names.
        
        Returns:
            List of provider names
        """
        return list(self._providers.keys())
    
    def get_provider_count(self) -> int:
        """
        Get the number of registered providers.
        
        Returns:
            Number of registered providers
        """
        return len(self._providers)


# Register built-in providers
DatabaseProviderFactory.register_provider("supabase", SupabaseDatabaseProvider) 