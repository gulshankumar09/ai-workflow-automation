package validator

import (
	"fmt"
	"reflect"
	"strings"

	"github.com/ai-workflow-automation/api-gateway/internal/models"
	"github.com/gin-gonic/gin"
	"github.com/go-playground/validator/v10"
)

var validate *validator.Validate

func init() {
	validate = validator.New()
	
	// Register custom validation functions
	validate.RegisterValidation("uuid", validateUUID)
	
	// Use JSON tag names in error messages
	validate.RegisterTagNameFunc(func(fld reflect.StructField) string {
		name := strings.SplitN(fld.Tag.Get("json"), ",", 2)[0]
		if name == "-" {
			return ""
		}
		return name
	})
}

// ValidateStruct validates a struct and returns validation errors
func ValidateStruct(s interface{}) []models.ValidationError {
	var validationErrors []models.ValidationError
	
	err := validate.Struct(s)
	if err != nil {
		for _, err := range err.(validator.ValidationErrors) {
			validationErrors = append(validationErrors, models.ValidationError{
				Field:   err.Field(),
				Message: getErrorMessage(err),
				Code:    getErrorCode(err.Tag()),
				Value:   fmt.Sprintf("%v", err.Value()),
			})
		}
	}
	
	return validationErrors
}

// ValidateJSONBinding validates JSON binding and custom validation
func ValidateJSONBinding(c *gin.Context, obj interface{}) []models.ValidationError {
	var validationErrors []models.ValidationError
	
	// First check binding errors (JSON format, required fields with binding tag)
	if err := c.ShouldBindJSON(obj); err != nil {
		validationErrors = append(validationErrors, models.ValidationError{
			Field:   "request_body",
			Message: "Invalid JSON format or required field missing",
			Code:    models.CodeInvalidFormat,
		})
		return validationErrors
	}
	
	// Then validate with custom validator
	customErrors := ValidateStruct(obj)
	validationErrors = append(validationErrors, customErrors...)
	
	return validationErrors
}

// ValidateQueryBinding validates query parameters
func ValidateQueryBinding(c *gin.Context, obj interface{}) []models.ValidationError {
	var validationErrors []models.ValidationError
	
	// Bind query parameters
	if err := c.ShouldBindQuery(obj); err != nil {
		validationErrors = append(validationErrors, models.ValidationError{
			Field:   "query_params",
			Message: "Invalid query parameters",
			Code:    models.CodeInvalidInput,
		})
		return validationErrors
	}
	
	// Validate with custom validator
	customErrors := ValidateStruct(obj)
	validationErrors = append(validationErrors, customErrors...)
	
	return validationErrors
}

// validateUUID validates UUID format
func validateUUID(fl validator.FieldLevel) bool {
	uuid := fl.Field().String()
	if uuid == "" {
		return true // Allow empty UUIDs (optional validation)
	}
	
	// Simple UUID format check (8-4-4-4-12 hex characters)
	parts := strings.Split(uuid, "-")
	if len(parts) != 5 {
		return false
	}
	
	expectedLengths := []int{8, 4, 4, 4, 12}
	for i, part := range parts {
		if len(part) != expectedLengths[i] {
			return false
		}
		
		// Check if all characters are hex
		for _, char := range part {
			if !((char >= '0' && char <= '9') || 
				 (char >= 'a' && char <= 'f') ||
				 (char >= 'A' && char <= 'F')) {
				return false
			}
		}
	}
	
	return true
}

// getErrorMessage converts validation errors to user-friendly messages
func getErrorMessage(err validator.FieldError) string {
	switch err.Tag() {
	case "required":
		return fmt.Sprintf("%s is required", err.Field())
	case "min":
		return fmt.Sprintf("%s must be at least %s characters", err.Field(), err.Param())
	case "max":
		return fmt.Sprintf("%s must be at most %s characters", err.Field(), err.Param())
	case "len":
		return fmt.Sprintf("%s must be exactly %s characters", err.Field(), err.Param())
	case "email":
		return fmt.Sprintf("%s must be a valid email address", err.Field())
	case "uuid":
		return fmt.Sprintf("%s must be a valid UUID", err.Field())
	case "oneof":
		return fmt.Sprintf("%s must be one of: %s", err.Field(), err.Param())
	case "gte":
		return fmt.Sprintf("%s must be greater than or equal to %s", err.Field(), err.Param())
	case "lte":
		return fmt.Sprintf("%s must be less than or equal to %s", err.Field(), err.Param())
	case "gt":
		return fmt.Sprintf("%s must be greater than %s", err.Field(), err.Param())
	case "lt":
		return fmt.Sprintf("%s must be less than %s", err.Field(), err.Param())
	default:
		return fmt.Sprintf("%s is invalid", err.Field())
	}
}

// getErrorCode maps validation tags to error codes
func getErrorCode(tag string) string {
	switch tag {
	case "required":
		return models.CodeRequiredField
	case "min", "max", "len", "gte", "lte", "gt", "lt":
		return models.CodeInvalidFormat
	case "email", "uuid":
		return models.CodeInvalidFormat
	case "oneof":
		return models.CodeInvalidInput
	default:
		return models.CodeValidationFailed
	}
} 