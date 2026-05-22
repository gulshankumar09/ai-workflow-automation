# AI Module - LLM Provider

This module provides a centralized, simple LLM provider for the ai-workflow-automation Core Microservice.

## Architecture

The AI module follows a **singleton pattern** with easy replacement capabilities:

```
app/ai/
├── __init__.py          # Package initialization
├── llm.py              # Main LLM provider (Gemini)
├── factory.py          # Backward compatibility factory
└── README.md           # This file
```

## Usage

### Basic Usage

```python
from app.ai.llm import get_llm

# Get the LLM instance (always returns the same instance)
llm = get_llm()

# Use with LangChain methods
response = await llm.ainvoke("Hello, how are you?")
print(response.content)
```

### Using in LangGraph Nodes

```python
from app.ai.llm import get_llm

async def my_node(state: MyState) -> Dict[str, Any]:
    llm = get_llm()

    prompt = "What is the meaning of life?"
    response = await llm.ainvoke(prompt)

    return {"response": response.content}
```

### Backward Compatibility

The module provides backward compatibility with the old factory pattern:

```python
from app.ai.factory import LLMProviderFactory, get_llm_factory

# Old way (still works)
factory = LLMProviderFactory()
llm = factory.create_provider()

# Or
factory = get_llm_factory()
llm = await factory.get_best_available_provider("gemini")
```

## Current Implementation: Gemini

The module currently uses **Google's Gemini** model via `langchain-google-genai`.

### Configuration

Set the API key via environment variables:

```bash
export GEMINI_API_KEY="your-api-key-here"
# OR
export GOOGLE_API_KEY="your-api-key-here"
```

### Model Configuration

The LLM is configured through the application settings (`app/shared/config.py`):

```python
# Default settings
model = "gemini-1.5-flash"  # or "gemini-1.5-pro"
temperature = 0.7
max_tokens = 2048
timeout = 60
```

## Replacing the LLM Provider

To replace Gemini with another provider (e.g., OpenAI, Anthropic), you only need to modify `app/ai/llm.py`:

### Example: Switching to OpenAI

```python
# app/ai/llm.py
from langchain_openai import ChatOpenAI
from typing import Optional
import os
from app.shared.config import get_settings

_llm_instance: Optional[ChatOpenAI] = None

def get_llm() -> ChatOpenAI:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = _create_openai_llm()
    return _llm_instance

def _create_openai_llm() -> ChatOpenAI:
    settings = get_settings()
    api_key = settings.llm.api_key or os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OpenAI API key not found")

    return ChatOpenAI(
        model=settings.llm.model,
        api_key=api_key,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
    )
```

### Example: Switching to Anthropic Claude

```python
# app/ai/llm.py
from langchain_anthropic import ChatAnthropic
from typing import Optional
import os
from app.shared.config import get_settings

_llm_instance: Optional[ChatAnthropic] = None

def get_llm() -> ChatAnthropic:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = _create_anthropic_llm()
    return _llm_instance

def _create_anthropic_llm() -> ChatAnthropic:
    settings = get_settings()
    api_key = settings.llm.api_key or os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError("Anthropic API key not found")

    return ChatAnthropic(
        model=settings.llm.model,  # e.g., "claude-3-5-sonnet-20241022"
        api_key=api_key,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
    )
```

## Testing

Run the test script to verify the LLM provider works:

```bash
cd core
python test_llm.py
```

## Key Benefits

1. **Centralized**: Single point of LLM configuration
2. **Simple**: No complex factory patterns or type abstractions
3. **Replaceable**: Easy to swap providers by editing one file
4. **Standard**: Returns exact LangChain objects with all methods
5. **Efficient**: Singleton pattern prevents multiple instances
6. **Compatible**: Works with all LangChain/LangGraph APIs

## Best Practices

1. **Always use `get_llm()`** instead of creating instances directly
2. **Use `await llm.ainvoke()`** for async operations
3. **Use `llm.invoke()`** for sync operations (if needed)
4. **Access `.content`** from responses to get text content
5. **Reset for testing** using `reset_llm()` in test teardown

## Environment Variables

| Variable          | Description                            | Required    |
| ----------------- | -------------------------------------- | ----------- |
| `GEMINI_API_KEY`  | Google Gemini API key                  | Yes         |
| `GOOGLE_API_KEY`  | Alternative Google API key             | Alternative |
| `LLM_MODEL`       | Model name (default: gemini-1.5-flash) | No          |
| `LLM_TEMPERATURE` | Temperature (default: 0.7)             | No          |
| `LLM_MAX_TOKENS`  | Max tokens (default: 2048)             | No          |
| `LLM_TIMEOUT`     | Timeout in seconds (default: 60)       | No          |
