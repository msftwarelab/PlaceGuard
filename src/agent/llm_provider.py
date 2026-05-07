"""LLM provider abstraction for multi-model support."""

import os
import json
from abc import ABC, abstractmethod
from typing import Any, Optional
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseLanguageModel


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


def get_llm_model(
    provider: LLMProvider = LLMProvider.OPENAI,
    model_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> BaseLanguageModel:
    """
    Get an LLM model instance from the specified provider.
    
    Args:
        provider: Which LLM provider to use
        model_name: Specific model name (uses defaults if None)
        temperature: Model temperature for sampling
        max_tokens: Maximum tokens in response
        
    Returns:
        Configured language model instance
        
    Raises:
        ValueError: If provider is unsupported or API key missing
    """
    
    if provider == LLMProvider.OPENAI:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        model = model_name or "gpt-4-turbo-preview"
        return ChatOpenAI(
            model_name=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    elif provider == LLMProvider.ANTHROPIC:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        model = model_name or "claude-3-opus-20240229"
        return ChatAnthropic(
            model_name=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    elif provider == LLMProvider.GEMINI:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        model = model_name or "gemini-pro"
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def get_default_llm(temperature: float = 0.7) -> BaseLanguageModel:
    """
    Get the default LLM model with fallback support.
    
    Tries providers in order: OpenAI → Anthropic → Gemini
    Uses the first provider with a valid API key.
    
    Args:
        temperature: Model temperature for sampling
        
    Returns:
        Configured language model instance
        
    Raises:
        ValueError: If no LLM provider is available
    """
    
    for provider in [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.GEMINI]:
        try:
            return get_llm_model(provider, temperature=temperature)
        except ValueError:
            continue
    
    raise ValueError(
        "No LLM provider available. Set one of: "
        "OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY"
    )
