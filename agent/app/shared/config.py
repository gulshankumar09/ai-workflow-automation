from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Environment(str, Enum):
    """Application environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ProviderType(str, Enum):
    """Provider types for different services"""
    SUPABASE = "supabase"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    REDIS = "redis"
    MEMORY = "memory"
    S3 = "s3"
    LOCAL = "local"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    OLLAMA = "ollama"


class DatabaseSettings(BaseSettings):
    """Database configuration settings"""
    model_config = SettingsConfigDict(env_prefix="DATABASE_")
    
    provider: ProviderType = ProviderType.SUPABASE
    url: str = Field("sqlite+aiosqlite:///:memory:", description="Database connection URL")
    max_connections: int = Field(20, description="Maximum database connections")
    min_connections: int = Field(1, description="Minimum database connections")
    connection_timeout: int = Field(30, description="Connection timeout in seconds")
    query_timeout: int = Field(30, description="Query timeout in seconds")
    ssl_mode: str = Field("prefer", description="SSL mode for database connections")
    pool_recycle: int = Field(3600, description="Connection pool recycle time in seconds")
    
    # Auto-creation settings
    auto_create_provider: bool = Field(True, description="Automatically create provider from environment")
    provider_name: str = Field("default", description="Provider instance name")


class CacheSettings(BaseSettings):
    """Cache configuration settings"""
    model_config = SettingsConfigDict(env_prefix="CACHE_")
    
    provider: ProviderType = ProviderType.SUPABASE
    url: Optional[str] = Field(None, description="Cache connection URL (Redis/etc)")
    default_ttl: int = Field(300, description="Default TTL in seconds")
    max_connections: int = Field(10, description="Maximum cache connections")
    timeout: int = Field(5, description="Cache operation timeout in seconds")
    key_prefix: str = Field("ai-workflow-automation:", description="Cache key prefix")


class StorageSettings(BaseSettings):
    """Storage configuration settings"""
    model_config = SettingsConfigDict(env_prefix="STORAGE_")
    
    provider: ProviderType = ProviderType.S3
    bucket_name: Optional[str] = Field(None, description="Storage bucket name")
    region: Optional[str] = Field(None, description="Storage region")
    access_key: Optional[str] = Field(None, description="Storage access key")
    secret_key: Optional[str] = Field(None, description="Storage secret key")
    endpoint_url: Optional[str] = Field(None, description="Custom storage endpoint")
    base_path: str = Field("./storage", description="Base path for local storage")


class LLMSettings(BaseSettings):
    """LLM provider configuration settings"""
    model_config = SettingsConfigDict(env_prefix="LLM_")
    
    provider: ProviderType = ProviderType.GEMINI
    api_key: Optional[str] = Field(None, description="LLM API key")
    model: str = Field("gemini-pro", description="Default model name")
    temperature: float = Field(0.7, description="Generation temperature")
    max_tokens: int = Field(4096, description="Maximum tokens per response")
    timeout: int = Field(60, description="LLM request timeout in seconds")
    retry_attempts: int = Field(3, description="Number of retry attempts")
    
    # Provider-specific settings
    openai_organization: Optional[str] = Field(None, description="OpenAI organization ID")
    azure_endpoint: Optional[str] = Field(None, description="Azure OpenAI endpoint")
    azure_deployment: Optional[str] = Field(None, description="Azure deployment name")
    ollama_host: str = Field("http://localhost:11434", description="Ollama host URL")


class SupabaseSettings(BaseSettings):
    """Supabase configuration settings"""
    model_config = SettingsConfigDict(env_prefix="SUPABASE_")
    
    url: str = Field("http://localhost:54321", description="Supabase project URL")
    api_key: str = Field("test-api-key", description="Supabase API key")
    jwt_secret: Optional[str] = Field(None, description="Supabase JWT secret")
    service_role_key: Optional[str] = Field(None, description="Supabase service role key")
    realtime_url: Optional[str] = Field(None, description="Supabase Realtime URL")
    storage_url: Optional[str] = Field(None, description="Supabase Storage URL")


class MCPSettings(BaseSettings):
    """MCP (Model Context Protocol) configuration settings"""
    model_config = SettingsConfigDict(env_prefix="MCP_")
    
    servers_config_path: str = Field("./configs/mcp_servers.yaml", description="Path to MCP servers configuration")
    connection_timeout: int = Field(30, description="MCP connection timeout in seconds")
    request_timeout: int = Field(60, description="MCP request timeout in seconds")
    retry_attempts: int = Field(3, description="Number of retry attempts")
    health_check_interval: int = Field(60, description="Health check interval in seconds")
    max_concurrent_connections: int = Field(10, description="Maximum concurrent MCP connections")
    
    # Tool-specific configurations
    slack_app_token: Optional[str] = Field(None, description="Slack app token")
    slack_bot_token: Optional[str] = Field(None, description="Slack bot token")
    notion_api_key: Optional[str] = Field(None, description="Notion API key")
    github_token: Optional[str] = Field(None, description="GitHub access token")
    google_api_key: Optional[str] = Field(None, description="Google API key")


class SecuritySettings(BaseSettings):
    """Security configuration settings"""
    model_config = SettingsConfigDict(env_prefix="SECURITY_")
    
    jwt_secret_key: str = Field("test-secret-key-change-in-production", description="JWT secret key")
    jwt_algorithm: str = Field("HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(15, description="Access token expiration in minutes")
    jwt_refresh_token_expire_days: int = Field(7, description="Refresh token expiration in days")
    
    # Encryption settings
    encryption_key: Optional[str] = Field(None, description="Encryption key for sensitive data")
    password_hash_algorithm: str = Field("bcrypt", description="Password hashing algorithm")
    password_min_length: int = Field(8, description="Minimum password length")
    
    # Rate limiting
    rate_limit_requests: int = Field(100, description="Rate limit requests per minute")
    rate_limit_window: int = Field(60, description="Rate limit window in seconds")


class Auth0Settings(BaseSettings):
    """Auth0 authentication configuration settings"""
    model_config = SettingsConfigDict(env_prefix="AUTH0_")
    
    domain: str = Field("", description="Auth0 domain")
    audience: str = Field("", description="Auth0 API audience")
    client_id: Optional[str] = Field(None, description="Auth0 client ID")
    jwks_cache_ttl: int = Field(3600, description="JWKS cache TTL in seconds")


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration settings"""
    model_config = SettingsConfigDict(env_prefix="MONITORING_")
    
    prometheus_enabled: bool = Field(True, description="Enable Prometheus metrics")
    prometheus_port: int = Field(8001, description="Prometheus metrics port")
    
    # Logging
    log_level: LogLevel = LogLevel.INFO
    log_format: str = Field("json", description="Log format (json or text)")
    log_file_path: Optional[str] = Field(None, description="Log file path")
    
    # Tracing
    jaeger_enabled: bool = Field(False, description="Enable Jaeger tracing")
    jaeger_endpoint: Optional[str] = Field(None, description="Jaeger endpoint URL")
    
    # Health checks
    health_check_enabled: bool = Field(True, description="Enable health checks")
    health_check_interval: int = Field(30, description="Health check interval in seconds")


class ServerSettings(BaseSettings):
    """Server configuration settings"""
    model_config = SettingsConfigDict(env_prefix="SERVER_")
    
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    workers: int = Field(1, description="Number of worker processes")
    reload: bool = Field(False, description="Enable auto-reload in development")
    debug: bool = Field(False, description="Enable debug mode")
    
    # gRPC settings
    grpc_port: int = Field(50051, description="gRPC server port")

    # Health check settings
    health_port: int = Field(8080, description="Health check server port")

class Settings(BaseSettings):
    """Main application settings"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application metadata
    app_name: str = Field("ai-workflow-automation Core", description="Application name")
    app_version: str = Field("1.0.0", description="Application version")
    app_description: str = Field("ai-workflow-automation Dynamic Workflow Generation System", description="Application description")
    environment: Environment = Environment.DEVELOPMENT
    
    # Component settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    supabase: SupabaseSettings = Field(default_factory=SupabaseSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    auth0: Auth0Settings = Field(default_factory=Auth0Settings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    
    @validator("environment", pre=True)
    def set_environment(cls, v):
        if isinstance(v, str):
            return Environment(v.lower())
        return v
    
    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_testing(self) -> bool:
        return self.environment == Environment.TEST
    
    def get_database_url(self) -> str:
        """Get the appropriate database URL based on environment"""
        if self.is_testing:
            return "sqlite+aiosqlite:///:memory:"
        return self.database.url
    
    def get_cache_provider(self) -> ProviderType:
        """Get the appropriate cache provider based on environment"""
        if self.is_development or self.is_testing:
            return ProviderType.MEMORY
        return self.cache.provider
    
    def get_storage_provider(self) -> ProviderType:
        """Get the appropriate storage provider based on environment"""
        if self.is_development or self.is_testing:
            return ProviderType.LOCAL
        return self.storage.provider
    
    def get_llm_provider(self) -> ProviderType:
        """Get the appropriate LLM provider based on environment"""
        return self.llm.provider
    
    @property
    def grpc_port(self) -> int:
        """Get the gRPC server port"""
        return self.server.grpc_port
    
    @property
    def health_port(self) -> int:
        """Get the health check server port"""
        return self.server.health_port
    
    @property
    def debug(self) -> bool:
        """Get debug mode setting"""
        return self.server.debug
    
    @property
    def log_level(self) -> str:
        """Get log level setting"""
        return self.monitoring.log_level.value


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance"""
    return settings


def reload_settings() -> Settings:
    """Reload settings from environment"""
    global settings
    settings = Settings()
    return settings 