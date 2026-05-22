package middleware

import (
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/ulule/limiter/v3"
	ginlimiter "github.com/ulule/limiter/v3/drivers/middleware/gin"
	"github.com/ulule/limiter/v3/drivers/store/memory"

	"github.com/ai-workflow-automation/api-gateway/internal/config"
)

// RateLimitMiddleware creates a rate limiting middleware
func RateLimitMiddleware(config config.RateLimitConfig) gin.HandlerFunc {
	if !config.Enabled {
		return func(c *gin.Context) {
			c.Next()
		}
	}

	// Create rate limiter
	rate := limiter.Rate{
		Period: time.Minute,
		Limit:  int64(config.RequestsPerMin),
	}

	// Create store (currently only memory store is implemented)
	store := memory.NewStore()

	// Create limiter instance
	instance := limiter.New(store, rate)

	// Create middleware with custom key function
	keyFunc := func(c *gin.Context) string {
		// Try to get user ID from context first
		if userID, exists := c.Get("user_id"); exists {
			if id, ok := userID.(string); ok && id != "" {
				return fmt.Sprintf("user:%s", id)
			}
		}
		
		// Fall back to IP address
		return c.ClientIP()
	}

	// Create gin limiter middleware
	return ginlimiter.NewMiddleware(instance, ginlimiter.WithKeyGetter(keyFunc))
} 