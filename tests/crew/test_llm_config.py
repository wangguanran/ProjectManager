"""Tests for LLM configuration."""

import json
import os
import tempfile

import pytest

from src.crew.exceptions import ConfigurationError
from src.crew.llm_config import LLMConfig, LLMProviderConfig, load_llm_config, validate_config


class TestLLMProviderConfig:
    """Tests for LLMProviderConfig."""

    def test_valid_provider_config(self):
        """Test creating a valid provider configuration."""
        os.environ["TEST_KEY"] = "test_api_key"
        
        config = LLMProviderConfig(
            provider="minimax",
            model="MiniMax-M2.1",
            api_key_env="TEST_KEY",
            base_url="https://api.minimaxi.com/v1",
        )
        
        assert config.provider == "minimax"
        assert config.model == "MiniMax-M2.1"
        assert config.api_key() == "test_api_key"
        assert config.has_api_key()
        
        del os.environ["TEST_KEY"]

    def test_invalid_provider(self):
        """Test invalid provider name."""
        with pytest.raises(ValueError, match="Provider must be one of"):
            LLMProviderConfig(
                provider="invalid_provider",
                model="model",
                api_key_env="KEY",
            )

    def test_empty_model(self):
        """Test empty model name."""
        with pytest.raises(ValueError, match="Model name cannot be empty"):
            LLMProviderConfig(
                provider="minimax",
                model="  ",
                api_key_env="KEY",
            )

    def test_missing_api_key(self):
        """Test missing API key."""
        config = LLMProviderConfig(
            provider="minimax",
            model="model",
            api_key_env="NONEXISTENT_KEY",
        )
        
        assert not config.has_api_key()
        with pytest.raises(ConfigurationError):
            config.api_key()

    def test_temperature_validation(self):
        """Test temperature bounds."""
        with pytest.raises(ValueError):
            LLMProviderConfig(
                provider="minimax",
                model="model",
                api_key_env="KEY",
                temperature=-0.1,  # Too low
            )
        
        with pytest.raises(ValueError):
            LLMProviderConfig(
                provider="minimax",
                model="model",
                api_key_env="KEY",
                temperature=2.1,  # Too high
            )


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_create_config_with_primary_only(self, mock_llm_config):
        """Test creating config with only primary provider."""
        assert mock_llm_config.primary.provider == "minimax"
        assert len(mock_llm_config.fallback) == 0
        assert mock_llm_config.max_retries == 2

    def test_create_config_with_fallback(self):
        """Test creating config with fallback providers."""
        os.environ["PRIMARY_KEY"] = "key1"
        os.environ["FALLBACK_KEY"] = "key2"
        
        primary = LLMProviderConfig(
            provider="minimax",
            model="model1",
            api_key_env="PRIMARY_KEY",
        )
        fallback = LLMProviderConfig(
            provider="openai",
            model="gpt-4",
            api_key_env="FALLBACK_KEY",
        )
        
        config = LLMConfig(primary=primary, fallback=[fallback])
        
        assert len(config.all_providers()) == 2
        assert config.all_providers()[0].provider == "minimax"
        assert config.all_providers()[1].provider == "openai"
        
        del os.environ["PRIMARY_KEY"]
        del os.environ["FALLBACK_KEY"]

    def test_max_retries_validation(self):
        """Test max retries bounds."""
        os.environ["TEST_KEY"] = "key"
        
        primary = LLMProviderConfig(
            provider="minimax",
            model="model",
            api_key_env="TEST_KEY",
        )
        
        with pytest.raises(ValueError):
            LLMConfig(primary=primary, max_retries=-1)
        
        with pytest.raises(ValueError):
            LLMConfig(primary=primary, max_retries=11)
        
        del os.environ["TEST_KEY"]


class TestLoadLLMConfig:
    """Tests for load_llm_config function."""

    def test_load_default_config_when_file_missing(self):
        """Test loading default config when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "nonexistent.json")
            config = load_llm_config(config_path)
            
            assert config.primary.provider == "minimax"
            assert config.primary.model == "MiniMax-M2.1"

    def test_load_config_from_file(self):
        """Test loading config from JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "test_config.json")
            
            config_data = {
                "provider": "openai",
                "model": "gpt-4",
                "api_key_env": "OPENAI_KEY",
                "base_url": "https://api.openai.com/v1",
                "temperature": 0.7,
                "max_tokens": 2000,
            }
            
            with open(config_path, "w") as f:
                json.dump(config_data, f)
            
            config = load_llm_config(config_path)
            
            assert config.primary.provider == "openai"
            assert config.primary.model == "gpt-4"
            assert config.primary.temperature == 0.7

    def test_load_config_invalid_json(self):
        """Test loading config with invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "invalid.json")
            
            with open(config_path, "w") as f:
                f.write("{ invalid json }")
            
            with pytest.raises(ConfigurationError, match="Invalid JSON"):
                load_llm_config(config_path)

    def test_load_config_new_format(self):
        """Test loading config with new format (primary + fallback)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "new_format.json")
            
            config_data = {
                "primary": {
                    "provider": "minimax",
                    "model": "model1",
                    "api_key_env": "KEY1",
                },
                "fallback": [
                    {
                        "provider": "openai",
                        "model": "gpt-4",
                        "api_key_env": "KEY2",
                    }
                ],
                "enable_memory": True,
                "max_retries": 3,
            }
            
            with open(config_path, "w") as f:
                json.dump(config_data, f)
            
            config = load_llm_config(config_path)
            
            assert config.primary.provider == "minimax"
            assert len(config.fallback) == 1
            assert config.fallback[0].provider == "openai"
            assert config.enable_memory
            assert config.max_retries == 3


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_validate_valid_config(self, mock_llm_config):
        """Test validating a valid configuration."""
        # Should not raise any exception
        validate_config(mock_llm_config)

    def test_validate_config_missing_api_key(self):
        """Test validating config with missing API key."""
        config = LLMConfig(
            primary=LLMProviderConfig(
                provider="minimax",
                model="model",
                api_key_env="NONEXISTENT_KEY",
            )
        )
        
        with pytest.raises(ConfigurationError, match="API key not set"):
            validate_config(config)

    def test_validate_config_warns_on_missing_fallback_key(self, mock_llm_config, caplog):
        """Test that validation warns about missing fallback API keys."""
        fallback = LLMProviderConfig(
            provider="openai",
            model="gpt-4",
            api_key_env="MISSING_FALLBACK_KEY",
        )
        
        mock_llm_config.fallback.append(fallback)
        
        validate_config(mock_llm_config)
        
        # Should log a warning, not raise an error
        assert "Fallback provider" in caplog.text
        assert "MISSING_FALLBACK_KEY" in caplog.text
