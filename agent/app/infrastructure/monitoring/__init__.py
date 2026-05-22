"""
Monitoring Infrastructure Module

This module provides monitoring and reliability patterns for the ai-workflow-automation system,
including circuit breakers for external service protection and health monitoring.
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitBreakerException,
    MultiServerCircuitBreaker  # Basic version
)

from .multi_server_circuit_breaker import (
    EnhancedMultiServerCircuitBreaker,  # Enhanced version
    ServerHealthStatus,
    FallbackStrategy,
    ServerMetrics
)

__all__ = [
    # Basic Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig", 
    "CircuitBreakerState",
    "CircuitBreakerException",
    "MultiServerCircuitBreaker",
    
    # Enhanced Multi-Server Circuit Breaker
    "EnhancedMultiServerCircuitBreaker",
    "ServerHealthStatus",
    "FallbackStrategy", 
    "ServerMetrics"
] 