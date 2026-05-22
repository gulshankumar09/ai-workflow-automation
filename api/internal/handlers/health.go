package handlers

import (
	"net/http"
	"time"

	"github.com/ai-workflow-automation/api-gateway/pkg/grpc_client"
	"github.com/gin-gonic/gin"
)

// HealthHandler handles health check endpoints
type HealthHandler struct {
	grpcManager *grpc_client.ClientManager
}

// NewHealthHandler creates a new health handler
func NewHealthHandler(grpcManager *grpc_client.ClientManager) *HealthHandler {
	return &HealthHandler{
		grpcManager: grpcManager,
	}
}

// HealthCheck godoc
// @Summary Health check endpoint
// @Description Returns the health status of the API Gateway
// @Tags health
// @Produce json
// @Success 200 {object} map[string]interface{}
// @Router /health [get]
func (h *HealthHandler) HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "healthy",
		"timestamp": time.Now(),
		"service":   "ai-workflow-automation-api-gateway",
		"version":   "1.0.0",
	})
}

// ReadinessCheck godoc
// @Summary Readiness probe endpoint
// @Description Checks if the API Gateway is ready to handle requests (including gRPC connectivity)
// @Tags health
// @Produce json
// @Success 200 {object} map[string]interface{}
// @Failure 503 {object} map[string]interface{}
// @Router /health/ready [get]
func (h *HealthHandler) ReadinessCheck(c *gin.Context) {
	// Check gRPC connections
	if !h.grpcManager.IsHealthy() {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"status":    "unhealthy",
			"reason":    "gRPC connection failed",
			"timestamp": time.Now(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"status":    "ready",
		"timestamp": time.Now(),
	})
}

// LivenessCheck godoc
// @Summary Liveness probe endpoint
// @Description Checks if the API Gateway is alive
// @Tags health
// @Produce json
// @Success 200 {object} map[string]interface{}
// @Router /health/live [get]
func (h *HealthHandler) LivenessCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "alive",
		"timestamp": time.Now(),
	})
} 