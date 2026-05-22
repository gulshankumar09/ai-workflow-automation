package config

import (
	"fmt"
	"os"
	"time"

	"github.com/spf13/viper"
)

// Config holds all configuration for the application
type Config struct {
	Server       ServerConfig       `mapstructure:"server"`
	GRPC         GRPCConfig         `mapstructure:"grpc"`
	Auth         AuthConfig         `mapstructure:"auth"`
	Supabase     SupabaseConfig     `mapstructure:"supabase"`
	RateLimit    RateLimitConfig    `mapstructure:"rate_limit"`
	CORS         CORSConfig         `mapstructure:"cors"`
	Database     DatabaseConfig     `mapstructure:"database"`
	Monitoring   MonitoringConfig   `mapstructure:"monitoring"`
	Logging      LoggingConfig      `mapstructure:"logging"`
	Environment  string             `mapstructure:"environment"`
}

// ServerConfig contains HTTP server configuration
type ServerConfig struct {
	Port            int           `mapstructure:"port"`
	Host            string        `mapstructure:"host"`
	ReadTimeout     time.Duration `mapstructure:"read_timeout"`
	WriteTimeout    time.Duration `mapstructure:"write_timeout"`
	IdleTimeout     time.Duration `mapstructure:"idle_timeout"`
	ShutdownTimeout time.Duration `mapstructure:"shutdown_timeout"`
	EnableHTTP2     bool          `mapstructure:"enable_http2"`
	TLSCertPath     string        `mapstructure:"tls_cert_path"`
	TLSKeyPath      string        `mapstructure:"tls_key_path"`
}

// GRPCConfig contains gRPC client configuration
type GRPCConfig struct {
	CoreServiceAddr    string        `mapstructure:"core_service_addr"`
	ConnectionTimeout  time.Duration `mapstructure:"connection_timeout"`
	RequestTimeout     time.Duration `mapstructure:"request_timeout"`
	MaxConnectionIdle  time.Duration `mapstructure:"max_connection_idle"`
	MaxConnectionAge   time.Duration `mapstructure:"max_connection_age"`
	KeepAliveTime      time.Duration `mapstructure:"keep_alive_time"`
	KeepAliveTimeout   time.Duration `mapstructure:"keep_alive_timeout"`
	MaxReceiveSize     int           `mapstructure:"max_receive_size"`
	MaxSendSize        int           `mapstructure:"max_send_size"`
	EnableTLS          bool          `mapstructure:"enable_tls"`
	TLSServerName      string        `mapstructure:"tls_server_name"`
}

// AuthConfig contains authentication configuration
type AuthConfig struct {
	Auth0Domain        string        `mapstructure:"auth0_domain"`
	Auth0Audience      string        `mapstructure:"auth0_audience"`
	Auth0ClientID      string        `mapstructure:"auth0_client_id"`
	JWKSCacheTTL       time.Duration `mapstructure:"jwks_cache_ttl"`
}

// SupabaseConfig contains Supabase configuration
type SupabaseConfig struct {
	URL                string        `mapstructure:"url"`
	AnonKey            string        `mapstructure:"anon_key"`
	ServiceRoleKey     string        `mapstructure:"service_role_key"`
	UsersTable         string        `mapstructure:"users_table"`
	ConnectionTimeout  time.Duration `mapstructure:"connection_timeout"`
	QueryTimeout       time.Duration `mapstructure:"query_timeout"`
}

// RateLimitConfig contains rate limiting configuration
type RateLimitConfig struct {
	Enabled        bool          `mapstructure:"enabled"`
	RequestsPerMin int           `mapstructure:"requests_per_minute"`
	BurstSize      int           `mapstructure:"burst_size"`
	CleanupPeriod  time.Duration `mapstructure:"cleanup_period"`
	Strategy       string        `mapstructure:"strategy"` // "memory", "redis"
	RedisAddr      string        `mapstructure:"redis_addr"`
	RedisPassword  string        `mapstructure:"redis_password"`
	RedisDB        int           `mapstructure:"redis_db"`
}

// CORSConfig contains CORS configuration
type CORSConfig struct {
	AllowedOrigins     []string      `mapstructure:"allowed_origins"`
	AllowedMethods     []string      `mapstructure:"allowed_methods"`
	AllowedHeaders     []string      `mapstructure:"allowed_headers"`
	ExposedHeaders     []string      `mapstructure:"exposed_headers"`
	AllowCredentials   bool          `mapstructure:"allow_credentials"`
	MaxAge             time.Duration `mapstructure:"max_age"`
}

// DatabaseConfig contains database configuration
type DatabaseConfig struct {
	URL                string        `mapstructure:"url"`
	MaxConnections     int           `mapstructure:"max_connections"`
	MaxIdleConnections int           `mapstructure:"max_idle_connections"`
	ConnectionTimeout  time.Duration `mapstructure:"connection_timeout"`
	QueryTimeout       time.Duration `mapstructure:"query_timeout"`
}

// MonitoringConfig contains monitoring configuration
type MonitoringConfig struct {
	Enabled              bool   `mapstructure:"enabled"`
	PrometheusEnabled    bool   `mapstructure:"prometheus_enabled"`
	PrometheusPort       int    `mapstructure:"prometheus_port"`
	TracingEnabled       bool   `mapstructure:"tracing_enabled"`
	TracingEndpoint      string `mapstructure:"tracing_endpoint"`
	TracingSampleRate    float64 `mapstructure:"tracing_sample_rate"`
	HealthCheckPath      string `mapstructure:"health_check_path"`
	ReadinessCheckPath   string `mapstructure:"readiness_check_path"`
	LivenessCheckPath    string `mapstructure:"liveness_check_path"`
}

// LoggingConfig contains logging configuration
type LoggingConfig struct {
	Level       string `mapstructure:"level"`
	Format      string `mapstructure:"format"` // "json", "text"
	Output      string `mapstructure:"output"` // "stdout", "file"
	FilePath    string `mapstructure:"file_path"`
	MaxSize     int    `mapstructure:"max_size"`    // MB
	MaxBackups  int    `mapstructure:"max_backups"`
	MaxAge      int    `mapstructure:"max_age"`     // days
	Compress    bool   `mapstructure:"compress"`
}

// LoadConfig loads configuration from environment variables and config files
func LoadConfig(configPath string) (*Config, error) {

	if configPath != "" {
		viper.AddConfigPath(configPath)
	}

	viper.AddConfigPath("./configs")
	viper.AddConfigPath("../../configs")  // For when running from cmd/server
	viper.AddConfigPath(".")

	viper.SetConfigName("config")
	viper.SetConfigType("yaml")

	// Enable automatic environment variable binding
	viper.AutomaticEnv()

	// Set defaults
	setDefaults()

	// Read config file if it exists
	if err := viper.ReadInConfig(); err != nil {
		// Don't fail if config file doesn't exist
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, fmt.Errorf("failed to read config file: %w", err)
		}
	}

	var config Config
	
	// Override with environment variables
	if err := overrideWithEnv(&config); err != nil {
		return nil, fmt.Errorf("failed to override with environment variables: %w", err)
	}

	if err := viper.Unmarshal(&config); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	// Validate configuration
	if err := validateConfig(&config); err != nil {
		return nil, fmt.Errorf("invalid configuration: %w", err)
	}

	return &config, nil
}

// setDefaults sets default configuration values
func setDefaults() {
	// Server defaults
	viper.SetDefault("server.port", 8082)
	viper.SetDefault("server.host", "0.0.0.0")
	viper.SetDefault("server.read_timeout", "30s")
	viper.SetDefault("server.write_timeout", "30s")
	viper.SetDefault("server.idle_timeout", "120s")
	viper.SetDefault("server.shutdown_timeout", "15s")
	viper.SetDefault("server.enable_http2", true)

	// gRPC defaults
	viper.SetDefault("grpc.core_service_addr", "localhost:50051")
	viper.SetDefault("grpc.connection_timeout", "10s")
	viper.SetDefault("grpc.request_timeout", "30s")
	viper.SetDefault("grpc.max_connection_idle", "30s")
	viper.SetDefault("grpc.max_connection_age", "300s")
	viper.SetDefault("grpc.keep_alive_time", "30s")
	viper.SetDefault("grpc.keep_alive_timeout", "5s")
	viper.SetDefault("grpc.max_receive_size", 4*1024*1024) // 4MB
	viper.SetDefault("grpc.max_send_size", 4*1024*1024)    // 4MB
	viper.SetDefault("grpc.enable_tls", false)

	// Auth defaults
	viper.SetDefault("auth.jwks_cache_ttl", "1h")
	viper.SetDefault("auth.enable_rbac", true)
	viper.SetDefault("auth.require_validation", true)
	// Legacy defaults for backward compatibility
	viper.SetDefault("auth.jwt_expiration", "24h")
	viper.SetDefault("auth.refresh_expiration", "168h") // 7 days

	// Rate limit defaults
	viper.SetDefault("rate_limit.enabled", true)
	viper.SetDefault("rate_limit.requests_per_minute", 60)
	viper.SetDefault("rate_limit.burst_size", 10)
	viper.SetDefault("rate_limit.cleanup_period", "1m")
	viper.SetDefault("rate_limit.strategy", "memory")

	// CORS defaults
	viper.SetDefault("cors.allowed_origins", []string{"*"})
	viper.SetDefault("cors.allowed_methods", []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"})
	viper.SetDefault("cors.allowed_headers", []string{"Origin", "Content-Type", "Authorization"})
	viper.SetDefault("cors.exposed_headers", []string{"Content-Length"})
	viper.SetDefault("cors.allow_credentials", true)
	viper.SetDefault("cors.max_age", "12h")

	// Database defaults
	viper.SetDefault("database.max_connections", 25)
	viper.SetDefault("database.max_idle_connections", 10)
	viper.SetDefault("database.connection_timeout", "30s")
	viper.SetDefault("database.query_timeout", "30s")

	// Supabase defaults
	viper.SetDefault("supabase.users_table", "users")
	viper.SetDefault("supabase.connection_timeout", "10s")
	viper.SetDefault("supabase.query_timeout", "5s")

	// Monitoring defaults
	viper.SetDefault("monitoring.enabled", true)
	viper.SetDefault("monitoring.prometheus_enabled", true)
	viper.SetDefault("monitoring.prometheus_port", 9090)
	viper.SetDefault("monitoring.tracing_enabled", false)
	viper.SetDefault("monitoring.tracing_sample_rate", 0.1)
	viper.SetDefault("monitoring.health_check_path", "/health")
	viper.SetDefault("monitoring.readiness_check_path", "/health/ready")
	viper.SetDefault("monitoring.liveness_check_path", "/health/live")

	// Logging defaults
	viper.SetDefault("logging.level", "info")
	viper.SetDefault("logging.format", "json")
	viper.SetDefault("logging.output", "stdout")
	viper.SetDefault("logging.max_size", 100)
	viper.SetDefault("logging.max_backups", 3)
	viper.SetDefault("logging.max_age", 28)
	viper.SetDefault("logging.compress", true)

	// Environment
	viper.SetDefault("environment", "development")
}

// overrideWithEnv overrides configuration with environment variables
func overrideWithEnv(config *Config) error {
	if port := os.Getenv("PORT"); port != "" {
		viper.Set("server.port", port)
	}
	if grpcAddr := os.Getenv("GRPC_CORE_SERVICE_ADDR"); grpcAddr != "" {
		viper.Set("grpc.core_service_addr", grpcAddr)
	}
	if jwtSecret := os.Getenv("JWT_SECRET"); jwtSecret != "" {
		viper.Set("auth.jwt_secret", jwtSecret)
	}
	if auth0Domain := os.Getenv("AUTH0_DOMAIN"); auth0Domain != "" {
		fmt.Println("auth0Domain", auth0Domain)
		viper.Set("auth.auth0_domain", auth0Domain)
	}
	if auth0Audience := os.Getenv("AUTH0_AUDIENCE"); auth0Audience != "" {
		viper.Set("auth.auth0_audience", auth0Audience)
	}
	if auth0ClientID := os.Getenv("AUTH0_CLIENT_ID"); auth0ClientID != "" {
		viper.Set("auth.auth0_client_id", auth0ClientID)
	}
	if supabaseURL := os.Getenv("SUPABASE_URL"); supabaseURL != "" {
		viper.Set("supabase.url", supabaseURL)
	}
	if supabaseAnonKey := os.Getenv("SUPABASE_ANON_KEY"); supabaseAnonKey != "" {
		viper.Set("supabase.anon_key", supabaseAnonKey)
	}
	if supabaseServiceKey := os.Getenv("SUPABASE_SERVICE_ROLE_KEY"); supabaseServiceKey != "" {
		viper.Set("supabase.service_role_key", supabaseServiceKey)
	}
	if dbURL := os.Getenv("DATABASE_URL"); dbURL != "" {
		viper.Set("database.url", dbURL)
	}
	if env := os.Getenv("ENVIRONMENT"); env != "" {
		viper.Set("environment", env)
	}

	return nil
}

// validateConfig validates the configuration
func validateConfig(config *Config) error {
	if config.Server.Port <= 0 || config.Server.Port > 65535 {
		return fmt.Errorf("invalid server port: %d", config.Server.Port)
	}

	if config.GRPC.CoreServiceAddr == "" {
		return fmt.Errorf("gRPC core service address is required")
	}

	if config.Auth.Auth0Domain == "" {
		return fmt.Errorf("Auth0 domain is required")
	}

	if config.Auth.Auth0Audience == "" {
		return fmt.Errorf("Auth0 audience is required")
	}

	if config.Supabase.URL == "" {
		return fmt.Errorf("Supabase URL is required")
	}

	if config.Supabase.ServiceRoleKey == "" {
		return fmt.Errorf("Supabase service role key is required")
	}

	return nil
}

// IsDevelopment returns true if running in development mode
func (c *Config) IsDevelopment() bool {
	return c.Environment == "development"
}

// IsProduction returns true if running in production mode
func (c *Config) IsProduction() bool {
	return c.Environment == "production"
}

// GetServerAddress returns the full server address
func (c *Config) GetServerAddress() string {
	return fmt.Sprintf("%s:%d", c.Server.Host, c.Server.Port)
} 