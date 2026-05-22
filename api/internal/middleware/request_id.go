package middleware

import (
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

const RequestIDKey = "request_id"

// RequestIDMiddleware adds a unique request ID to each request
func RequestIDMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Check if request ID is already provided in headers
		requestID := c.GetHeader("X-Request-ID")
		if requestID == "" {
			// Generate a new UUID for the request
			requestID = uuid.New().String()
		}

		// Set request ID in context
		c.Set(RequestIDKey, requestID)
		
		// Add request ID to response headers
		c.Header("X-Request-ID", requestID)
		
		// Add request ID to request headers for downstream services
		c.Request.Header.Set("X-Request-ID", requestID)

		c.Next()
	}
}

// GetRequestID extracts request ID from the Gin context
func GetRequestID(c *gin.Context) string {
	if requestID, exists := c.Get(RequestIDKey); exists {
		if id, ok := requestID.(string); ok {
			return id
		}
	}
	return ""
} 