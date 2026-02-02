"""Load LLM configuration for the Crew workflow."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    """Minimal LLM config placeholder for Crew workflow."""

    provider: str
    model: str
    api_key_env: str
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    def api_key(self) -> Optional[str]:
        """Return API key from environment, if set."""
        return os.getenv(self.api_key_env)


DEFAULT_CONFIG_PATH = os.path.join(os.getcwd(), "config", "crewai.json")


def load_llm_config(path: Optional[str] = None) -> LLMConfig:
    """Load LLM config from JSON file.

    NOTE: API keys are read from environment variables only.
    """

    cfg_path = path or DEFAULT_CONFIG_PATH
    if not os.path.exists(cfg_path):
        return LLMConfig(provider="minimax", model="abab6", api_key_env="MINIMAX_API_KEY")

    with open(cfg_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return LLMConfig(
        provider=data.get("provider", "minimax"),
        model=data.get("model", "abab6"),
        api_key_env=data.get("api_key_env", "MINIMAX_API_KEY"),
        base_url=data.get("base_url"),
        temperature=data.get("temperature"),
        max_tokens=data.get("max_tokens"),
    )
