"""Tests for configuration module."""

import os
import pytest
from pathlib import Path

from app.config import Settings, get_settings

class TestSettings:
    """Test Settings configuration."""

    def test_default_settings(self):
        """Test settings with defaults."""
        settings = Settings(
            telegram_bot_token="test_token",
            telegram_admin_id=123456
        )
        assert settings.app_env == "development"
        assert settings.server_host == "0.0.0.0"
        assert settings.server_port == 8000
        assert settings.app_debug is True

    def test_settings_from_env(self, tmp_path, monkeypatch):
        """Test settings loaded from environment variables."""
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("APP_DEBUG", "false")
        monkeypatch.setenv("SERVER_PORT", "9000")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "prod_token")

        settings = Settings(telegram_admin_id=789)
        assert settings.app_env == "production"
        assert settings.app_debug is False
        assert settings.server_port == 9000
        assert settings.telegram_bot_token == "prod_token"

    def test_log_level_validation(self, monkeypatch):
        """Test log level is valid."""
        # Ensure environment variable doesn't interfere with constructor argument
        monkeypatch.delenv("APP_LOG_LEVEL", raising=False)
        settings = Settings(
            app_log_level="DEBUG",
            telegram_bot_token="test",
            telegram_admin_id=123
        )
        assert settings.app_log_level == "DEBUG"
    
    def test_logs_directory_creation(self, tmp_path, monkeypatch):
        """Test logs directory is created."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        settings = Settings(
            telegram_bot_token="test",
            telegram_admin_id=123,
        )
        assert settings.logs_dir.exists()

    def test_database_url_default(self):
        """Test default database URL."""
        settings = Settings(
            telegram_bot_token="test",
            telegram_admin_id=123
        )
        assert "postgresql" in settings.database_url

    def test_rate_limit_configuration(self):
        """Test rate limit configuration."""
        settings = Settings(
            telegram_bot_token="test",
            telegram_admin_id=123,
            rate_limit_enabled=True,
            rate_limit_per_minute=100
        )
        assert settings.rate_limit_enabled is True
        assert settings.rate_limit_per_minute == 100

    def test_get_settings_singleton(self):
        """Test get_settings returns settings."""
        settings = get_settings()
        assert settings is not None
        assert hasattr(settings, "app_env")
        assert hasattr(settings, "telegram_bot_token")

class TestSettingsValidation:
    """Test settings validation."""

    def test_missing_telegram_token_default(self):
        """Test missing telegram token defaults to empty string."""
        settings = Settings(telegram_admin_id=123)
        assert settings.telegram_bot_token == ""

    def test_settings_with_all_params(self):
        """Test settings with all parameters."""
        settings = Settings(
            app_name="Test Bot",
            app_env="testing",
            app_debug=False,
            app_log_level="ERROR",
            server_host="127.0.0.1",
            server_port=5000,
            telegram_bot_token="test_token",
            telegram_admin_id=999,
            database_url="sqlite:///:memory:",
            sqlalchemy_echo=False,
            rate_limit_enabled=False,
            rate_limit_per_minute=30
        )
        assert settings.app_name == "Test Bot"
        assert settings.server_host == "127.0.0.1"
        assert settings.rate_limit_per_minute == 30
