package grpc_client

import (
	"context"
	"crypto/tls"
	"fmt"
	"log"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"

	"github.com/ai-workflow-automation/api-gateway/internal/config"
	pb "github.com/ai-workflow-automation/api-gateway/pkg/grpc_client/protos"
)

// ClientManager manages gRPC connections and clients
type ClientManager struct {
	config     *config.GRPCConfig
	conn       *grpc.ClientConn
	mu         sync.RWMutex
	isHealthy  bool
	lastCheck  time.Time
	
	// Service clients
	workflowClient   pb.WorkflowServiceClient
	executionClient  pb.ExecutionServiceClient
	chatClient       pb.ChatServiceClient
	userClient       pb.UserServiceClient
}

// ClientManagerOptions contains options for creating a client manager
type ClientManagerOptions struct {
	Config                *config.GRPCConfig
	MaxRetries           int
	RetryBackoff         time.Duration
	HealthCheckInterval  time.Duration
}

// NewClientManager creates a new gRPC client manager
func NewClientManager(opts ClientManagerOptions) (*ClientManager, error) {
	if opts.Config == nil {
		return nil, fmt.Errorf("gRPC config is required")
	}

	manager := &ClientManager{
		config:    opts.Config,
		isHealthy: false,
	}

	// Establish connection
	if err := manager.connect(); err != nil {
		return nil, fmt.Errorf("failed to connect to gRPC server: %w", err)
	}

	// Initialize service clients
	manager.initClients()

	// Start health checking
	go manager.startHealthChecker(opts.HealthCheckInterval)

	return manager, nil
}

// connect establishes a gRPC connection with the configured options
func (cm *ClientManager) connect() error {
	ctx, cancel := context.WithTimeout(context.Background(), cm.config.ConnectionTimeout)
	defer cancel()

	// Configure connection options
	opts := []grpc.DialOption{
		grpc.WithBlock(),
		grpc.WithKeepaliveParams(keepalive.ClientParameters{
			Time:                cm.config.KeepAliveTime,
			Timeout:             cm.config.KeepAliveTimeout,
			PermitWithoutStream: false,
		}),
		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(cm.config.MaxReceiveSize),
			grpc.MaxCallSendMsgSize(cm.config.MaxSendSize),
		),
	}

	// Configure TLS if enabled
	if cm.config.EnableTLS {
		tlsConfig := &tls.Config{
			ServerName: cm.config.TLSServerName,
		}
		opts = append(opts, grpc.WithTransportCredentials(credentials.NewTLS(tlsConfig)))
	} else {
		opts = append(opts, grpc.WithTransportCredentials(insecure.NewCredentials()))
	}

	// Establish connection
	conn, err := grpc.DialContext(ctx, cm.config.CoreServiceAddr, opts...)
	if err != nil {
		return fmt.Errorf("failed to dial gRPC server: %w", err)
	}

	cm.mu.Lock()
	defer cm.mu.Unlock()
	
	cm.conn = conn
	cm.isHealthy = true
	cm.lastCheck = time.Now()

	return nil
}

// initClients initializes all service clients
func (cm *ClientManager) initClients() {
	cm.workflowClient = pb.NewWorkflowServiceClient(cm.conn)
	cm.executionClient = pb.NewExecutionServiceClient(cm.conn)
	cm.chatClient = pb.NewChatServiceClient(cm.conn)
	cm.userClient = pb.NewUserServiceClient(cm.conn)
}

// startHealthChecker starts the background health checking
func (cm *ClientManager) startHealthChecker(interval time.Duration) {
	if interval == 0 {
		interval = 30 * time.Second
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for range ticker.C {
		cm.checkHealth()
		cm.reconnectIfNeeded()
	}
}

// checkHealth checks the health of the gRPC connection
func (cm *ClientManager) checkHealth() {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	if cm.conn == nil {
		cm.isHealthy = false
		return
	}

	state := cm.conn.GetState()
	cm.isHealthy = state == connectivity.Ready || state == connectivity.Idle
	cm.lastCheck = time.Now()

	if !cm.isHealthy {
		log.Printf("WARNING [gRPC]: Connection unhealthy, state: %v", state)
	}
}

// reconnectIfNeeded attempts to reconnect if the connection is unhealthy
func (cm *ClientManager) reconnectIfNeeded() {
	cm.mu.RLock()
	needsReconnect := !cm.isHealthy
	cm.mu.RUnlock()

	if needsReconnect {
		log.Printf("INFO [gRPC]: Attempting to reconnect to gRPC server...")
		if err := cm.Reconnect(); err != nil {
			log.Printf("ERROR [gRPC]: Failed to reconnect: %v", err)
		} else {
			log.Printf("INFO [gRPC]: Successfully reconnected to gRPC server")
		}
	}
}

// Reconnect closes the current connection and establishes a new one
func (cm *ClientManager) Reconnect() error {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	// Close existing connection
	if cm.conn != nil {
		cm.conn.Close()
	}

	// Establish new connection
	if err := cm.connect(); err != nil {
		return err
	}

	// Reinitialize clients
	cm.initClients()
	return nil
}

// Close closes the gRPC connection
func (cm *ClientManager) Close() error {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	if cm.conn != nil {
		err := cm.conn.Close()
		cm.conn = nil
		cm.isHealthy = false
		return err
	}
	return nil
}

// IsHealthy returns the current health status of the connection
func (cm *ClientManager) IsHealthy() bool {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	return cm.isHealthy
}

// GetLastHealthCheck returns the time of the last health check
func (cm *ClientManager) GetLastHealthCheck() time.Time {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	return cm.lastCheck
}

// GetConnectionState returns the current connection state
func (cm *ClientManager) GetConnectionState() connectivity.State {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	
	if cm.conn == nil {
		return connectivity.Shutdown
	}
	return cm.conn.GetState()
}

// Service client getters with health checks

// WorkflowClient returns the workflow service client
func (cm *ClientManager) WorkflowClient() (pb.WorkflowServiceClient, error) {
	if !cm.IsHealthy() {
		return nil, fmt.Errorf("gRPC connection is not healthy")
	}
	return cm.workflowClient, nil
}

// ExecutionClient returns the execution service client
func (cm *ClientManager) ExecutionClient() (pb.ExecutionServiceClient, error) {
	if !cm.IsHealthy() {
		return nil, fmt.Errorf("gRPC connection is not healthy")
	}
	return cm.executionClient, nil
}

// ChatClient returns the chat service client
func (cm *ClientManager) ChatClient() (pb.ChatServiceClient, error) {
	if !cm.IsHealthy() {
		return nil, fmt.Errorf("gRPC connection is not healthy")
	}
	return cm.chatClient, nil
}

// UserClient returns the user service client
func (cm *ClientManager) UserClient() (pb.UserServiceClient, error) {
	if !cm.IsHealthy() {
		return nil, fmt.Errorf("gRPC connection is not healthy")
	}
	return cm.userClient, nil
}

// WithContext creates a context with the configured request timeout
func (cm *ClientManager) WithContext(ctx context.Context) (context.Context, context.CancelFunc) {
	return context.WithTimeout(ctx, cm.config.RequestTimeout)
}

// CircuitBreakerWrapper wraps gRPC calls with circuit breaker logic
type CircuitBreakerWrapper struct {
	manager           *ClientManager
	failureThreshold  int
	successThreshold  int
	timeout           time.Duration
	currentFailures   int
	lastFailureTime   time.Time
	state             string // "closed", "open", "half-open"
	mu                sync.RWMutex
}

// NewCircuitBreakerWrapper creates a new circuit breaker wrapper
func NewCircuitBreakerWrapper(manager *ClientManager, failureThreshold, successThreshold int, timeout time.Duration) *CircuitBreakerWrapper {
	return &CircuitBreakerWrapper{
		manager:          manager,
		failureThreshold: failureThreshold,
		successThreshold: successThreshold,
		timeout:          timeout,
		state:           "closed",
	}
}

// Call executes a function with circuit breaker protection
func (cb *CircuitBreakerWrapper) Call(fn func() error) error {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	// Check if circuit breaker should open
	if cb.state == "closed" && cb.currentFailures >= cb.failureThreshold {
		cb.state = "open"
		cb.lastFailureTime = time.Now()
	}

	// Check if circuit breaker should move to half-open
	if cb.state == "open" && time.Since(cb.lastFailureTime) >= cb.timeout {
		cb.state = "half-open"
	}

	// Reject calls if circuit breaker is open
	if cb.state == "open" {
		return fmt.Errorf("circuit breaker is open")
	}

	// Execute the function
	err := fn()
	
	if err != nil {
		cb.currentFailures++
		if cb.state == "half-open" {
			cb.state = "open"
			cb.lastFailureTime = time.Now()
		}
		return err
	}

	// Reset on success
	if cb.state == "half-open" {
		cb.state = "closed"
	}
	cb.currentFailures = 0
	return nil
}

// GetState returns the current circuit breaker state
func (cb *CircuitBreakerWrapper) GetState() string {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
} 