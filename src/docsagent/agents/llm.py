"""
LLM utilities using LangGraph's init_chat_model
"""
import os
from typing import Optional
from loguru import logger

from langchain_core.language_models import BaseChatModel
from langchain.chat_models import init_chat_model

from docsagent import config


def set_api_key(api_key: str, model_name: str):
    """
    Set API key based on model provider
    
    Args:
        api_key: API key for the model provider
        model_name: Model name to determine the provider
    """
    model_lower = model_name.lower()
    
    if 'openai' in model_lower or 'gpt' in model_lower:
        os.environ['OPENAI_API_KEY'] = api_key
        logger.debug("Set OPENAI_API_KEY")
    elif 'anthropic' in model_lower or 'claude' in model_lower:
        os.environ['ANTHROPIC_API_KEY'] = api_key
        logger.debug("Set ANTHROPIC_API_KEY")
    elif 'google' in model_lower or 'gemini' in model_lower:
        os.environ['GOOGLE_API_KEY'] = api_key
        logger.debug("Set GOOGLE_API_KEY")
    elif 'moonshot' in model_lower or 'kimi' in model_lower:
        os.environ['OPENAI_API_KEY'] = api_key
        logger.debug("Set OPENAI_API_KEY")
    elif 'qwen' in model_lower:
        os.environ['OPENAI_API_KEY'] = api_key
        logger.debug("Set OPENAI_API_KEY")
    else:
        # For other providers, try to set a generic key
        logger.warning(f"Unknown provider for model {model_name}, API key may not be set correctly")


def create_chat_model(
    model: Optional[str] = None,
    model_provider: Optional[str] = None,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs
) -> BaseChatModel:
    """
    Create a chat model using LangGraph's init_chat_model
    
    Args:
        model: Model name (e.g., 'openai:gpt-3.5-turbo', 'anthropic:claude-3-sonnet')
        api_key: API key for the model provider
        api_url: Custom API URL if needed
        temperature: Temperature for generation (0.0-1.0)
        max_tokens: Maximum tokens to generate
        **kwargs: Additional parameters for the model
        
    Returns:
        Initialized chat model instance
    """
    model_name = model or config.LLM_MODEL
    model_provider = model_provider or config.LLM_PROVIDER
    api_key = api_key or config.LLM_API_KEY
    api_url = api_url or config.LLM_URL
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens if max_tokens is not None else config.LLM_MAX_TOKENS

    # Set API key if provided
    if api_key:
        set_api_key(api_key, model_name)
    
    # Initialize the chat model
    try:
        if api_url is not None and model_provider is not None:
            chat_model = init_chat_model(
                model=model_name,
                model_provider=model_provider,
                api_key=api_key,
                base_url=api_url,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        else:
            chat_model = init_chat_model(
                model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        logger.info(f"Initialized chat model: {model_name}")
        return chat_model
    except Exception as e:
        logger.error(f"Failed to initialize chat model {model_name}: {e}")
        raise


# Global default chat model instance
_default_chat_model = None


def get_default_chat_model() -> BaseChatModel:
    """
    Get or create the default chat model instance
    
    Returns:
        Default chat model instance
    """
    global _default_chat_model
    if _default_chat_model is None:
        _default_chat_model = create_chat_model()
    return _default_chat_model