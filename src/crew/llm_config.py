"""Load LLM configuration for the Crew workflow."""

from __future__ import annotations

import json
import os
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .exceptions import ConfigurationError


class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    provider: str = Field(..., description="LLM provider name")
    model: str = Field(..., description="Model identifier")
    api_key_env: str = Field(..., description="Environment variable for API key")
    base_url: Optional[str] = Field(None, description="Base URL for API")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(4096, gt=0, le=128000, description="Maximum output tokens")
    timeout: int = Field(300, gt=0, description="Request timeout in seconds")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate provider name."""
        supported = ["minimax", "openai", "anthropic", "azure", "ollama", "gemini"]
        if v not in supported:
            raise ValueError(f"Provider must be one of {supported}, got: {v}")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate model name is not empty."""
        if not v or not v.strip():
            raise ValueError("Model name cannot be empty")
        return v.strip()

    def api_key(self) -> str:
        """Get API key from environment variable.

        Raises:
            ConfigurationError: If API key is not set in environment
        """
        key = os.getenv(self.api_key_env)
        if not key:
            raise ConfigurationError(
                f"API key not found in environment variable: {self.api_key_env}",
                {"provider": self.provider, "api_key_env": self.api_key_env},
            )
        return key

    def has_api_key(self) -> bool:
        """Check if API key is set in environment."""
        return os.getenv(self.api_key_env) is not None


class LLMConfig(BaseModel):
    """Complete LLM configuration with fallback support."""

    primary: LLMProviderConfig = Field(..., description="Primary LLM provider")
    fallback: List[LLMProviderConfig] = Field(default_factory=list, description="Fallback providers")
    enable_memory: bool = Field(True, description="Enable CrewAI memory system")
    enable_parallel: bool = Field(False, description="Enable parallel task execution")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay: float = Field(2.0, ge=0.0, description="Delay between retries in seconds")

    @classmethod
    def from_provider_config(cls, provider_config: LLMProviderConfig, **kwargs) -> LLMConfig:
        """Create LLMConfig from a single provider configuration."""
        return cls(primary=provider_config, **kwargs)

    def all_providers(self) -> List[LLMProviderConfig]:
        """Get all configured providers (primary + fallback)."""
        return [self.primary] + self.fallback


DEFAULT_CONFIG_PATH = os.path.join(os.getcwd(), "config", "crewai.json")


def load_llm_config(path: Optional[str] = None) -> LLMConfig:
    """Load LLM config from JSON file.

    Args:
        path: Path to config file (defaults to config/crewai.json)

    Returns:
        LLMConfig: Validated configuration

    Raises:
        ConfigurationError: If config is invalid or file cannot be read

    NOTE: API keys are read from environment variables only, never from config files.
    """
    cfg_path = path or DEFAULT_CONFIG_PATH

    # Default configuration if file doesn't exist
    if not os.path.exists(cfg_path):
        return LLMConfig(
            primary=LLMProviderConfig(
                provider="minimax",
                model="MiniMax-M2.1",
                api_key_env="MINIMAX_API_KEY",
                base_url="https://api.minimaxi.com/v1",
            )
        )

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON in config file: {cfg_path}", {"error": str(exc)}) from exc
    except IOError as exc:
        raise ConfigurationError(f"Cannot read config file: {cfg_path}", {"error": str(exc)}) from exc

    try:
        # Support both old format (single provider) and new format (with fallback)
        if "primary" in data:
            # New format with fallback support
            return LLMConfig(**data)
        else:
            # Old format: single provider configuration
            provider_config = LLMProviderConfig(**data)
            return LLMConfig.from_provider_config(
                provider_config,
                enable_memory=data.get("enable_memory", True),
                enable_parallel=data.get("enable_parallel", False),
                max_retries=data.get("max_retries", 3),
            )
    except Exception as exc:
        raise ConfigurationError(f"Invalid configuration in {cfg_path}: {exc}") from exc


def validate_config(config: LLMConfig) -> None:
    """Validate that configuration is usable.

    Args:
        config: Configuration to validate

    Raises:
        ConfigurationError: If configuration is not usable
    """
    # Check that at least primary provider has API key
    if not config.primary.has_api_key():
        raise ConfigurationError(
            f"Primary provider '{config.primary.provider}' API key not set",
            {"api_key_env": config.primary.api_key_env},
        )

    # Warn about fallback providers without API keys
    for i, fallback in enumerate(config.fallback):
        if not fallback.has_api_key():
            from src.log_manager import log

            log.warning(
                f"Fallback provider #{i+1} '{fallback.provider}' API key not set: {fallback.api_key_env}"
            )


__all__ = ["LLMConfig", "LLMProviderConfig", "load_llm_config", "validate_config", "DEFAULT_CONFIG_PATH"]
