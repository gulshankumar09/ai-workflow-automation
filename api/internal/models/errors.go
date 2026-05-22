package models

import (
	"net/http"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// ErrorResponse represents a standardized API error response
type ErrorResponse struct {
	Error         string                 `json:"error"`
	Code          string                 `json:"code"`
	Message       string                 `json:"message"`
	CorrelationID string                 `json:"correlation_id"`
	Details       map[string]interface{} `json:"details,omitempty"`
	Timestamp     time.Time              `json:"timestamp"`
}

// ValidationError represents a field validation error
type ValidationError struct {
	Field   string `json:"field"`
	Message string `json:"message"`
	Code    string `json:"code"`
	Value   string `json:"value,omitempty"`
}

// ErrorCode constants for common error types
const (
	// Authentication and Authorization
	CodeUnauthorized         = "UNAUTHORIZED"
	CodeForbidden           = "FORBIDDEN" 
	CodeInvalidToken        = "INVALID_TOKEN"
	CodeTokenExpired        = "TOKEN_EXPIRED"
	CodeMissingAuthHeader   = "MISSING_AUTH_HEADER"
	CodeInvalidAuthFormat   = "INVALID_AUTH_FORMAT"
	CodeInsufficientRole    = "INSUFFICIENT_ROLE"
	
	// Validation
	CodeValidationFailed    = "VALIDATION_FAILED"
	CodeInvalidInput        = "INVALID_INPUT"
	CodeInvalidFormat       = "INVALID_FORMAT"
	CodeRequiredField       = "REQUIRED_FIELD"
	
	// Resources
	CodeNotFound           = "NOT_FOUND"
	CodeConflict           = "CONFLICT"
	CodeAlreadyExists      = "ALREADY_EXISTS"
	
	// Rate Limiting
	CodeRateLimitExceeded  = "RATE_LIMIT_EXCEEDED"
	CodeRateLimiterError   = "RATE_LIMITER_ERROR"
	
	// Server Errors
	CodeInternalError      = "INTERNAL_ERROR"
	CodeServiceUnavailable = "SERVICE_UNAVAILABLE"
	CodeGRPCError          = "GRPC_ERROR"
	CodeTimeout            = "TIMEOUT"
	CodeCircuitBreakerOpen = "CIRCUIT_BREAKER_OPEN"
	
	// Business Logic
	CodeWorkflowNotFound   = "WORKFLOW_NOT_FOUND"
	CodeExecutionFailed    = "EXECUTION_FAILED"
	CodeChatSessionClosed  = "CHAT_SESSION_CLOSED"
)

// NewErrorResponse creates a new error response
func NewErrorResponse(code, message, correlationID string) *ErrorResponse {
	return &ErrorResponse{
		Error:         http.StatusText(GetHTTPStatusFromCode(code)),
		Code:          code,
		Message:       message,
		CorrelationID: correlationID,
		Timestamp:     time.Now(),
	}
}

// NewValidationErrorResponse creates an error response for validation failures
func NewValidationErrorResponse(correlationID string, validationErrors []ValidationError) *ErrorResponse {
	details := map[string]interface{}{
		"validation_errors": validationErrors,
	}
	
	return &ErrorResponse{
		Error:         "Bad Request",
		Code:          CodeValidationFailed,
		Message:       "Request validation failed",
		CorrelationID: correlationID,
		Details:       details,
		Timestamp:     time.Now(),
	}
}

// ConvertGRPCError converts a gRPC error to HTTP error response
func ConvertGRPCError(err error, correlationID string) (int, *ErrorResponse) {
	st, ok := status.FromError(err)
	if !ok {
		return 500, &ErrorResponse{
			Error:         "Internal Server Error",
			Code:          CodeInternalError,
			Message:       "An unexpected error occurred",
			CorrelationID: correlationID,
			Timestamp:     time.Now(),
		}
	}

	var httpStatus int
	var errorCode string
	var message string

	switch st.Code() {
	case codes.OK:
		httpStatus = 200
		errorCode = ""
		message = ""
	case codes.InvalidArgument:
		httpStatus = 400
		errorCode = CodeInvalidInput
		message = st.Message()
	case codes.Unauthenticated:
		httpStatus = 401
		errorCode = CodeUnauthorized
		message = "Authentication required"
	case codes.PermissionDenied:
		httpStatus = 403
		errorCode = CodeForbidden
		message = "Permission denied"
	case codes.NotFound:
		httpStatus = 404
		errorCode = CodeNotFound
		message = st.Message()
	case codes.AlreadyExists:
		httpStatus = 409
		errorCode = CodeAlreadyExists
		message = st.Message()
	case codes.ResourceExhausted:
		httpStatus = 429
		errorCode = CodeRateLimitExceeded
		message = "Rate limit exceeded"
	case codes.Canceled:
		httpStatus = 408
		errorCode = CodeTimeout
		message = "Request was canceled"
	case codes.DeadlineExceeded:
		httpStatus = 408
		errorCode = CodeTimeout
		message = "Request timeout"
	case codes.Unimplemented:
		httpStatus = 501
		errorCode = CodeServiceUnavailable
		message = "Service not implemented"
	case codes.Unavailable:
		httpStatus = 503
		errorCode = CodeServiceUnavailable
		message = "Service temporarily unavailable"
	default:
		httpStatus = 500
		errorCode = CodeGRPCError
		message = st.Message()
	}

	// Add gRPC details if available
	details := make(map[string]interface{})
	if len(st.Details()) > 0 {
		details["grpc_details"] = st.Details()
	}
	details["grpc_code"] = st.Code().String()

	if httpStatus == 200 {
		return httpStatus, nil
	}

	return httpStatus, &ErrorResponse{
		Error:         http.StatusText(httpStatus),
		Code:          errorCode,
		Message:       message,
		CorrelationID: correlationID,
		Details:       details,
		Timestamp:     time.Now(),
	}
}

// GetHTTPStatusFromCode maps error codes to HTTP status codes
func GetHTTPStatusFromCode(code string) int {
	switch code {
	case CodeUnauthorized, CodeInvalidToken, CodeTokenExpired, CodeMissingAuthHeader, CodeInvalidAuthFormat:
		return 401
	case CodeForbidden, CodeInsufficientRole:
		return 403
	case CodeNotFound, CodeWorkflowNotFound:
		return 404
	case CodeConflict, CodeAlreadyExists:
		return 409
	case CodeRateLimitExceeded:
		return 429
	case CodeValidationFailed, CodeInvalidInput, CodeInvalidFormat, CodeRequiredField:
		return 400
	case CodeTimeout:
		return 408
	case CodeServiceUnavailable, CodeCircuitBreakerOpen:
		return 503
	case CodeInternalError, CodeGRPCError, CodeRateLimiterError, CodeExecutionFailed:
		return 500
	default:
		return 500
	}
}

// IsRetryableError determines if an error is retryable
func IsRetryableError(code string) bool {
	retryableCodes := map[string]bool{
		CodeTimeout:            true,
		CodeServiceUnavailable: true,
		CodeCircuitBreakerOpen: true,
		CodeInternalError:      true,
		CodeGRPCError:          true,
	}
	return retryableCodes[code]
} 