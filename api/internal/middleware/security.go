package middleware

import (
	"github.com/gin-gonic/gin"
)

// SecurityHeadersMiddleware adds common security headers to responses
func SecurityHeadersMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Prevent MIME type sniffing
		c.Header("X-Content-Type-Options", "nosniff")
		
		// Enable XSS protection
		c.Header("X-XSS-Protection", "1; mode=block")
		
		// Prevent clickjacking
		c.Header("X-Frame-Options", "DENY")
		
		// Enforce HTTPS in production
		c.Header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
		
		// Referrer policy
		c.Header("Referrer-Policy", "strict-origin-when-cross-origin")
		
		// Content Security Policy (basic)
		c.Header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'")
		
		// Remove server information
		c.Header("Server", "")

		c.Next()
	}
} 