"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_settings_defaults():
    """Test that settings use sensible defaults."""
    with patch.dict(
        os.environ,
        {
            "YT_APP_SECRET_KEY": "test-secret",
            "YT_TOKEN_ENC_KEY": "test-enc-key",
            "YT_GOOGLE_CLIENT_ID": "test-client-id",
            "YT_GOOGLE_CLIENT_SECRET": "test-client-secret",
            "YT_GOOGLE_REDIRECT_URI": "http://localhost:8000/auth/callback",
        },
        clear=True,
    ):
        settings = Settings()

        assert settings.app_secret_key == "test-secret"
        assert settings.database_url == "sqlite+aiosqlite:///./dev.db"
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.feed_ttl_seconds == 1800
        assert settings.page_size_default == 24
        assert settings.env == "dev"


def test_settings_env_override():
    """Test that environment variables override defaults."""
    with patch.dict(
        os.environ,
        {
            "YT_APP_SECRET_KEY": "test-secret",
            "YT_TOKEN_ENC_KEY": "test-enc-key",
            "YT_GOOGLE_CLIENT_ID": "test-client-id",
            "YT_GOOGLE_CLIENT_SECRET": "test-client-secret",
            "YT_GOOGLE_REDIRECT_URI": "http://localhost:8000/auth/callback",
            "YT_DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb",
            "YT_PAGE_SIZE_DEFAULT": "50",
            "YT_ENV": "prod",
        },
        clear=True,
    ):
        settings = Settings()

        assert (
            settings.database_url == "postgresql+asyncpg://user:pass@localhost/testdb"
        )
        assert settings.page_size_default == 50
        assert settings.env == "prod"


def test_settings_validation_error():
    """Test that missing required fields raise validation error."""
    # Temporarily disable .env file loading for this test
    with patch.dict(os.environ, {}, clear=True):
        # Create a test Settings class that doesn't read from .env
        from pydantic_settings import SettingsConfigDict

        original_config = Settings.model_config
        try:
            # Override config to not read from .env file
            Settings.model_config = SettingsConfigDict(env_prefix="YT_", extra="ignore")

            with pytest.raises(ValidationError) as exc_info:
                Settings()

            errors = exc_info.value.errors()
            error_fields = {e["loc"][0] for e in errors}
            assert "app_secret_key" in error_fields
            assert "token_enc_key" in error_fields
        finally:
            # Restore original config
            Settings.model_config = original_config


def test_get_settings_singleton():
    """Test that get_settings returns the same instance."""
    with patch.dict(
        os.environ,
        {
            "YT_APP_SECRET_KEY": "test-secret",
            "YT_TOKEN_ENC_KEY": "test-enc-key",
            "YT_GOOGLE_CLIENT_ID": "test-client-id",
            "YT_GOOGLE_CLIENT_SECRET": "test-client-secret",
            "YT_GOOGLE_REDIRECT_URI": "http://localhost:8000/auth/callback",
        },
        clear=True,
    ):
        # Clear the singleton
        import app.config

        app.config._settings = None

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2
