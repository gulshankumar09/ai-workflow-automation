# ai-workflow-automation

A repository for a dynamic workflow automation platform with a Python-based core service and a Go API gateway.

## Project Structure

- `agent/`
  - Python core service
  - Implements dynamic workflow generation and execution using Domain-Driven Design (DDD)
  - Uses FastAPI, gRPC, MCP, LangGraph, and a custom exception handling framework
- `api/`
  - Go-based HTTP/REST API gateway
  - Bridges external clients to Python gRPC services
  - Supports authentication, rate limiting, streaming, observability, and security
- `docs/`
  - Architecture and product requirement documentation

## Key Features

- Dynamic workflow generation and execution
- Model Context Protocol (MCP) integrations for external tools
- Real-time progress tracking and streaming execution updates
- Structured error handling with custom exceptions
- REST API gateway with JWT auth, rate limiting, and health checks
- gRPC communication between gateway and core services

## Technologies

- Python 3.12+
- FastAPI
- gRPC (`grpcio`, `grpcio-tools`, `grpcio-reflection`, `grpcio-status`)
- LangGraph
- MCP
- Pydantic / Pydantic Settings
- Go 1.21+ for API gateway
- Supabase, PostgreSQL, and external tool integrations

## Getting Started

### Core Service (`agent/`)

1. Install dependencies:

```bash
cd agent
uv sync
```

2. Run tests:

```bash
python -m pytest app/tests/ -v
```

3. Start the core service (example):

```bash
uvicorn app.main:app --reload
```

### API Gateway (`api/`)

1. Install dependencies:

```bash
cd api
go mod tidy
```

2. Copy and update config:

```bash
cp configs/config.yaml configs/local.yaml
```

3. Build and run:

```bash
go build ./cmd/server
./server
```

## Configuration

- Python dependencies are managed in `agent/pyproject.toml`
- API gateway config is in `api/configs/config.yaml`
- Environment variables may include JWT secrets, database URLs, GRPC target addresses, and Supabase credentials

## Notes

- The core service is designed for workflow orchestration, MCP server management, and resilient execution.
- The API gateway acts as a secure entrypoint for external clients and provides HTTP/REST access to the core.

## Useful Links

- `agent/README.md` - Python core service documentation
- `api/README.md` - API gateway documentation
- `docs/` - architecture and product docs
