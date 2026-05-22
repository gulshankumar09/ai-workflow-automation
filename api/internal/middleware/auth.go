package middleware

import (
	"context"
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"net/http"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"

	"github.com/ai-workflow-automation/api-gateway/internal/config"
	"github.com/ai-workflow-automation/api-gateway/internal/services"
)

// Auth0Claims represents the JWT token claims from Auth0
type Auth0Claims struct {
	UserID        string   `json:"sub"`              // Auth0 user ID
	Email         string   `json:"email"`
	EmailVerified bool     `json:"email_verified"`
	Name          string   `json:"name"`
	Picture       string   `json:"picture"`
	Nickname      string   `json:"nickname"`
	Audience      []string `json:"aud"`
	Issuer        string   `json:"iss"`
	Scope         string   `json:"scope"`
	Permissions   []string `json:"permissions"`      // Auth0 permissions
	jwt.RegisteredClaims
}

// JWK represents a JSON Web Key
type JWK struct {
	Kty string `json:"kty"`
	Kid string `json:"kid"`
	Use string `json:"use"`
	N   string `json:"n"`
	E   string `json:"e"`
	X5c []string `json:"x5c"`
}

// JWKS represents a JSON Web Key Set
type JWKS struct {
	Keys []JWK `json:"keys"`
}

// UserServiceInterface defines the interface for user service operations
type UserServiceInterface interface {
	GetUserByAuthID(ctx context.Context, authID string) (*services.User, error)
}

// Auth0JWTMiddleware creates an Auth0 JWT authentication middleware
func Auth0JWTMiddleware(authConfig config.AuthConfig, userService UserServiceInterface) gin.HandlerFunc {
	return Auth0JWTMiddlewareWithOptions(authConfig, userService, false)
}

// Auth0JWTMiddlewareOptionalUser creates an Auth0 JWT authentication middleware that doesn't require user to exist in Supabase
func Auth0JWTMiddlewareOptionalUser(authConfig config.AuthConfig, userService UserServiceInterface) gin.HandlerFunc {
	return Auth0JWTMiddlewareWithOptions(authConfig, userService, true)
}

// Auth0JWTMiddlewareWithOptions creates an Auth0 JWT authentication middleware with configurable options
func Auth0JWTMiddlewareWithOptions(authConfig config.AuthConfig, userService UserServiceInterface, allowMissingUser bool) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Extract token from Authorization header
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Authorization header is required",
				"code":  "MISSING_AUTH_HEADER",
			})
			c.Abort()
			return
		}

		// Check if header has Bearer prefix
		tokenString := strings.TrimPrefix(authHeader, "Bearer ")
		if tokenString == authHeader {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Authorization header must start with 'Bearer '",
				"code":  "INVALID_AUTH_FORMAT",
			})
			c.Abort()
			return
		}

		// Parse token without verification first to get the kid
		token, _, err := new(jwt.Parser).ParseUnverified(tokenString, &Auth0Claims{})
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Failed to parse token",
				"code":  "INVALID_TOKEN_FORMAT",
				"details": err.Error(),
			})
			c.Abort()
			return
		}

		// Get the kid from token header
		kid, ok := token.Header["kid"].(string)
		if !ok {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Token missing kid header",
				"code":  "MISSING_KID",
			})
			c.Abort()
			return
		}

		// Get public key for verification
		publicKey, err := getAuth0PublicKey(authConfig.Auth0Domain, kid)
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Failed to get public key",
				"code":  "JWKS_ERROR",
				"details": err.Error(),
			})
			c.Abort()
			return
		}

		// Parse and validate token with public key
		parsedToken, err := jwt.ParseWithClaims(tokenString, &Auth0Claims{}, func(token *jwt.Token) (interface{}, error) {
			// Verify the signing method
			if _, ok := token.Method.(*jwt.SigningMethodRSA); !ok {
				return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
			}
			return publicKey, nil
		})

		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Invalid token",
				"code":  "INVALID_TOKEN",
				"details": err.Error(),
			})
			c.Abort()
			return
		}

		// Extract and validate claims
		if claims, ok := parsedToken.Claims.(*Auth0Claims); ok && parsedToken.Valid {
			// Validate issuer
			expectedIssuer := fmt.Sprintf("https://%s/", authConfig.Auth0Domain)
			if claims.Issuer != expectedIssuer {
				c.JSON(http.StatusUnauthorized, gin.H{
					"error": "Invalid token issuer",
					"code":  "INVALID_ISSUER",
				})
				c.Abort()
				return
			}

			// Validate audience
			validAudience := false
			for _, aud := range claims.Audience {
				if aud == authConfig.Auth0Audience {
					validAudience = true
					break
				}
			}
			if !validAudience {
				c.JSON(http.StatusUnauthorized, gin.H{
					"error": "Invalid token audience",
					"code":  "INVALID_AUDIENCE",
				})
				c.Abort()
				return
			}

			// Fetch user from Supabase using Auth0 user ID (optional based on allowMissingUser)
			user, err := userService.GetUserByAuthID(c.Request.Context(), claims.UserID)
			if err != nil && !allowMissingUser {
				c.JSON(http.StatusUnauthorized, gin.H{
					"error": "Failed to fetch user from database",
					"code":  "USER_NOT_FOUND",
					"details": err.Error(),
				})
				c.Abort()
				return
			}

			// Set user information in context
			if user != nil {
				// User exists in Supabase - set Supabase UUID as user_id
				c.Set("user_id", user.ID)                    // Supabase UUID
				c.Set("user_exists_in_db", true)
				// Add to request headers for downstream services
				c.Request.Header.Set("X-User-ID", user.ID)   // Supabase UUID
			} else {
				// User doesn't exist in Supabase yet (for user creation scenarios)
				c.Set("user_id", "")                         // No Supabase UUID yet
				c.Set("user_exists_in_db", false)
				// Add to request headers for downstream services
				c.Request.Header.Set("X-User-ID", "")        // No Supabase UUID yet
			}

			// Always set Auth0 information regardless of Supabase user existence
			c.Set("auth_user_id", claims.UserID)         // Auth0 ID
			c.Set("user_email", claims.Email)
			c.Set("user_name", claims.Name)
			c.Set("user_permissions", claims.Permissions)
			c.Set("user_scope", claims.Scope)
			
			// Add Auth0 info to request headers for downstream services
			c.Request.Header.Set("X-Auth-User-ID", claims.UserID) // Auth0 ID
			c.Request.Header.Set("X-User-Email", claims.Email)
			c.Request.Header.Set("X-User-Name", claims.Name)
			
			c.Next()
		} else {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Invalid token claims",
				"code":  "INVALID_CLAIMS",
			})
			c.Abort()
		}
	}
}

// getAuth0PublicKey fetches the public key from Auth0's JWKS endpoint
func getAuth0PublicKey(domain, kid string) (*rsa.PublicKey, error) {
	jwksURL := fmt.Sprintf("https://%s/.well-known/jwks.json", domain)
	
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	
	resp, err := client.Get(jwksURL)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch JWKS: %v", err)
	}
	defer resp.Body.Close()

	var jwks JWKS
	if err := json.NewDecoder(resp.Body).Decode(&jwks); err != nil {
		return nil, fmt.Errorf("failed to decode JWKS: %v", err)
	}

	// Find the key with matching kid
	for _, key := range jwks.Keys {
		if key.Kid == kid && key.Kty == "RSA" {
			return buildRSAPublicKey(key)
		}
	}

	return nil, fmt.Errorf("unable to find key with kid: %s", kid)
}

// buildRSAPublicKey builds an RSA public key from JWK
func buildRSAPublicKey(key JWK) (*rsa.PublicKey, error) {
	// Decode the modulus
	nBytes, err := base64.RawURLEncoding.DecodeString(key.N)
	if err != nil {
		return nil, fmt.Errorf("failed to decode modulus: %v", err)
	}

	// Decode the exponent
	eBytes, err := base64.RawURLEncoding.DecodeString(key.E)
	if err != nil {
		return nil, fmt.Errorf("failed to decode exponent: %v", err)
	}

	// Convert bytes to big integers
	n := new(big.Int).SetBytes(nBytes)
	e := 0
	for _, b := range eBytes {
		e = e<<8 + int(b)
	}

	return &rsa.PublicKey{
		N: n,
		E: e,
	}, nil
}

// Backward compatibility: JWTAuthMiddleware now uses Auth0
func JWTAuthMiddleware(authConfig config.AuthConfig, userService UserServiceInterface) gin.HandlerFunc {
	return Auth0JWTMiddleware(authConfig, userService)
}

// GetUserID extracts user ID from the Gin context
func GetUserID(c *gin.Context) (string, bool) {
	userID, exists := c.Get("user_id")
	if !exists {
		return "", false
	}
	if id, ok := userID.(string); ok {
		return id, true
	}
	return "", false
}

// GetUserEmail extracts user email from the Gin context
func GetUserEmail(c *gin.Context) (string, bool) {
	email, exists := c.Get("user_email")
	if !exists {
		return "", false
	}
	if e, ok := email.(string); ok {
		return e, true
	}
	return "", false
}

// GetUserName extracts user name from the Gin context
func GetUserName(c *gin.Context) (string, bool) {
	name, exists := c.Get("user_name")
	if !exists {
		return "", false
	}
	if n, ok := name.(string); ok {
		return n, true
	}
	return "", false
}

// GetUserPermissions extracts user permissions from the Gin context
func GetUserPermissions(c *gin.Context) ([]string, bool) {
	permissions, exists := c.Get("user_permissions")
	if !exists {
		return nil, false
	}
	if p, ok := permissions.([]string); ok {
		return p, true
	}
	return nil, false
}

// GetUserScope extracts user scope from the Gin context
func GetUserScope(c *gin.Context) (string, bool) {
	scope, exists := c.Get("user_scope")
	if !exists {
		return "", false
	}
	if s, ok := scope.(string); ok {
		return s, true
	}
	return "", false
}

// GetUserRoles extracts user roles from the Gin context (deprecated - use permissions)
func GetUserRoles(c *gin.Context) ([]string, bool) {
	return GetUserPermissions(c)
}

// GetAuthUserID extracts Auth0 user ID from the Gin context
func GetAuthUserID(c *gin.Context) (string, bool) {
	authUserID, exists := c.Get("auth_user_id")
	if !exists {
		return "", false
	}
	if id, ok := authUserID.(string); ok {
		return id, true
	}
	return "", false
}

// UserExistsInDB checks if the authenticated user exists in the Supabase database
func UserExistsInDB(c *gin.Context) bool {
	exists, ok := c.Get("user_exists_in_db")
	if !ok {
		return false
	}
	if existsFlag, ok := exists.(bool); ok {
		return existsFlag
	}
	return false
}

// RequireUserInDB creates a middleware that requires the user to exist in Supabase database
func RequireUserInDB() gin.HandlerFunc {
	return func(c *gin.Context) {
		if !UserExistsInDB(c) {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "User not found in database",
				"code":  "USER_NOT_FOUND",
				"message": "Your account is not properly set up. Please contact support.",
			})
			c.Abort()
			return
		}
		c.Next()
	}
}

// RequirePermission creates a middleware that requires specific Auth0 permission
func RequirePermission(requiredPermission string) gin.HandlerFunc {
	return func(c *gin.Context) {
		permissions, exists := GetUserPermissions(c)
		if !exists {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "User permissions not found",
				"code":  "MISSING_PERMISSIONS",
			})
			c.Abort()
			return
		}

		// Check if user has the required permission
		hasPermission := false
		for _, permission := range permissions {
			if permission == requiredPermission {
				hasPermission = true
				break
			}
		}

		if !hasPermission {
			c.JSON(http.StatusForbidden, gin.H{
				"error": fmt.Sprintf("Permission '%s' is required", requiredPermission),
				"code":  "INSUFFICIENT_PERMISSION",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// RequireRole creates a middleware that requires specific role (deprecated - use RequirePermission)
func RequireRole(requiredRole string) gin.HandlerFunc {
	return RequirePermission(requiredRole)
} 