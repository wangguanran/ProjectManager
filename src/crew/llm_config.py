"""Load LLM configuration for the Crew workflow."""

from __future__ import annotations

import json
import os
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, field_validator

from .exceptions import ConfigurationError


class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider.

    Supports both API-key and OAuth token credentials by pulling the secret
    from an environment variable. Default remains API key for backward
    compatibility.
    """

    provider: str = Field(..., description="LLM provider name")
    model: str = Field(..., description="Model identifier")
    api_key_env: Optional[str] = Field(
        None, description="Environment variable for API key (legacy/default)"
    )
    credential_env: Optional[str] = Field(
        None, description="Environment variable holding OAuth access token or other credential"
    )
    auth_mode: Literal["api_key", "oauth"] = Field(
        "api_key", description="Credential type; defaults to API key"
    )
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

    @field_validator("auth_mode")
    @classmethod
    def validate_auth_mode(cls, v: str) -> str:
        """Validate auth mode value."""
        if v not in {"api_key", "oauth"}:
            raise ValueError("auth_mode must be 'api_key' or 'oauth'")
        return v

    @field_validator("credential_env")
    @classmethod
    def default_credential_env(cls, v: Optional[str], values: dict) -> Optional[str]:
        """Use api_key_env as credential if oauth mode but credential not set."""
        auth_mode = values.get("auth_mode", "api_key")
        if v is None and auth_mode == "oauth":
            # fallback to api_key_env for convenience/migration
            return values.get("api_key_env")
        return v

    @field_validator("api_key_env")
    @classmethod
    def ensure_credential_present(cls, v: Optional[str], values: dict) -> Optional[str]:
        """Ensure at least one credential source is provided."""
        credential_env = values.get("credential_env")
        auth_mode = values.get("auth_mode", "api_key")

        # In api_key mode we need api_key_env
        if auth_mode == "api_key" and not v:
            raise ValueError("api_key_env is required when auth_mode is 'api_key'")

        # In oauth mode we need credential_env (or api_key_env if reused)
        if auth_mode == "oauth" and not (credential_env or v):
            raise ValueError("credential_env (or api_key_env) is required when auth_mode is 'oauth'")

        return v

    def credential_env_name(self) -> str:
        """Return the env var name that should hold the credential."""
        return self.credential_env or self.api_key_env  # api_key_env kept for compatibility

    def credential(self) -> str:
        """Get credential (API key or OAuth token) from environment variable.

        Raises:
            ConfigurationError: If credential is not set in environment
        """
        env_name = self.credential_env_name()
        key = os.getenv(env_name) if env_name else None
        if not key:
            raise ConfigurationError(
                f"Credential not found in environment variable: {env_name}",
                {
                    "provider": self.provider,
                    "auth_mode": self.auth_mode,
                    "credential_env": env_name,
                },
            )
        return key

    def has_credential(self) -> bool:
        """Check if credential is set in environment."""
        env_name = self.credential_env_name()
        return env_name is not None and os.getenv(env_name) is not None


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
    # Check that at least primary provider has credential
    if not config.primary.has_credential():
        raise ConfigurationError(
            f"Primary provider '{config.primary.provider}' credential not set",
            {
                "auth_mode": config.primary.auth_mode,
                "credential_env": config.primary.credential_env_name(),
            },
        )

    # Warn about fallback providers without credentials
    for i, fallback in enumerate(config.fallback):
        if not fallback.has_credential():
            from src.log_manager import log

            log.warning(
                f"Fallback provider #{i+1} '{fallback.provider}' credential not set: {fallback.credential_env_name()}"
            )


__all__ = ["LLMConfig", "LLMProviderConfig", "load_llm_config", "validate_config", "DEFAULT_CONFIG_PATH"]
