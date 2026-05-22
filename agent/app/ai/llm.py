"""
Gemini LLM Provider

A simple, centralized LLM provider using Google's Gemini model.
This file provides a single LLM instance that can be used throughout the application.
"""

from builtins import ValueError
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Optional
import os
from app.shared.config import get_settings

# Global LLM instance
_llm_instance: Optional[ChatGoogleGenerativeAI] = None

def get_llm() -> ChatGoogleGenerativeAI:
    """
    Get the global LLM instance (Gemini).
    
    Returns the exact ChatGoogleGenerativeAI instance from langchain_google_genai
    so you can access all framework methods directly.
    
    Returns:
        ChatGoogleGenerativeAI: The Gemini LLM instance
    """
    global _llm_instance
    
    if _llm_instance is None:
        _llm_instance = _create_gemini_llm()
    
    return _llm_instance

def _create_gemini_llm() -> ChatGoogleGenerativeAI:
    """Create and configure the Gemini LLM instance"""
    settings = get_settings()
    
    # Get API key from settings or environment
    api_key = settings.llm.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError(
            "Gemini API key not found. Please set GEMINI_API_KEY or GOOGLE_API_KEY environment variable "
            "or configure it in settings."
        )
    
    return ChatGoogleGenerativeAI(
        model=settings.llm.model,
        google_api_key=api_key,
        temperature=settings.llm.temperature,
        max_output_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
        max_retries=3,
        # convert_system_message_to_human=True,  # Required for Gemini
    )

def reset_llm() -> None:
    """Reset the global LLM instance (useful for testing)"""
    global _llm_instance
    _llm_instance = None

# For backward compatibility with existing factory pattern
class LLMProviderFactory:
    """Legacy factory class for backward compatibility"""
    
    @staticmethod
    def create_provider(provider_type: str = "gemini"):
        """Create LLM provider (always returns Gemini for now)"""
        return get_llm()
    
    @staticmethod
    async def get_best_available_provider(preferred: str = "gemini"):
        """Get the best available provider (always returns Gemini for now)"""
        return get_llm()

def get_llm_factory():
    """Get LLM factory instance for backward compatibility"""
    return LLMProviderFactory() 