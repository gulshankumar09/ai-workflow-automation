package middleware

import (
	"log"
	"net/http"
	"runtime"

	"github.com/ai-workflow-automation/api-gateway/internal/models"
	"github.com/gin-gonic/gin"
)

// ErrorRecoveryMiddleware handles panics and converts them to proper error responses
func ErrorRecoveryMiddleware() gin.HandlerFunc {
	return gin.CustomRecovery(func(c *gin.Context, err interface{}) {
		// Get request ID for correlation
		correlationID := GetRequestID(c)
		
		// Log the panic with stack trace
		stack := make([]byte, 4<<10) // 4KB
		length := runtime.Stack(stack, false)
		if gin.Mode() != gin.ReleaseMode {
			log.Printf("PANIC RECOVERED [%s]: %v\nType: %T\nStack trace:\n%s", correlationID, err, err, stack[:length])
		} else {
			log.Printf("PANIC RECOVERED [%s]: %v", correlationID, err)
		}

		// Create error response
		errorResponse := models.NewErrorResponse(
			models.CodeInternalError,
			"An unexpected error occurred",
			correlationID,
		)

		// Add panic details in non-production environments
		if gin.Mode() != gin.ReleaseMode {
			if errorResponse.Details == nil {
				errorResponse.Details = make(map[string]interface{})
			}
			errorResponse.Details["panic"] = err
			errorResponse.Details["stack_trace"] = string(stack[:length])
		}

		c.Header("Content-Type", "application/json")
		c.JSON(http.StatusInternalServerError, errorResponse)
		c.Abort()
	})
}

// ErrorHandlerMiddleware provides centralized error handling
func ErrorHandlerMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()

		// Check for errors that occurred during request processing
		if len(c.Errors) > 0 {
			correlationID := GetRequestID(c)
			
			// Get the last error (most recent)
			err := c.Errors.Last()
			
					// Log the error with more context in debug mode
		if gin.Mode() != gin.ReleaseMode {
			log.Printf("REQUEST ERROR [%s]: %v\nType: %T\nMeta: %+v", correlationID, err.Err, err.Err, err.Meta)
		} else {
			log.Printf("REQUEST ERROR [%s]: %v", correlationID, err.Err)
		}

			// Check if response was already written
			if c.Writer.Written() {
				return
			}

			// Determine if it's a known error type
			if apiErr, ok := err.Meta.(*models.ErrorResponse); ok {
				status := models.GetHTTPStatusFromCode(apiErr.Code)
				c.JSON(status, apiErr)
			} else {
				// Generic error response
				errorResponse := models.NewErrorResponse(
					models.CodeInternalError,
					"An error occurred while processing the request",
					correlationID,
				)
				c.JSON(http.StatusInternalServerError, errorResponse)
			}
		}
	}
}

// AbortWithError creates an error response and aborts the request
func AbortWithError(c *gin.Context, code string, message string) {
	correlationID := GetRequestID(c)
	errorResponse := models.NewErrorResponse(code, message, correlationID)
	status := models.GetHTTPStatusFromCode(code)
	
	c.JSON(status, errorResponse)
	c.Abort()
}

// AbortWithGRPCError converts a gRPC error and aborts the request
func AbortWithGRPCError(c *gin.Context, err error) {
	correlationID := GetRequestID(c)
	status, errorResponse := models.ConvertGRPCError(err, correlationID)
	
	c.JSON(status, errorResponse)
	c.Abort()
}

// AbortWithValidationError handles validation errors
func AbortWithValidationError(c *gin.Context, validationErrors []models.ValidationError) {
	correlationID := GetRequestID(c)
	errorResponse := models.NewValidationErrorResponse(correlationID, validationErrors)
	
	c.JSON(http.StatusBadRequest, errorResponse)
	c.Abort()
} 