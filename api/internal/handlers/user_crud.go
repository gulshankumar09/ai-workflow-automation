package handlers

import (
	"net/http"

	"github.com/ai-workflow-automation/api-gateway/internal/middleware"
	"github.com/ai-workflow-automation/api-gateway/internal/models"
	"github.com/ai-workflow-automation/api-gateway/internal/services"
	"github.com/gin-gonic/gin"
)

// UserCRUDHandler handles user CRUD HTTP requests
type UserCRUDHandler struct {
	userService *services.UserService
}

// NewUserCRUDHandler creates a new user CRUD handler
func NewUserCRUDHandler(userService *services.UserService) *UserCRUDHandler {
	return &UserCRUDHandler{
		userService: userService,
	}
}



// CreateUser handles POST /api/v1/users
// @Summary Create a new user
// @Description Create a new user in the system
// @Tags users
// @Accept json
// @Produce json
// @Param user body models.CreateUserRequest true "User data"
// @Success 201 {object} models.CreateUserResponse
// @Failure 400 {object} models.ErrorResponse
// @Failure 401 {object} models.ErrorResponse
// @Failure 409 {object} models.ErrorResponse
// @Failure 500 {object} models.ErrorResponse
// @Security BearerAuth
// @Router /api/v1/users [post]
func (h *UserCRUDHandler) CreateUser(c *gin.Context) {
	var req models.CreateUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.CreateUserResponse{
			Success: false,
			Message: "Invalid request format: " + err.Error(),
		})
		return
	}

	// Validate request
	if err := req.Validate(); err != nil {
		c.JSON(http.StatusBadRequest, models.CreateUserResponse{
			Success: false,
			Message: err.Error(),
		})
		return
	}

	// Get Auth0 user ID from context for validation
	authUserID, exists := middleware.GetAuthUserID(c)
	if !exists {
		c.JSON(http.StatusUnauthorized, models.CreateUserResponse{
			Success: false,
			Message: "Auth0 user ID not found in token",
		})
		return
	}

	// Validate that the auth_id in request matches the authenticated user
	// This prevents users from creating accounts for other Auth0 users
	if req.AuthID != authUserID {
		c.JSON(http.StatusForbidden, models.CreateUserResponse{
			Success: false,
			Message: "You can only create an account for yourself",
		})
		return
	}

	// Check if user already exists (middleware allows optional user lookup)
	userExists := middleware.UserExistsInDB(c)
	if userExists {
		c.JSON(http.StatusConflict, models.CreateUserResponse{
			Success: false,
			Message: "User already exists in the system",
		})
		return
	}

	// Use Auth0 information from token for consistency
	userEmail, _ := middleware.GetUserEmail(c)
	userName, _ := middleware.GetUserName(c)

	// Convert request to service model
	user := services.User{
		Name:      userName,   // Use name from Auth0 token
		Email:     userEmail,  // Use email from Auth0 token
		AvatarURL: req.AvatarURL,
		AuthID:    authUserID, // Use Auth0 ID from token
	}

	// Override with request data if provided and not empty
	if req.Name != "" {
		user.Name = req.Name
	}
	if req.Email != "" {
		user.Email = req.Email
	}

	// Create user
	createdUser, err := h.userService.CreateUser(c.Request.Context(), user)
	if err != nil {
		c.JSON(http.StatusConflict, models.CreateUserResponse{
			Success: false,
			Message: "Failed to create user: " + err.Error(),
		})
		return
	}

	// Convert to response model
	userDetails := &models.UserDetails{
		ID:        createdUser.ID,
		Name:      createdUser.Name,
		Email:     createdUser.Email,
		AvatarURL: createdUser.AvatarURL,
		AuthID:    createdUser.AuthID,
		CreatedAt: createdUser.CreatedAt,
		UpdatedAt: createdUser.CreatedAt, // Use CreatedAt as UpdatedAt for new users
	}

	c.JSON(http.StatusCreated, models.CreateUserResponse{
		User:    userDetails,
		Success: true,
		Message: "User created successfully",
	})
}

// // GetUser handles GET /api/v1/users/:id
// // @Summary Get user by ID
// // @Description Get a specific user by their UUID
// // @Tags users
// // @Produce json
// // @Param id path string true "User UUID"
// // @Success 200 {object} models.GetUserResponse
// // @Failure 400 {object} models.ErrorResponse
// // @Failure 401 {object} models.ErrorResponse
// // @Failure 404 {object} models.ErrorResponse
// // @Failure 500 {object} models.ErrorResponse
// // @Security BearerAuth
// // @Router /api/v1/users/{id} [get]
// func (h *UserCRUDHandler) GetUser(c *gin.Context) {
// 	userID := c.Param("id")
// 	if userID == "" {
// 		c.JSON(http.StatusBadRequest, models.GetUserResponse{
// 			Success: false,
// 			Message: "User ID is required",
// 		})
// 		return
// 	}

// 	// Get user
// 	user, err := h.userService.GetUserByID(c.Request.Context(), userID)
// 	if err != nil {
// 		c.JSON(http.StatusNotFound, models.GetUserResponse{
// 			Success: false,
// 			Message: "User not found: " + err.Error(),
// 		})
// 		return
// 	}

// 	// Convert to response model
// 	userDetails := &models.UserDetails{
// 		ID:        user.ID,
// 		Name:      user.Name,
// 		Email:     user.Email,
// 		AvatarURL: user.AvatarURL,
// 		AuthID:    user.AuthID,
// 		CreatedAt: user.CreatedAt,
// 		UpdatedAt: user.CreatedAt, // Note: We don't have UpdatedAt in the service model yet
// 	}

// 	c.JSON(http.StatusOK, models.GetUserResponse{
// 		User:    userDetails,
// 		Success: true,
// 		Message: "User retrieved successfully",
// 	})
// }

// GetCurrentUser handles GET /api/v1/users/me
// @Summary Get current user profile
// @Description Get the profile of the currently authenticated user
// @Tags users
// @Produce json
// @Success 200 {object} models.GetUserResponse
// @Failure 401 {object} models.ErrorResponse
// @Failure 404 {object} models.ErrorResponse
// @Failure 500 {object} models.ErrorResponse
// @Security BearerAuth
// @Router /api/v1/users/me [get]
func (h *UserCRUDHandler) GetCurrentUser(c *gin.Context) {
	// Get user ID from context (set by auth middleware)
	userID, exists := middleware.GetUserID(c)
	if !exists {
		c.JSON(http.StatusUnauthorized, models.GetUserResponse{
			Success: false,
			Message: "User ID not found in token",
		})
		return
	}

	// Get user
	user, err := h.userService.GetUserByID(c.Request.Context(), userID)
	if err != nil {
		c.JSON(http.StatusNotFound, models.GetUserResponse{
			Success: false,
			Message: "User not found: " + err.Error(),
		})
		return
	}

	// Convert to response model
	userDetails := &models.UserDetails{
		ID:        user.ID,
		Name:      user.Name,
		Email:     user.Email,
		AvatarURL: user.AvatarURL,
		AuthID:    user.AuthID,
		CreatedAt: user.CreatedAt,
		UpdatedAt: user.CreatedAt,
	}

	c.JSON(http.StatusOK, models.GetUserResponse{
		User:    userDetails,
		Success: true,
		Message: "Current user retrieved successfully",
	})
}

// // GetUsers handles GET /api/v1/users
// // @Summary List users with pagination
// // @Description Get a paginated list of users with optional search and sorting
// // @Tags users
// // @Produce json
// // @Param limit query int false "Number of users per page (default: 20, max: 100)"
// // @Param offset query int false "Number of users to skip (default: 0)"
// // @Param search query string false "Search term for name or email"
// // @Param sort_by query string false "Sort field" Enums(name, email, created_at, updated_at)
// // @Param order query string false "Sort order" Enums(asc, desc)
// // @Success 200 {object} models.GetUsersResponse
// // @Failure 400 {object} models.ErrorResponse
// // @Failure 401 {object} models.ErrorResponse
// // @Failure 500 {object} models.ErrorResponse
// // @Security BearerAuth
// // @Router /api/v1/users [get]
// func (h *UserCRUDHandler) GetUsers(c *gin.Context) {
// 	var req models.GetUsersRequest
// 	if err := c.ShouldBindQuery(&req); err != nil {
// 		c.JSON(http.StatusBadRequest, models.GetUsersResponse{
// 			Success: false,
// 			Message: "Invalid query parameters: " + err.Error(),
// 		})
// 		return
// 	}

// 	// Set defaults
// 	req.SetDefaults()

// 	// Validate limits
// 	if req.Limit > models.MaxUsersPerPage {
// 		req.Limit = models.MaxUsersPerPage
// 	}

// 	// Get users
// 	users, totalCount, err := h.userService.GetAllUsers(
// 		c.Request.Context(),
// 		req.Limit,
// 		req.Offset,
// 		req.Search,
// 		req.SortBy,
// 		req.Order,
// 	)
// 	if err != nil {
// 		c.JSON(http.StatusInternalServerError, models.GetUsersResponse{
// 			Success: false,
// 			Message: "Failed to retrieve users: " + err.Error(),
// 		})
// 		return
// 	}

// 	// Convert to response models
// 	userDetails := make([]*models.UserDetails, len(users))
// 	for i, user := range users {
// 		userDetails[i] = &models.UserDetails{
// 			ID:        user.ID,
// 			Name:      user.Name,
// 			Email:     user.Email,
// 			AvatarURL: user.AvatarURL,
// 			AuthID:    user.AuthID,
// 			CreatedAt: user.CreatedAt,
// 			UpdatedAt: user.CreatedAt,
// 		}
// 	}

// 	c.JSON(http.StatusOK, models.GetUsersResponse{
// 		Users:      userDetails,
// 		TotalCount: totalCount,
// 		Limit:      req.Limit,
// 		Offset:     req.Offset,
// 		Success:    true,
// 		Message:    "Users retrieved successfully",
// 	})
// }

// // UpdateUser handles PUT /api/v1/users/:id
// // @Summary Update user
// // @Description Update an existing user's information
// // @Tags users
// // @Accept json
// // @Produce json
// // @Param id path string true "User UUID"
// // @Param user body models.UpdateUserRequest true "Updated user data"
// // @Success 200 {object} models.UpdateUserResponse
// // @Failure 400 {object} models.ErrorResponse
// // @Failure 401 {object} models.ErrorResponse
// // @Failure 403 {object} models.ErrorResponse
// // @Failure 404 {object} models.ErrorResponse
// // @Failure 500 {object} models.ErrorResponse
// // @Security BearerAuth
// // @Router /api/v1/users/{id} [put]
// func (h *UserCRUDHandler) UpdateUser(c *gin.Context) {
// 	userID := c.Param("id")
// 	if userID == "" {
// 		c.JSON(http.StatusBadRequest, models.UpdateUserResponse{
// 			Success: false,
// 			Message: "User ID is required",
// 		})
// 		return
// 	}

// 	// Check if current user is updating their own profile or if they have admin permissions
// 	currentUserID, exists := middleware.GetUserID(c)
// 	if !exists {
// 		c.JSON(http.StatusUnauthorized, models.UpdateUserResponse{
// 			Success: false,
// 			Message: "User ID not found in token",
// 		})
// 		return
// 	}

// 	// For now, only allow users to update their own profile
// 	// TODO: Add role-based permissions for admin users
// 	if currentUserID != userID {
// 		c.JSON(http.StatusForbidden, models.UpdateUserResponse{
// 			Success: false,
// 			Message: "You can only update your own profile",
// 		})
// 		return
// 	}

// 	var req models.UpdateUserRequest
// 	if err := c.ShouldBindJSON(&req); err != nil {
// 		c.JSON(http.StatusBadRequest, models.UpdateUserResponse{
// 			Success: false,
// 			Message: "Invalid request format: " + err.Error(),
// 		})
// 		return
// 	}

// 	// Validate request
// 	if err := req.Validate(); err != nil {
// 		c.JSON(http.StatusBadRequest, models.UpdateUserResponse{
// 			Success: false,
// 			Message: err.Error(),
// 		})
// 		return
// 	}

// 	// Convert request to service model
// 	updates := services.User{}
// 	if req.Name != nil {
// 		updates.Name = *req.Name
// 	}
// 	if req.Email != nil {
// 		updates.Email = *req.Email
// 	}
// 	if req.AvatarURL != nil {
// 		updates.AvatarURL = *req.AvatarURL
// 	}

// 	// Update user
// 	updatedUser, err := h.userService.UpdateUser(c.Request.Context(), userID, updates)
// 	if err != nil {
// 		c.JSON(http.StatusInternalServerError, models.UpdateUserResponse{
// 			Success: false,
// 			Message: "Failed to update user: " + err.Error(),
// 		})
// 		return
// 	}

// 	// Convert to response model
// 	userDetails := &models.UserDetails{
// 		ID:        updatedUser.ID,
// 		Name:      updatedUser.Name,
// 		Email:     updatedUser.Email,
// 		AvatarURL: updatedUser.AvatarURL,
// 		AuthID:    updatedUser.AuthID,
// 		CreatedAt: updatedUser.CreatedAt,
// 		UpdatedAt: updatedUser.CreatedAt,
// 	}

// 	c.JSON(http.StatusOK, models.UpdateUserResponse{
// 		User:    userDetails,
// 		Success: true,
// 		Message: "User updated successfully",
// 	})
// }

// UpdateCurrentUser handles PUT /api/v1/users/me
// @Summary Update current user profile
// @Description Update the profile of the currently authenticated user
// @Tags users
// @Accept json
// @Produce json
// @Param user body models.UpdateUserRequest true "Updated user data"
// @Success 200 {object} models.UpdateUserResponse
// @Failure 400 {object} models.ErrorResponse
// @Failure 401 {object} models.ErrorResponse
// @Failure 404 {object} models.ErrorResponse
// @Failure 500 {object} models.ErrorResponse
// @Security BearerAuth
// @Router /api/v1/users/me [put]
func (h *UserCRUDHandler) UpdateCurrentUser(c *gin.Context) {
	// Get user ID from context (set by auth middleware)
	userID, exists := middleware.GetUserID(c)
	if !exists {
		c.JSON(http.StatusUnauthorized, models.UpdateUserResponse{
			Success: false,
			Message: "User ID not found in token",
		})
		return
	}

	var req models.UpdateUserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, models.UpdateUserResponse{
			Success: false,
			Message: "Invalid request format: " + err.Error(),
		})
		return
	}

	// Validate request
	if err := req.Validate(); err != nil {
		c.JSON(http.StatusBadRequest, models.UpdateUserResponse{
			Success: false,
			Message: err.Error(),
		})
		return
	}

	// Convert request to service model
	updates := services.User{}
	if req.Name != nil {
		updates.Name = *req.Name
	}
	if req.Email != nil {
		updates.Email = *req.Email
	}
	if req.AvatarURL != nil {
		updates.AvatarURL = *req.AvatarURL
	}

	// Update user
	updatedUser, err := h.userService.UpdateUser(c.Request.Context(), userID, updates)
	if err != nil {
		c.JSON(http.StatusInternalServerError, models.UpdateUserResponse{
			Success: false,
			Message: "Failed to update user: " + err.Error(),
		})
		return
	}

	// Convert to response model
	userDetails := &models.UserDetails{
		ID:        updatedUser.ID,
		Name:      updatedUser.Name,
		Email:     updatedUser.Email,
		AvatarURL: updatedUser.AvatarURL,
		AuthID:    updatedUser.AuthID,
		CreatedAt: updatedUser.CreatedAt,
		UpdatedAt: updatedUser.CreatedAt,
	}

	c.JSON(http.StatusOK, models.UpdateUserResponse{
		User:    userDetails,
		Success: true,
		Message: "Profile updated successfully",
	})
}

// DeleteUser handles DELETE /api/v1/users/:id
// @Summary Delete user
// @Description Delete a user from the system (admin only)
// @Tags users
// @Produce json
// @Param id path string true "User UUID"
// @Success 200 {object} models.DeleteUserResponse
// @Failure 400 {object} models.ErrorResponse
// @Failure 401 {object} models.ErrorResponse
// @Failure 403 {object} models.ErrorResponse
// @Failure 404 {object} models.ErrorResponse
// @Failure 500 {object} models.ErrorResponse
// @Security BearerAuth
// @Router /api/v1/users/{id} [delete]
func (h *UserCRUDHandler) DeleteUser(c *gin.Context) {
	userID := c.Param("id")
	if userID == "" {
		c.JSON(http.StatusBadRequest, models.DeleteUserResponse{
			Success: false,
			Message: "User ID is required",
		})
		return
	}

	// TODO: Add proper role-based authorization
	// For now, prevent users from deleting their own account for safety
	currentUserID, exists := middleware.GetUserID(c)
	if !exists {
		c.JSON(http.StatusUnauthorized, models.DeleteUserResponse{
			Success: false,
			Message: "User ID not found in token",
		})
		return
	}

	if currentUserID == userID {
		c.JSON(http.StatusForbidden, models.DeleteUserResponse{
			Success: false,
			Message: "You cannot delete your own account. Please contact support.",
		})
		return
	}

	// Check if user has admin permissions
	// TODO: Implement proper role checking
	permissions, _ := middleware.GetUserPermissions(c)
	hasAdminPermission := false
	for _, perm := range permissions {
		if perm == "admin:users:delete" || perm == "admin:all" {
			hasAdminPermission = true
			break
		}
	}

	if !hasAdminPermission {
		c.JSON(http.StatusForbidden, models.DeleteUserResponse{
			Success: false,
			Message: "Insufficient permissions to delete users",
		})
		return
	}

	// Delete user
	err := h.userService.DeleteUser(c.Request.Context(), userID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, models.DeleteUserResponse{
			Success: false,
			Message: "Failed to delete user: " + err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, models.DeleteUserResponse{
		Success: true,
		Message: "User deleted successfully",
	})
} 