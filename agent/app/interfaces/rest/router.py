"""
Main REST API Router for ai-workflow-automation Core Microservice.

This module creates and configures the main FastAPI router that includes
all REST endpoints for the core microservice.
"""

from fastapi import APIRouter

from .endpoints.chat_endpoints import create_chat_router

def create_rest_router() -> APIRouter:
    """
    Create the main REST API router.
    
    Returns:
        APIRouter configured with all REST endpoints
    """
    router = APIRouter()
    
    # Include chat endpoints
    chat_router = create_chat_router()
    router.include_router(chat_router)
    
    return router
