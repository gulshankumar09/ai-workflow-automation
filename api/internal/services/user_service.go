package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/ai-workflow-automation/api-gateway/internal/config"
)

// User represents a user from the Supabase users table
type User struct {
	ID        string     `json:"id"`
	Name      string     `json:"name"`
	Email     string     `json:"email"`
	AvatarURL string     `json:"avatar_url"`
	AuthID    string     `json:"auth_id"`
	CreatedAt time.Time  `json:"created_at"`
}

// CreateUserRequest represents the data needed to create a new user (excludes auto-generated fields)
type CreateUserRequest struct {
	Name      string `json:"name"`
	Email     string `json:"email"`
	AvatarURL string `json:"avatar_url"`
	AuthID    string `json:"auth_id"`
}

// UserService handles user-related operations with Supabase
type UserService struct {
	config     config.SupabaseConfig
	httpClient *http.Client
}

// NewUserService creates a new UserService instance
func NewUserService(cfg config.SupabaseConfig) *UserService {
	return &UserService{
		config: cfg,
		httpClient: &http.Client{
			Timeout: cfg.ConnectionTimeout,
		},
	}
}

// GetUserByAuthID fetches a user by their Auth0 ID from Supabase
func (s *UserService) GetUserByAuthID(ctx context.Context, authID string) (*User, error) {
	// Prepare the query URL
	url := fmt.Sprintf("%s/rest/v1/%s?auth_id=eq.%s&select=*", 
		s.config.URL, s.config.UsersTable, authID)

	// Create request context with timeout
	reqCtx, cancel := context.WithTimeout(ctx, s.config.QueryTimeout)
	defer cancel()

	// Create HTTP request
	req, err := http.NewRequestWithContext(reqCtx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set required Supabase headers
	req.Header.Set("apikey", s.config.ServiceRoleKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", s.config.ServiceRoleKey))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "return=representation")

	// Execute request
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Check response status
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("supabase request failed with status %d", resp.StatusCode)
	}

	// Parse response
	var users []User
	if err := json.NewDecoder(resp.Body).Decode(&users); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	// Check if user was found
	if len(users) == 0 {
		return nil, fmt.Errorf("user not found with auth_id: %s", authID)
	}

	if len(users) > 1 {
		return nil, fmt.Errorf("multiple users found with auth_id: %s", authID)
	}

	return &users[0], nil
}

// CreateUser creates a new user in Supabase (for future use)
func (s *UserService) CreateUser(ctx context.Context, user User) (*User, error) {
	// Prepare the request URL
	url := fmt.Sprintf("%s/rest/v1/%s", s.config.URL, s.config.UsersTable)

	// Create request payload without auto-generated fields
	createRequest := CreateUserRequest{
		Name:      user.Name,
		Email:     user.Email,
		AvatarURL: user.AvatarURL,
		AuthID:    user.AuthID,
	}

	// Prepare request body
	requestBody, err := json.Marshal(createRequest)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal user data: %w", err)
	}

	// Create request context with timeout
	reqCtx, cancel := context.WithTimeout(ctx, s.config.QueryTimeout)
	defer cancel()

	// Create HTTP request
	req, err := http.NewRequestWithContext(reqCtx, "POST", url, bytes.NewBuffer(requestBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set required Supabase headers
	req.Header.Set("apikey", s.config.ServiceRoleKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", s.config.ServiceRoleKey))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "return=representation")

	// Execute request
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Check response status
	if resp.StatusCode != http.StatusCreated {
		// Read the response body to get detailed error information
		bodyBytes, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, fmt.Errorf("supabase create request failed with status %d (could not read error details)", resp.StatusCode)
		}
		return nil, fmt.Errorf("supabase create request failed with status %d: %s", resp.StatusCode, string(bodyBytes))
	}

	// Parse response
	var createdUsers []User
	if err := json.NewDecoder(resp.Body).Decode(&createdUsers); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	if len(createdUsers) == 0 {
		return nil, fmt.Errorf("no user returned from create operation")
	}

	return &createdUsers[0], nil
}

// GetAllUsers fetches multiple users with pagination and filtering
func (s *UserService) GetAllUsers(ctx context.Context, limit, offset int, search, sortBy, order string) ([]User, int, error) {
	// Build query URL with filters
	url := fmt.Sprintf("%s/rest/v1/%s", s.config.URL, s.config.UsersTable)
	
	// Add query parameters
	params := make([]string, 0)
	
	// Add search filter if provided
	if search != "" {
		// Search in name and email fields
		searchFilter := fmt.Sprintf("or=(name.ilike.*%s*,email.ilike.*%s*)", search, search)
		params = append(params, searchFilter)
	}
	
	// Add sorting
	if sortBy != "" && order != "" {
		sortParam := fmt.Sprintf("%s.%s", sortBy, order)
		params = append(params, fmt.Sprintf("order=%s", sortParam))
	}
	
	// Add pagination
	params = append(params, fmt.Sprintf("limit=%d", limit))
	params = append(params, fmt.Sprintf("offset=%d", offset))
	
	// Add select all fields
	params = append(params, "select=*")
	
	if len(params) > 0 {
		url += "?" + strings.Join(params, "&")
	}

	// Create request context with timeout
	reqCtx, cancel := context.WithTimeout(ctx, s.config.QueryTimeout)
	defer cancel()

	// Create HTTP request
	req, err := http.NewRequestWithContext(reqCtx, "GET", url, nil)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to create request: %w", err)
	}

	// Set required Supabase headers
	req.Header.Set("apikey", s.config.ServiceRoleKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", s.config.ServiceRoleKey))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "count=exact")

	// Execute request
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Check response status
	if resp.StatusCode != http.StatusOK {
		return nil, 0, fmt.Errorf("supabase request failed with status %d", resp.StatusCode)
	}

	// Parse response
	var users []User
	if err := json.NewDecoder(resp.Body).Decode(&users); err != nil {
		return nil, 0, fmt.Errorf("failed to decode response: %w", err)
	}

	// Get total count from Content-Range header
	totalCount := 0
	if contentRange := resp.Header.Get("Content-Range"); contentRange != "" {
		// Parse format: "0-19/100" to get total count
		parts := strings.Split(contentRange, "/")
		if len(parts) == 2 {
			if count, err := strconv.Atoi(parts[1]); err == nil {
				totalCount = count
			}
		}
	}

	return users, totalCount, nil
}

// GetUserByID fetches a user by their Supabase UUID
func (s *UserService) GetUserByID(ctx context.Context, userID string) (*User, error) {
	// Prepare the query URL
	url := fmt.Sprintf("%s/rest/v1/%s?id=eq.%s&select=*", 
		s.config.URL, s.config.UsersTable, userID)

	// Create request context with timeout
	reqCtx, cancel := context.WithTimeout(ctx, s.config.QueryTimeout)
	defer cancel()

	// Create HTTP request
	req, err := http.NewRequestWithContext(reqCtx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set required Supabase headers
	req.Header.Set("apikey", s.config.ServiceRoleKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", s.config.ServiceRoleKey))
	req.Header.Set("Content-Type", "application/json")

	// Execute request
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Check response status
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("supabase request failed with status %d", resp.StatusCode)
	}

	// Parse response
	var users []User
	if err := json.NewDecoder(resp.Body).Decode(&users); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	// Check if user was found
	if len(users) == 0 {
		return nil, fmt.Errorf("user not found with id: %s", userID)
	}

	return &users[0], nil
}

// UpdateUser updates an existing user by their Supabase UUID
func (s *UserService) UpdateUser(ctx context.Context, userID string, updates User) (*User, error) {
	// Prepare the request URL
	url := fmt.Sprintf("%s/rest/v1/%s?id=eq.%s", s.config.URL, s.config.UsersTable, userID)

	// Only include non-empty fields in the update
	updateData := make(map[string]interface{})
	if updates.Name != "" {
		updateData["name"] = updates.Name
	}
	if updates.Email != "" {
		updateData["email"] = updates.Email
	}
	if updates.AvatarURL != "" {
		updateData["avatar_url"] = updates.AvatarURL
	}
	// Always update the updated_at timestamp
	updateData["updated_at"] = time.Now()

	// Prepare request body
	requestBody, err := json.Marshal(updateData)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal update data: %w", err)
	}

	// Create request context with timeout
	reqCtx, cancel := context.WithTimeout(ctx, s.config.QueryTimeout)
	defer cancel()

	// Create HTTP request
	req, err := http.NewRequestWithContext(reqCtx, "PATCH", url, bytes.NewBuffer(requestBody))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set required Supabase headers
	req.Header.Set("apikey", s.config.ServiceRoleKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", s.config.ServiceRoleKey))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Prefer", "return=representation")

	// Execute request
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Check response status
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("supabase update request failed with status %d", resp.StatusCode)
	}

	// Parse response
	var updatedUsers []User
	if err := json.NewDecoder(resp.Body).Decode(&updatedUsers); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	if len(updatedUsers) == 0 {
		return nil, fmt.Errorf("no user returned from update operation")
	}

	return &updatedUsers[0], nil
}

// DeleteUser deletes a user by their Supabase UUID
func (s *UserService) DeleteUser(ctx context.Context, userID string) error {
	// Prepare the request URL
	url := fmt.Sprintf("%s/rest/v1/%s?id=eq.%s", s.config.URL, s.config.UsersTable, userID)

	// Create request context with timeout
	reqCtx, cancel := context.WithTimeout(ctx, s.config.QueryTimeout)
	defer cancel()

	// Create HTTP request
	req, err := http.NewRequestWithContext(reqCtx, "DELETE", url, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	// Set required Supabase headers
	req.Header.Set("apikey", s.config.ServiceRoleKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", s.config.ServiceRoleKey))
	req.Header.Set("Content-Type", "application/json")

	// Execute request
	resp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to execute request: %w", err)
	}
	defer resp.Body.Close()

	// Check response status
	if resp.StatusCode != http.StatusNoContent && resp.StatusCode != http.StatusOK {
		return fmt.Errorf("supabase delete request failed with status %d", resp.StatusCode)
	}

	return nil
} 