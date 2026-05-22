package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/ai-workflow-automation/api-gateway/internal/models"
	"github.com/ai-workflow-automation/api-gateway/pkg/grpc_client"
	"github.com/ai-workflow-automation/api-gateway/pkg/grpc_client/protos"
	"github.com/ai-workflow-automation/api-gateway/pkg/validator"
	"github.com/gin-gonic/gin"
	"google.golang.org/protobuf/types/known/structpb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// ChatHandler handles chat-related HTTP requests
type ChatHandler struct {
	grpcManager *grpc_client.ClientManager
}

// NewChatHandler creates a new chat handler
func NewChatHandler(grpcManager *grpc_client.ClientManager) *ChatHandler {
	return &ChatHandler{
		grpcManager: grpcManager,
	}
}

// StartChatSession godoc
// @Summary Start a new chat session
// @Description Create a new chat session with specified type and context
// @Tags chat
// @Accept json
// @Produce json
// @Security BearerAuth
// @Param request body models.StartChatSessionRequest true "Chat session request"
// @Success 200 {object} models.StartChatSessionResponse
// @Failure 400 {object} models.ErrorResponse
// @Failure 401 {object} models.ErrorResponse
// @Router /api/v1/chat/sessions [post]
func (h *ChatHandler) StartChatSession(c *gin.Context) {
	var req models.StartChatSessionRequest
	
	// Validate request
	if validationErrors := validator.ValidateJSONBinding(c, &req); len(validationErrors) > 0 {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewValidationErrorResponse(correlationID, validationErrors)
		c.JSON(http.StatusBadRequest, errorResponse)
		return
	}
	
	// Get user ID from context
	userID, exists := c.Get("user_id")
	if !exists {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeUnauthorized, "User not authenticated", correlationID)
		c.JSON(http.StatusUnauthorized, errorResponse)
		return
	}
	
	// Convert context to protobuf struct
	var contextStruct *structpb.Struct
	if req.Context != nil {
		var err error
		contextStruct, err = structpb.NewStruct(req.Context)
		if err != nil {
			correlationID := c.GetString("request_id")
			errorResponse := models.NewErrorResponse(models.CodeInvalidInput, "Invalid context format", correlationID)
			c.JSON(http.StatusBadRequest, errorResponse)
			return
		}
	}

	// Convert session type string to enum
	sessionType := convertStringToSessionType(req.SessionType)
	
	// Create gRPC request
	grpcReq := &protos.StartChatSessionRequest{
		UserId:       userID.(string),
		SessionType:  sessionType,
		Context:      contextStruct,
		Capabilities: req.Capabilities,
	}
	
	// Call gRPC service
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	
	chatClient, err := h.grpcManager.ChatClient()
	if err != nil {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeServiceUnavailable, "Chat service unavailable", correlationID)
		c.JSON(http.StatusServiceUnavailable, errorResponse)
		return
	}
	
	grpcResp, err := chatClient.StartChatSession(ctx, grpcReq)
	if err != nil {
		correlationID := c.GetString("request_id")
		httpStatus, errorResponse := models.ConvertGRPCError(err, correlationID)
		c.JSON(httpStatus, errorResponse)
		return
	}
	
	// Convert gRPC response to API response
	response := &models.StartChatSessionResponse{
		SessionID:      grpcResp.SessionId,
		Status:         grpcResp.Status.String(),
		Context:        models.StructToMap(grpcResp.Context),
		AvailableTools: grpcResp.AvailableTools,
		Message:        grpcResp.Message,
	}
	
	c.JSON(http.StatusOK, response)
}

// SendMessage godoc
// @Summary Send a message in a chat session
// @Description Send a message to a chat session and optionally receive streaming response
// @Tags chat
// @Accept json
// @Produce json
// @Security BearerAuth
// @Param id path string true "Session ID"
// @Param request body models.SendMessageRequest true "Message request"
// @Success 200 {object} models.ChatMessageResponse
// @Failure 400 {object} models.ErrorResponse
// @Failure 401 {object} models.ErrorResponse
// @Failure 404 {object} models.ErrorResponse
// @Router /api/v1/chat/sessions/{id}/messages [post]
func (h *ChatHandler) SendMessage(c *gin.Context) {
	sessionID := c.Param("id")
	if sessionID == "" {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeInvalidInput, "Session ID is required", correlationID)
		c.JSON(http.StatusBadRequest, errorResponse)
		return
	}
	
	var req models.SendMessageRequest
	
	// Validate request
	if validationErrors := validator.ValidateJSONBinding(c, &req); len(validationErrors) > 0 {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewValidationErrorResponse(correlationID, validationErrors)
		c.JSON(http.StatusBadRequest, errorResponse)
		return
	}
	
	// Get user ID from context
	_, exists := c.Get("user_id")
	if !exists {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeUnauthorized, "User not authenticated", correlationID)
		c.JSON(http.StatusUnauthorized, errorResponse)
		return
	}
	
	// Convert metadata to protobuf struct
	var metadataStruct *structpb.Struct
	if req.Metadata != nil {
		var err error
		metadataStruct, err = structpb.NewStruct(req.Metadata)
		if err != nil {
			correlationID := c.GetString("request_id")
			errorResponse := models.NewErrorResponse(models.CodeInvalidInput, "Invalid metadata format", correlationID)
			c.JSON(http.StatusBadRequest, errorResponse)
			return
		}
	}

	// Convert message type string to enum
	messageType := convertStringToMessageType(req.MessageType)
	
	// Create gRPC request - Always enable streaming since Core always returns stream
	grpcReq := &protos.SendMessageRequest{
		SessionId:      sessionID,
		Message:        req.Message,
		MessageType:    messageType,
		Metadata:       metadataStruct,
		StreamResponse: true, // Core always returns stream
	}
	
	// Call gRPC service
	chatClient, err := h.grpcManager.ChatClient()
	if err != nil {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeServiceUnavailable, "Chat service unavailable", correlationID)
		c.JSON(http.StatusServiceUnavailable, errorResponse)
		return
	}
	
	// Check if client wants streaming response
	if req.Stream {
		// Check Accept header to determine streaming format
		acceptHeader := c.GetHeader("Accept")
		if strings.Contains(acceptHeader, "application/x-ndjson") || strings.Contains(acceptHeader, "application/json-seq") {
			// Handle JSON streaming (NDJSON format)
			h.streamChatResponseJSON(c, chatClient, grpcReq)
		} else {
			// Handle SSE streaming (default)
			h.streamChatResponse(c, chatClient, grpcReq)
		}
	} else {
		// Handle non-streaming: collect all responses and return as single JSON
		h.handleNonStreamingResponse(c, chatClient, grpcReq)
	}
}



// GetSessionContext handles GET /api/v1/chat/sessions/:id
// GetSessionContext godoc
// @Summary Get chat session context
// @Description Retrieve current context and status of a chat session
// @Tags chat
// @Accept json
// @Produce json
// @Security BearerAuth
// @Param id path string true "Session ID"
// @Success 200 {object} models.GetSessionContextResponse
// @Failure 400 {object} models.ErrorResponse
// @Failure 401 {object} models.ErrorResponse
// @Failure 404 {object} models.ErrorResponse
// @Router /api/v1/chat/sessions/{id} [get]
func (h *ChatHandler) GetSessionContext(c *gin.Context) {
	sessionID := c.Param("id")
	if sessionID == "" {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeInvalidInput, "Session ID is required", correlationID)
		c.JSON(http.StatusBadRequest, errorResponse)
		return
	}
	
	// Get user ID from context
	_, exists := c.Get("user_id")
	if !exists {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeUnauthorized, "User not authenticated", correlationID)
		c.JSON(http.StatusUnauthorized, errorResponse)
		return
	}
	
	// Create gRPC request
	grpcReq := &protos.GetSessionContextRequest{
		SessionId: sessionID,
	}
	
	// Call gRPC service
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	
	chatClient, err := h.grpcManager.ChatClient()
	if err != nil {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeServiceUnavailable, "Chat service unavailable", correlationID)
		c.JSON(http.StatusServiceUnavailable, errorResponse)
		return
	}
	
	grpcResp, err := chatClient.GetSessionContext(ctx, grpcReq)
	if err != nil {
		correlationID := c.GetString("request_id")
		httpStatus, errorResponse := models.ConvertGRPCError(err, correlationID)
		c.JSON(httpStatus, errorResponse)
		return
	}
	
	// Convert gRPC response to API response
	response := &models.GetSessionContextResponse{
		SessionID:   grpcResp.SessionId,
		Status:      grpcResp.Status.String(),
		Context:     models.StructToMap(grpcResp.Context),
		ActiveTools: grpcResp.ActiveTools,
		Metrics:     convertSessionMetrics(grpcResp.Metrics),
	}
	
	c.JSON(http.StatusOK, response)
}

// GetChatHistory godoc
// @Summary Get chat session history
// @Description Retrieve message history for a chat session with pagination
// @Tags chat
// @Accept json
// @Produce json
// @Security BearerAuth
// @Param id path string true "Session ID"
// @Param limit query int false "Number of messages to retrieve (default: 50, max: 100)"
// @Param cursor query string false "Pagination cursor for next page"
// @Param start_time query string false "Start time filter (RFC3339 format)"
// @Param end_time query string false "End time filter (RFC3339 format)"
// @Success 200 {object} models.GetChatHistoryResponse
// @Failure 400 {object} models.ErrorResponse
// @Failure 401 {object} models.ErrorResponse
// @Failure 404 {object} models.ErrorResponse
// @Router /api/v1/chat/sessions/{id}/history [get]
func (h *ChatHandler) GetChatHistory(c *gin.Context) {
	sessionID := c.Param("id")
	if sessionID == "" {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeInvalidInput, "Session ID is required", correlationID)
		c.JSON(http.StatusBadRequest, errorResponse)
		return
	}
	
	var req models.GetChatHistoryRequest
	
	// Validate query parameters
	if validationErrors := validator.ValidateQueryBinding(c, &req); len(validationErrors) > 0 {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewValidationErrorResponse(correlationID, validationErrors)
		c.JSON(http.StatusBadRequest, errorResponse)
		return
	}
	
	// Set defaults
	if req.Limit == 0 {
		req.Limit = 50
	}
	
	// Get user ID from context
	_, exists := c.Get("user_id")
	if !exists {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeUnauthorized, "User not authenticated", correlationID)
		c.JSON(http.StatusUnauthorized, errorResponse)
		return
	}
	
	// Create gRPC request
	grpcReq := &protos.GetChatHistoryRequest{
		SessionId: sessionID,
		Limit:     req.Limit,
		Cursor:    req.Cursor,
	}
	
	if !req.StartTime.IsZero() {
		grpcReq.StartTime = &timestamppb.Timestamp{}
		grpcReq.StartTime.Seconds = req.StartTime.Unix()
	}
	
	if !req.EndTime.IsZero() {
		grpcReq.EndTime = &timestamppb.Timestamp{}
		grpcReq.EndTime.Seconds = req.EndTime.Unix()
	}
	
	// Call gRPC service
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	
	chatClient, err := h.grpcManager.ChatClient()
	if err != nil {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeServiceUnavailable, "Chat service unavailable", correlationID)
		c.JSON(http.StatusServiceUnavailable, errorResponse)
		return
	}
	
	grpcResp, err := chatClient.GetChatHistory(ctx, grpcReq)
	if err != nil {
		correlationID := c.GetString("request_id")
		httpStatus, errorResponse := models.ConvertGRPCError(err, correlationID)
		c.JSON(httpStatus, errorResponse)
		return
	}
	
	// Convert gRPC response to API response
	messages := make([]*models.ChatMessage, len(grpcResp.Messages))
	for i, message := range grpcResp.Messages {
		messages[i] = convertChatMessage(message)
	}
	
	response := &models.GetChatHistoryResponse{
		Messages:   messages,
		NextCursor: grpcResp.NextCursor,
		HasMore:    grpcResp.HasMore,
		TotalCount: grpcResp.TotalCount,
	}
	
	c.JSON(http.StatusOK, response)
}

// EndChatSession godoc
// @Summary End a chat session
// @Description Terminate a chat session and optionally provide a reason
// @Tags chat
// @Accept json
// @Produce json
// @Security BearerAuth
// @Param id path string true "Session ID"
// @Param request body models.EndChatSessionRequest false "End session request with optional reason"
// @Success 200 {object} models.EndChatSessionResponse
// @Failure 400 {object} models.ErrorResponse
// @Failure 401 {object} models.ErrorResponse
// @Failure 404 {object} models.ErrorResponse
// @Router /api/v1/chat/sessions/{id} [delete]
func (h *ChatHandler) EndChatSession(c *gin.Context) {
	sessionID := c.Param("id")
	if sessionID == "" {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeInvalidInput, "Session ID is required", correlationID)
		c.JSON(http.StatusBadRequest, errorResponse)
		return
	}
	
	var req models.EndChatSessionRequest
	
	// Validate request (reason is optional)
	if validationErrors := validator.ValidateJSONBinding(c, &req); len(validationErrors) > 0 {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewValidationErrorResponse(correlationID, validationErrors)
		c.JSON(http.StatusBadRequest, errorResponse)
		return
	}
	
	// Get user ID from context
	_, exists := c.Get("user_id")
	if !exists {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeUnauthorized, "User not authenticated", correlationID)
		c.JSON(http.StatusUnauthorized, errorResponse)
		return
	}
	
	// Create gRPC request
	grpcReq := &protos.EndChatSessionRequest{
		SessionId: sessionID,
		Reason:    req.Reason,
	}
	
	// Call gRPC service
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	
	chatClient, err := h.grpcManager.ChatClient()
	if err != nil {
		correlationID := c.GetString("request_id")
		errorResponse := models.NewErrorResponse(models.CodeServiceUnavailable, "Chat service unavailable", correlationID)
		c.JSON(http.StatusServiceUnavailable, errorResponse)
		return
	}
	
	grpcResp, err := chatClient.EndChatSession(ctx, grpcReq)
	if err != nil {
		correlationID := c.GetString("request_id")
		httpStatus, errorResponse := models.ConvertGRPCError(err, correlationID)
		c.JSON(httpStatus, errorResponse)
		return
	}
	
	// Convert gRPC response to API response
	response := &models.EndChatSessionResponse{
		SessionID: grpcResp.SessionId,
		Status:    grpcResp.Status.String(),
		Message:   grpcResp.Message,
		EndedAt:   grpcResp.EndedAt.AsTime(),
	}
	
	c.JSON(http.StatusOK, response)
}

// streamChatResponse handles Server-Sent Events streaming for chat responses
func (h *ChatHandler) streamChatResponse(c *gin.Context, chatClient protos.ChatServiceClient, req *protos.SendMessageRequest) {
	// Set SSE headers
	c.Header("Content-Type", "text/event-stream")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("X-Accel-Buffering", "no") // Disable nginx buffering
	
	correlationID := c.GetString("request_id")
	
	// Use request context to inherit timeouts and cancellation
	ctx := c.Request.Context()
	
	// Check if client connection is still active
	if ctx.Err() != nil {
		log.Printf("[%s] Client disconnected before starting stream", correlationID)
		return
	}
	
	// Start streaming
	stream, err := chatClient.SendMessage(ctx, req)
	if err != nil {
		log.Printf("[%s] Failed to start gRPC stream: %v", correlationID, err)
		fmt.Fprintf(c.Writer, "data: {\"error\": \"Failed to start stream: %v\", \"type\": \"error\", \"is_final\": true}\n\n", err)
		c.Writer.Flush()
		return
	}
	
	log.Printf("[%s] Started streaming response for session: %s", correlationID, req.SessionId)
	
	// Track if we've sent any responses to avoid duplicates
	responseSent := false
	var lastResponse *models.ChatMessageResponse
	
	// Stream responses with proper error handling
	for {
		// Check if client is still connected
		select {
		case <-ctx.Done():
			log.Printf("[%s] Request context cancelled, stopping stream: %v", correlationID, ctx.Err())
			// Send final response if we had partial data
			if responseSent && lastResponse != nil {
				finalResponse := *lastResponse
				finalResponse.IsFinal = true
				finalResponse.Status = "RESPONSE_STATUS_SUCCESS"
				finalJSON, _ := json.Marshal(finalResponse)
				fmt.Fprintf(c.Writer, "data: %s\n\n", finalJSON)
			} else {
				fmt.Fprintf(c.Writer, "data: {\"error\": \"Request timeout or cancelled\", \"type\": \"error\", \"is_final\": true}\n\n")
			}
			c.Writer.Flush()
			return
		default:
		}
		
		resp, err := stream.Recv()
		if err != nil {
			if err == io.EOF {
				log.Printf("[%s] Stream ended normally", correlationID)
				if !responseSent {
					fmt.Fprintf(c.Writer, "data: {\"type\": \"end\", \"is_final\": true}\n\n")
				}
			} else {
				// Handle cancellation gracefully
				if strings.Contains(err.Error(), "Cancelled") || strings.Contains(err.Error(), "context canceled") {
					log.Printf("[%s] Stream cancelled: %v", correlationID, err)
					if responseSent && lastResponse != nil {
						// Send final response with accumulated content
						finalResponse := *lastResponse
						finalResponse.IsFinal = true
						finalResponse.Status = "RESPONSE_STATUS_SUCCESS"
						finalJSON, _ := json.Marshal(finalResponse)
						fmt.Fprintf(c.Writer, "data: %s\n\n", finalJSON)
					} else {
						fmt.Fprintf(c.Writer, "data: {\"error\": \"Request was cancelled\", \"type\": \"error\", \"is_final\": true}\n\n")
					}
				} else {
					log.Printf("[%s] Stream error: %v", correlationID, err)
					fmt.Fprintf(c.Writer, "data: {\"error\": \"Stream error: %v\", \"type\": \"error\", \"is_final\": true}\n\n", err)
				}
			}
			c.Writer.Flush()
			break
		}
		
		// Convert to API response and send
		response := convertChatMessageResponse(resp)
		responseJSON, err := json.Marshal(response)
		if err != nil {
			log.Printf("[%s] Failed to marshal response: %v", correlationID, err)
			continue
		}
		
		// Send SSE formatted response
		fmt.Fprintf(c.Writer, "data: %s\n\n", responseJSON)
		
		// Flush immediately to ensure real-time streaming
		if flusher, ok := c.Writer.(http.Flusher); ok {
			flusher.Flush()
		}
		
		responseSent = true
		lastResponse = response
		log.Printf("[%s] Sent response chunk, final: %v", correlationID, resp.IsFinal)
		
		// Break if this is the final message
		if resp.IsFinal {
			log.Printf("[%s] Final response sent, ending stream", correlationID)
			break
		}
	}
}

// handleNonStreamingResponse collects all streaming responses and returns as single JSON
func (h *ChatHandler) handleNonStreamingResponse(c *gin.Context, chatClient protos.ChatServiceClient, req *protos.SendMessageRequest) {
	correlationID := c.GetString("request_id")
	
	// Use request context to inherit timeouts and cancellation
	ctx := c.Request.Context()
	
	// Check if client connection is still active
	if ctx.Err() != nil {
		log.Printf("[%s] Client disconnected before starting non-streaming request", correlationID)
		errorResponse := models.NewErrorResponse(models.CodeServiceUnavailable, "Client disconnected", correlationID)
		c.JSON(http.StatusBadRequest, errorResponse)
		return
	}
	
	log.Printf("[%s] Starting non-streaming response collection for session: %s", correlationID, req.SessionId)
	
	stream, err := chatClient.SendMessage(ctx, req)
	if err != nil {
		log.Printf("[%s] Failed to start gRPC stream: %v", correlationID, err)
		httpStatus, errorResponse := models.ConvertGRPCError(err, correlationID)
		c.JSON(httpStatus, errorResponse)
		return
	}

	// Collect all streaming responses
	var allResponses []*protos.ChatMessageResponse
	var finalResponse *protos.ChatMessageResponse
	var combinedContent strings.Builder

	for {
		// Check if client is still connected
		select {
		case <-ctx.Done():
			log.Printf("[%s] Request context cancelled during response collection: %v", correlationID, ctx.Err())
			return
		default:
		}
		
		resp, err := stream.Recv()
		if err != nil {
			if err == io.EOF {
				log.Printf("[%s] Stream ended normally, collected %d responses", correlationID, len(allResponses))
				break
			}
			
			// Handle cancellation gracefully
			if strings.Contains(err.Error(), "Cancelled") || strings.Contains(err.Error(), "context canceled") {
				log.Printf("[%s] Stream cancelled during collection: %v", correlationID, err)
				if len(allResponses) > 0 {
					// Use partial response if we have some data
					log.Printf("[%s] Using partial response with %d chunks", correlationID, len(allResponses))
					break
				} else {
					errorResponse := models.NewErrorResponse(models.CodeServiceUnavailable, "Request was cancelled", correlationID)
					c.JSON(http.StatusServiceUnavailable, errorResponse)
					return
				}
			}
			
			log.Printf("[%s] Stream error during collection: %v", correlationID, err)
			httpStatus, errorResponse := models.ConvertGRPCError(err, correlationID)
			c.JSON(httpStatus, errorResponse)
			return
		}

		allResponses = append(allResponses, resp)
		
		// Append content to combined response
		if resp.Content != "" {
			combinedContent.WriteString(resp.Content)
		}

		// Keep track of the latest response for metadata
		finalResponse = resp
		
		log.Printf("[%s] Collected chunk %d, final: %v", correlationID, len(allResponses), resp.IsFinal)

		// Break if this is the final message
		if resp.IsFinal {
			break
		}
	}

	if finalResponse == nil {
		log.Printf("[%s] No response received from chat service", correlationID)
		errorResponse := models.NewErrorResponse(models.CodeInternalError, "No response received from chat service", correlationID)
		c.JSON(http.StatusInternalServerError, errorResponse)
		return
	}

	// Create combined response using the last response as template but with combined content
	combinedResponse := &protos.ChatMessageResponse{
		SessionId:   finalResponse.SessionId,
		MessageId:   finalResponse.MessageId,
		Content:     combinedContent.String(), // Combined content from all responses
		MessageType: finalResponse.MessageType,
		Status:      finalResponse.Status,
		Timestamp:   finalResponse.Timestamp,
		Metadata:    finalResponse.Metadata,
		IsFinal:     true, // Always final for non-streaming
		ToolCalls:   finalResponse.ToolCalls,
	}

	// Convert gRPC response to API response
	response := convertChatMessageResponse(combinedResponse)
	log.Printf("[%s] Returning combined response with %d characters", correlationID, len(response.Content))
	c.JSON(http.StatusOK, response)
}

// streamChatResponseJSON handles JSON streaming (NDJSON format) for chat responses
func (h *ChatHandler) streamChatResponseJSON(c *gin.Context, chatClient protos.ChatServiceClient, req *protos.SendMessageRequest) {
	// Set JSON streaming headers
	c.Header("Content-Type", "application/x-ndjson")
	c.Header("Cache-Control", "no-cache")
	c.Header("Connection", "keep-alive")
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("X-Accel-Buffering", "no") // Disable nginx buffering
	
	correlationID := c.GetString("request_id")
	
	// Use request context to inherit timeouts and cancellation
	ctx := c.Request.Context()
	
	// Check if client connection is still active
	if ctx.Err() != nil {
		log.Printf("[%s] Client disconnected before starting JSON stream", correlationID)
		return
	}
	
	log.Printf("[%s] Starting JSON streaming response for session: %s", correlationID, req.SessionId)
	
	stream, err := chatClient.SendMessage(ctx, req)
	if err != nil {
		log.Printf("[%s] Failed to start gRPC stream for JSON: %v", correlationID, err)
		errorJSON, _ := json.Marshal(map[string]interface{}{
			"error":    fmt.Sprintf("Failed to start stream: %v", err),
			"type":     "error",
			"is_final": true,
		})
		fmt.Fprintf(c.Writer, "%s\n", errorJSON)
		c.Writer.Flush()
		return
	}
	
	// Track if we've sent any responses to avoid duplicates
	responseSent := false
	var lastResponse *models.ChatMessageResponse
	
	// Stream responses as NDJSON (newline-delimited JSON)
	for {
		// Check if client is still connected
		select {
		case <-ctx.Done():
			log.Printf("[%s] Request context cancelled, stopping JSON stream: %v", correlationID, ctx.Err())
			// Send final response if we had partial data
			if responseSent && lastResponse != nil {
				finalResponse := *lastResponse
				finalResponse.IsFinal = true
				finalResponse.Status = "RESPONSE_STATUS_SUCCESS"
				finalJSON, _ := json.Marshal(finalResponse)
				fmt.Fprintf(c.Writer, "%s\n", finalJSON)
			} else {
				errorJSON, _ := json.Marshal(map[string]interface{}{
					"error":    "Request timeout or cancelled",
					"type":     "error",
					"is_final": true,
				})
				fmt.Fprintf(c.Writer, "%s\n", errorJSON)
			}
			c.Writer.Flush()
			return
		default:
		}
		
		resp, err := stream.Recv()
		if err != nil {
			if err == io.EOF {
				log.Printf("[%s] JSON stream ended normally", correlationID)
				if !responseSent {
					endJSON, _ := json.Marshal(map[string]interface{}{
						"type":     "end",
						"is_final": true,
					})
					fmt.Fprintf(c.Writer, "%s\n", endJSON)
				}
			} else {
				// Handle cancellation gracefully
				if strings.Contains(err.Error(), "Cancelled") || strings.Contains(err.Error(), "context canceled") {
					log.Printf("[%s] JSON stream cancelled: %v", correlationID, err)
					if responseSent && lastResponse != nil {
						// Send final response with accumulated content
						finalResponse := *lastResponse
						finalResponse.IsFinal = true
						finalResponse.Status = "RESPONSE_STATUS_SUCCESS"
						finalJSON, _ := json.Marshal(finalResponse)
						fmt.Fprintf(c.Writer, "%s\n", finalJSON)
					} else {
						errorJSON, _ := json.Marshal(map[string]interface{}{
							"error":    "Request was cancelled",
							"type":     "error",
							"is_final": true,
						})
						fmt.Fprintf(c.Writer, "%s\n", errorJSON)
					}
				} else {
					log.Printf("[%s] JSON stream error: %v", correlationID, err)
					errorJSON, _ := json.Marshal(map[string]interface{}{
						"error":    fmt.Sprintf("Stream error: %v", err),
						"type":     "error",
						"is_final": true,
					})
					fmt.Fprintf(c.Writer, "%s\n", errorJSON)
				}
			}
			c.Writer.Flush()
			break
		}
		
		// Convert to API response and send as JSON line
		response := convertChatMessageResponse(resp)
		responseJSON, err := json.Marshal(response)
		if err != nil {
			log.Printf("[%s] Failed to marshal JSON response: %v", correlationID, err)
			continue
		}
		
		fmt.Fprintf(c.Writer, "%s\n", responseJSON)
		
		// Flush immediately to ensure real-time streaming
		if flusher, ok := c.Writer.(http.Flusher); ok {
			flusher.Flush()
		}
		
		responseSent = true
		lastResponse = response
		log.Printf("[%s] Sent JSON response chunk, final: %v", correlationID, resp.IsFinal)
		
		// Break if this is the final message
		if resp.IsFinal {
			log.Printf("[%s] Final JSON response sent, ending stream", correlationID)
			break
		}
	}
}

// Helper functions for converting between string and enum types

func convertStringToSessionType(sessionType string) protos.SessionType {
	switch sessionType {
	case "workflow":
		return protos.SessionType_SESSION_TYPE_WORKFLOW
	case "chat":
		return protos.SessionType_SESSION_TYPE_CHAT
	case "tool_discovery":
		return protos.SessionType_SESSION_TYPE_TOOL_DISCOVERY
	case "assistance":
		return protos.SessionType_SESSION_TYPE_ASSISTANCE
	default:
		return protos.SessionType_SESSION_TYPE_UNSPECIFIED
	}
}

func convertStringToMessageType(messageType string) protos.MessageType {
	switch messageType {
	case "user":
		return protos.MessageType_MESSAGE_TYPE_USER
	case "assistant":
		return protos.MessageType_MESSAGE_TYPE_ASSISTANT
	case "system":
		return protos.MessageType_MESSAGE_TYPE_SYSTEM
	case "tool_call":
		return protos.MessageType_MESSAGE_TYPE_TOOL_CALL
	case "tool_result":
		return protos.MessageType_MESSAGE_TYPE_TOOL_RESULT
	default:
		return protos.MessageType_MESSAGE_TYPE_UNSPECIFIED
	}
}

// convertChatMessage converts protobuf ChatMessage to API model
func convertChatMessage(proto *protos.ChatMessage) *models.ChatMessage {
	return &models.ChatMessage{
		MessageID:   proto.MessageId,
		SessionID:   proto.SessionId,
		Content:     proto.Content,
		MessageType: proto.MessageType.String(),
		Timestamp:   proto.Timestamp.AsTime(),
		Metadata:    models.StructToMap(proto.Metadata),
		ToolCalls:   convertToolCalls(proto.ToolCalls),
	}
}

// convertChatMessageResponse converts protobuf ChatMessageResponse to API model
func convertChatMessageResponse(proto *protos.ChatMessageResponse) *models.ChatMessageResponse {
	return &models.ChatMessageResponse{
		SessionID:   proto.SessionId,
		MessageID:   proto.MessageId,
		Content:     proto.Content,
		MessageType: proto.MessageType.String(),
		Status:      proto.Status.String(),
		Timestamp:   proto.Timestamp.AsTime(),
		Metadata:    models.StructToMap(proto.Metadata),
		IsFinal:     proto.IsFinal,
		ToolCalls:   convertToolCalls(proto.ToolCalls),
	}
}

// convertToolCalls converts protobuf ToolCall slice to API model slice
func convertToolCalls(protoCalls []*protos.ToolCall) []*models.ToolCall {
	toolCalls := make([]*models.ToolCall, len(protoCalls))
	for i, call := range protoCalls {
		toolCalls[i] = &models.ToolCall{
			ToolID:    call.ToolId,
			ToolName:  call.ToolName,
			Arguments: models.StructToMap(call.Arguments),
			Result:    call.Result,
			Status:    call.Status.String(),
			Timestamp: call.Timestamp.AsTime(),
		}
	}
	return toolCalls
}

// convertSessionMetrics converts protobuf SessionMetrics to API model
func convertSessionMetrics(proto *protos.SessionMetrics) *models.SessionMetrics {
	return &models.SessionMetrics{
		MessageCount:    proto.MessageCount,
		ToolCallsCount:  proto.ToolCallsCount,
		SessionDuration: proto.SessionDuration.AsTime(),
		TokensUsed:      proto.TokensUsed,
	}
} 
