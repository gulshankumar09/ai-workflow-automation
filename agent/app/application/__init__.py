"""
Application Layer for ai-workflow-automation Core Microservice

This layer contains the core application services that implement the business logic
of the workflow generation and execution system.

Services:
- WorkflowService: Workflow generation and management
- ExecutionService: Workflow execution with real-time tracking
- MCPService: MCP tool management and discovery
- UserService: User context and preferences management
- FallbackService: Error recovery and fallback mechanisms
- RealtimeService: Supabase realtime integration
- EventBus: Internal messaging service
- MetricsService: Monitoring and metrics collection
- HealthCheckService: Service health monitoring
"""

from typing import Optional

# Core application services will be imported here as they are implemented
__all__ = [
    # Core services (to be implemented)
    "WorkflowService",
    "ExecutionService", 
    "MCPService",
    "UserService",
    "FallbackService",
    # Integration services (to be implemented)
    "RealtimeService",
    "EventBus",
    "MetricsService", 
    "HealthCheckService"
] 