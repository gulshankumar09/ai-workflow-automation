# ai-workflow-automation API Gateway

The ai-workflow-automation API Gateway is a HTTP/REST API service that provides a bridge between external clients and the core Python gRPC services for the ai-workflow-automation Dynamic Workflow Generation System.

## Architecture

```
Client Applications (Web/Mobile/CLI)
           ↓ HTTP/REST/WebSocket/SSE
     Golang API Gateway
           ↓ gRPC
     Python Core Services
```

## Features

- **RESTful API** - Full HTTP/REST interface for all core services
- **Real-time Streaming** - Server-Sent Events (SSE) and WebSocket support
- **Authentication** - JWT-based authentication with role-based access control
- **Rate Limiting** - Configurable rate limiting per user/IP
- **Health Checks** - Comprehensive health monitoring endpoints
- **Security** - CORS, security headers, and input validation
- **HTTP/2 Support** - High-performance HTTP/2 with h2c
- **Circuit Breaker** - Fault tolerance for gRPC connections
- **Observability** - Prometheus metrics, distributed tracing, structured logging

## Getting Started

### Prerequisites

- Go 1.21 or later
- Protocol Buffers compiler (protoc)
- Running instance of ai-workflow-automation Core Services

### Installation

1. Clone the repository and navigate to the API directory:

```bash
cd api/
```

2. Install dependencies:

```bash
go mod tidy
```

3. Configure the service by copying the sample configuration:

```bash
cp configs/config.yaml configs/local.yaml
# Edit configs/local.yaml with your settings
```

4. Build the service:

```bash
go build ./cmd/server
```

5. Run the service:

```bash
./server
```

The API gateway will start on port 8080 by default.

### Configuration

Configuration can be provided via:

- YAML configuration file (`configs/config.yaml`)
- Environment variables (prefixed with `VERBILIO_`)
- Command line arguments

Key configuration sections:

- `server` - HTTP server settings
- `grpc` - gRPC client connection settings
- `auth` - Authentication and authorization
- `rate_limit` - Rate limiting configuration
- `cors` - Cross-origin resource sharing
- `monitoring` - Health checks and observability

### Environment Variables

```bash
# Server
export PORT=8080
export GRPC_CORE_SERVICE_ADDR=localhost:50051

# Authentication
export JWT_SECRET=your-jwt-secret
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_KEY=your-supabase-key

# Database
export DATABASE_URL=postgresql://user:pass@localhost/dbname

# Environment
export ENVIRONMENT=production
```

## API Documentation

### Health Endpoints

- `GET /health` - Basic health check
- `GET /health/ready` - Readiness probe (checks gRPC connectivity)
- `GET /health/live` - Liveness probe

### API v1 Endpoints

All API endpoints require authentication via `Authorization: Bearer <token>` header.

#### Workflows

- `POST /api/v1/workflows/generate` - Generate new workflow
- `GET /api/v1/workflows/generate/stream` - Stream workflow generation (SSE)
- `GET /api/v1/workflows/{id}` - Get workflow details
- `GET /api/v1/workflows` - List user workflows
- `PUT /api/v1/workflows/{id}` - Update workflow
- `DELETE /api/v1/workflows/{id}` - Delete workflow
- `POST /api/v1/workflows/{id}/validate` - Validate workflow

#### Executions

- `POST /api/v1/executions` - Execute workflow
- `GET /api/v1/executions/{id}/stream` - Stream execution progress (SSE)
- `GET /api/v1/executions/{id}` - Get execution status
- `GET /api/v1/executions` - List user executions
- `POST /api/v1/executions/{id}/cancel` - Cancel execution
- `GET /api/v1/executions/{id}/logs` - Get execution logs

#### Chat

- `POST /api/v1/chat/sessions` - Start chat session
- `POST /api/v1/chat/sessions/{id}/messages` - Send message
- `GET /api/v1/chat/sessions/{id}/stream` - SSE chat streaming
- `GET /api/v1/chat/sessions/{id}/ws` - WebSocket chat
- `GET /api/v1/chat/sessions/{id}` - Get session context
- `GET /api/v1/chat/sessions/{id}/history` - Get chat history
- `DELETE /api/v1/chat/sessions/{id}` - End chat session

#### Users

- `GET /api/v1/users/profile` - Get user profile
- `PUT /api/v1/users/preferences` - Update preferences
- `GET /api/v1/users/context` - Get user context
- `PUT /api/v1/users/context` - Update context
- `GET /api/v1/users/tools` - Get user tools
- `POST /api/v1/users/tools` - Register new tool
- `GET /api/v1/users/activity` - Get activity metrics

## API Streaming Capabilities

The API Gateway now properly handles streaming responses from the Core service in multiple formats:

### 1. Non-Streaming Response (Default)

When `stream: false` or no stream parameter:

- Collects ALL streaming chunks from Core service
- Combines content into a single response
- Returns complete JSON response

```bash
curl -X POST "http://localhost:8082/api/v1/chat/sessions/session-id/messages" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "message": "I want to create a workflow to sync my GitHub issues to a Slack channel",
    "stream": false
  }'
```

### 2. Server-Sent Events (SSE) Streaming

When `stream: true` (default streaming format):

- Real-time streaming via SSE
- Compatible with EventSource API

```bash
curl -X POST "http://localhost:8082/api/v1/chat/sessions/session-id/messages" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "message": "I want to create a workflow to sync my GitHub issues to a Slack channel",
    "stream": true
  }'
```

### 3. JSON Streaming (NDJSON)

When `stream: true` with `Accept: application/x-ndjson` header:

- Newline-delimited JSON streaming
- Each line is a complete JSON response chunk

```bash
curl -X POST "http://localhost:8082/api/v1/chat/sessions/session-id/messages" \
  -H "Content-Type: application/json" \
  -H "Accept: application/x-ndjson" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "message": "I want to create a workflow to sync my GitHub issues to a Slack channel",
    "stream": true
  }'
```

### Response Format

Each streaming chunk follows this structure:

```json
{
  "session_id": "session-id",
  "message_id": "msg-id",
  "content": "partial response content",
  "message_type": "MESSAGE_TYPE_ASSISTANT",
  "status": "RESPONSE_STATUS_SUCCESS",
  "timestamp": "2024-01-01T00:00:00Z",
  "is_final": false,
  "tool_calls": [],
  "metadata": {}
}
```

The `is_final` flag indicates when the response is complete.

## Development

### Project Structure

```
api/
├── cmd/server/          # Main application entry point
├── internal/
│   ├── config/          # Configuration management
│   ├── handlers/        # HTTP request handlers
│   ├── middleware/      # HTTP middleware (auth, CORS, etc.)
│   ├── models/          # Data models
│   ├── services/        # Business logic services
│   └── utils/           # Utility functions
├── pkg/
│   ├── auth/            # Authentication utilities
│   ├── grpc_client/     # gRPC client management
│   └── validator/       # Input validation
├── configs/             # Configuration files
├── docs/                # Documentation
└── scripts/             # Build and deployment scripts
```

### Building

```bash
# Build for current platform
go build ./cmd/server

# Build for Linux
GOOS=linux GOARCH=amd64 go build ./cmd/server

# Build with version info
go build -ldflags "-X main.version=$(git describe --tags)" ./cmd/server
```

### Testing

```bash
# Run unit tests
go test ./...

# Run tests with coverage
go test -race -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

### Generating Protobuf Code

```bash
cd pkg/grpc_client/protos
protoc --go_out=. --go-grpc_out=. --go_opt=paths=source_relative --go-grpc_opt=paths=source_relative *.proto
```

## Deployment

### Docker

```bash
# Build Docker image
docker build -t ai-workflow-automation/api-gateway .

# Run container
docker run -p 8080:8080 -e GRPC_CORE_SERVICE_ADDR=host.docker.internal:50051 ai-workflow-automation/api-gateway
```

### Kubernetes

```bash
# Deploy to Kubernetes
kubectl apply -f k8s/
```

## Monitoring

The API gateway exposes Prometheus metrics on `/metrics` endpoint and supports distributed tracing with OpenTelemetry.

Key metrics:

- Request duration and count
- gRPC connection health
- Rate limiting statistics
- Circuit breaker state

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run linting and tests
6. Submit a pull request

## License

This project is part of the ai-workflow-automation Dynamic Workflow Generation System.
