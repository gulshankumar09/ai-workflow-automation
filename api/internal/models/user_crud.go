package models

import (
	"time"

	"github.com/google/uuid"
)

// User CRUD Request Models

type CreateUserRequest struct {
	Name      string `json:"name,omitempty" validate:"omitempty,min=1,max=255"`
	Email     string `json:"email,omitempty" validate:"omitempty,email"`
	AvatarURL string `json:"avatar_url,omitempty" validate:"omitempty,url"`
	AuthID    string `json:"auth_id" binding:"required" validate:"required"`
}

type UpdateUserRequest struct {
	Name      *string `json:"name,omitempty" validate:"omitempty,min=1,max=255"`
	Email     *string `json:"email,omitempty" validate:"omitempty,email"`
	AvatarURL *string `json:"avatar_url,omitempty" validate:"omitempty,url"`
}

type GetUsersRequest struct {
	Limit  int    `form:"limit,omitempty" validate:"omitempty,min=1,max=100"`
	Offset int    `form:"offset,omitempty" validate:"omitempty,min=0"`
	Search string `form:"search,omitempty" validate:"omitempty,max=255"`
	SortBy string `form:"sort_by,omitempty" validate:"omitempty,oneof=name email created_at updated_at"`
	Order  string `form:"order,omitempty" validate:"omitempty,oneof=asc desc"`
}

// User CRUD Response Models

type CreateUserResponse struct {
	User    *UserDetails `json:"user"`
	Success bool         `json:"success"`
	Message string       `json:"message,omitempty"`
}

type GetUserResponse struct {
	User    *UserDetails `json:"user"`
	Success bool         `json:"success"`
	Message string       `json:"message,omitempty"`
}

type UpdateUserResponse struct {
	User    *UserDetails `json:"user"`
	Success bool         `json:"success"`
	Message string       `json:"message,omitempty"`
}

type DeleteUserResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message,omitempty"`
}

type GetUsersResponse struct {
	Users      []*UserDetails `json:"users"`
	TotalCount int            `json:"total_count"`
	Limit      int            `json:"limit"`
	Offset     int            `json:"offset"`
	Success    bool           `json:"success"`
	Message    string         `json:"message,omitempty"`
}

// User Data Model for CRUD operations
type UserDetails struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Email     string    `json:"email"`
	AvatarURL string    `json:"avatar_url"`
	AuthID    string    `json:"auth_id"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// Validation helpers

// Simple validation error type
type UserValidationError struct {
	Message string
}

func (e *UserValidationError) Error() string {
	return e.Message
}

func NewValidationError(message string) error {
	return &UserValidationError{Message: message}
}

func (req *CreateUserRequest) Validate() error {
	if req.AuthID == "" {
		return NewValidationError("auth_id is required")
	}
	// Name and email are optional in request (will be taken from Auth0 token)
	// But if provided, they should be valid
	if req.Name != "" && len(req.Name) > 255 {
		return NewValidationError("name cannot exceed 255 characters")
	}
	return nil
}

func (req *UpdateUserRequest) Validate() error {
	if req.Name != nil && *req.Name == "" {
		return NewValidationError("name cannot be empty")
	}
	if req.Email != nil && *req.Email == "" {
		return NewValidationError("email cannot be empty")
	}
	return nil
}

func (req *GetUsersRequest) SetDefaults() {
	if req.Limit == 0 {
		req.Limit = 20
	}
	if req.Offset < 0 {
		req.Offset = 0
	}
	if req.SortBy == "" {
		req.SortBy = "created_at"
	}
	if req.Order == "" {
		req.Order = "desc"
	}
}

// Helper function to generate new UUID
func GenerateUUID() string {
	return uuid.New().String()
}

// Constants for user operations
const (
	MaxUsersPerPage     = 100
	DefaultUsersPerPage = 20
) 