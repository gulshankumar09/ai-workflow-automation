package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"golang.org/x/net/http2"
	"golang.org/x/net/http2/h2c"

	"github.com/ai-workflow-automation/api-gateway/internal/config"
	"github.com/ai-workflow-automation/api-gateway/internal/handlers"
	"github.com/ai-workflow-automation/api-gateway/internal/middleware"
	"github.com/ai-workflow-automation/api-gateway/internal/services"
	"github.com/ai-workflow-automation/api-gateway/pkg/grpc_client"

	// Swagger imports
	_ "github.com/ai-workflow-automation/api-gateway/docs" // This loads the generated docs
	swaggerfiles "github.com/swaggo/files"
	ginSwagger "github.com/swaggo/gin-swagger"
)

// @title ai-workflow-automation API Gateway
// @version 1.0
// @description API Gateway for ai-workflow-automation Dynamic Workflow Generation System
// @termsOfService http://swagger.io/terms/

// @contact.name API Support
// @contact.url http://www.ai-workflow-automation.com/support
// @contact.email support@ai-workflow-automation.com

// @license.name Apache 2.0
// @license.url http://www.apache.org/licenses/LICENSE-2.0.html

// @host localhost:8082

// @securityDefinitions.apikey BearerAuth
// @in header
// @name Authorization
// @description Type "Bearer" followed by a space and JWT token.

// @Summary API Gateway Information
// @Description Get API gateway service information and available endpoints
// @Tags public
// @Produce json
// @Success 200 {object} map[string]interface{} "API information"
// @Router /api/info [get]
func getAPIInfo() {}

// @Summary Test Endpoint
// @Description Public test endpoint to verify API connectivity (no authentication required)
// @Tags public
// @Produce json
// @Success 200 {object} map[string]interface{} "Test response"
// @Router /api/test [get]
func testEndpoint() {}

func main() {
	// Load configuration
	cfg, err := config.LoadConfig("")
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Setup logger based on configuration
	config.SetupLogger(cfg)

	// Initialize gRPC client manager
	grpcManager, err := grpc_client.NewClientManager(grpc_client.ClientManagerOptions{
		Config:              &cfg.GRPC,
		MaxRetries:          3,
		RetryBackoff:        time.Second,
		HealthCheckInterval: 30 * time.Second,
	})
	if err != nil {
		log.Fatalf("Failed to initialize gRPC client manager: %v", err)
	}
	defer grpcManager.Close()

	// Initialize UserService for Supabase operations
	userService := services.NewUserService(cfg.Supabase)

	// Setup Gin router
	if cfg.IsProduction() {
		gin.SetMode(gin.ReleaseMode)
	}

	router := gin.New()

	// Swagger documentation endpoint
	router.GET("/swagger/*any", ginSwagger.WrapHandler(swaggerfiles.Handler))
	
	// Add middleware
	router.Use(gin.Logger())
	router.Use(middleware.ErrorRecoveryMiddleware()) // Add custom recovery middleware
	router.Use(middleware.ErrorHandlerMiddleware())  // Add custom error handling
	router.Use(middleware.CORSMiddleware(cfg.CORS))
	router.Use(middleware.RequestIDMiddleware())
	router.Use(middleware.SecurityHeadersMiddleware())

	// Initialize handlers
	chatHandler := handlers.NewChatHandler(grpcManager)
	userHandler := handlers.NewUserHandler(grpcManager)
	userCRUDHandler := handlers.NewUserCRUDHandler(userService)
	healthHandler := handlers.NewHealthHandler(grpcManager)

	// Health endpoints
	router.GET(cfg.Monitoring.HealthCheckPath, healthHandler.HealthCheck)
	router.GET(cfg.Monitoring.ReadinessCheckPath, healthHandler.ReadinessCheck)
	router.GET(cfg.Monitoring.LivenessCheckPath, healthHandler.LivenessCheck)

	// Public API info endpoints (no authentication required)
	router.GET("/api/info", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"service":     "ai-workflow-automation-api-gateway",
			"version":     "1.0.0",
			"description": "API Gateway for ai-workflow-automation Dynamic Workflow Generation System",
			"endpoints": gin.H{
				"health":    "/health",
				"swagger":   "/swagger/index.html",
				"api_base":  "/api/v1",
			},
			"authentication": gin.H{
				"type":        "JWT Bearer Token",
				"header":      "Authorization",
				"format":      "Bearer <token>",
				"description": "All /api/v1/* endpoints require JWT authentication",
			},
		})
	})

	// Public test endpoint for Swagger testing (no authentication)
	router.GET("/api/test", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"message":   "API Gateway is working!",
			"timestamp": time.Now().Format(time.RFC3339),
			"method":    "GET",
			"path":      "/api/test",
			"note":      "This is a public endpoint for testing Swagger UI",
		})
	})

	// API v1 routes
	v1 := router.Group("/api/v1")
	
	// Rate limiting setup function
	applyRateLimit := func(group *gin.RouterGroup) {
		if cfg.RateLimit.Enabled {
			group.Use(middleware.RateLimitMiddleware(cfg.RateLimit))
		}
	}
	
	{
		// Routes that allow user creation (user doesn't need to exist in Supabase)
		userCreation := v1.Group("")
		userCreation.Use(middleware.Auth0JWTMiddlewareOptionalUser(cfg.Auth, userService))
		applyRateLimit(userCreation)
		{
			// User creation route
			userCreation.POST("/users", userCRUDHandler.CreateUser)
		}

		// Routes that require user to exist in Supabase database
		protected := v1.Group("")
		protected.Use(middleware.JWTAuthMiddleware(cfg.Auth, userService))
		applyRateLimit(protected)
		{
			// Chat routes (require existing user)
			chat := protected.Group("/chat")
			{
				sessions := chat.Group("/sessions")
				{
					sessions.POST("", chatHandler.StartChatSession)
					sessions.POST("/:id/messages", chatHandler.SendMessage)
					sessions.GET("/:id", chatHandler.GetSessionContext)
					sessions.GET("/:id/history", chatHandler.GetChatHistory)
					sessions.DELETE("/:id", chatHandler.EndChatSession)
				}
			}

			// User routes (require existing user)
			users := protected.Group("/users")
			{
				// Legacy user endpoints
				users.GET("/profile", userHandler.GetUserProfile)
				users.PUT("/preferences", userHandler.UpdateUserPreferences)
				users.GET("/context", userHandler.GetUserContext)
				users.PUT("/context", userHandler.UpdateUserContext)
				users.GET("/tools", userHandler.GetUserTools)
				users.POST("/tools", userHandler.RegisterUserTool)
				users.GET("/activity", userHandler.GetUserActivity)
				
				// User CRUD operations that require existing user
				// users.GET("", userCRUDHandler.GetUsers)              // List users (admin)
				users.GET("/me", userCRUDHandler.GetCurrentUser)     // Get current user profile
				users.PUT("/me", userCRUDHandler.UpdateCurrentUser)  // Update current user profile
				// users.GET("/:id", userCRUDHandler.GetUser)           // Get specific user by ID
				// users.PUT("/:id", userCRUDHandler.UpdateUser)        // Update user by ID
				// users.DELETE("/:id", userCRUDHandler.DeleteUser)     // Delete user (admin only)
			}
		}
	}

	// Create HTTP server
	server := &http.Server{
		Addr:         cfg.GetServerAddress(),
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
		IdleTimeout:  cfg.Server.IdleTimeout,
	}

	// Configure HTTP/2 if enabled
	if cfg.Server.EnableHTTP2 {
		server.Handler = h2c.NewHandler(router, &http2.Server{})
	} else {
		server.Handler = router
	}

	// Start server in goroutine
	go func() {
		log.Printf("Starting API Gateway server on %s", cfg.GetServerAddress())
		log.Printf("Swagger UI available at: http://%s/swagger/index.html", cfg.GetServerAddress())
		
		if cfg.Server.TLSCertPath != "" && cfg.Server.TLSKeyPath != "" {
			log.Println("Starting server with TLS")
			if err := server.ListenAndServeTLS(cfg.Server.TLSCertPath, cfg.Server.TLSKeyPath); err != nil && err != http.ErrServerClosed {
				log.Fatalf("Failed to start HTTPS server: %v", err)
			}
		} else {
			log.Println("Starting server without TLS")
			if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
				log.Fatalf("Failed to start HTTP server: %v", err)
			}
		}
	}()

	// Wait for interrupt signal to gracefully shutdown the server
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down server...")

	// Give outstanding requests time to complete
	ctx, cancel := context.WithTimeout(context.Background(), cfg.Server.ShutdownTimeout)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}

	log.Println("Server exited")
} 