"""Tests for configuration module."""

from app.config import Settings, get_settings


class TestSettings:
    """Test Settings configuration."""

    def test_default_settings(self):
        """Test settings with defaults."""
        settings = Settings(
            telegram_bot_token="test_token",
            telegram_admin_id=123456,
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

    def test_log_level_valid_values(self):
        """Test log level has valid value."""
        settings = Settings(telegram_bot_token="test", telegram_admin_id=123)
        # Should have some valid log level
        assert settings.app_log_level in [
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ]

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
        settings = Settings(telegram_bot_token="test", telegram_admin_id=123)
        assert "postgresql" in settings.database_url

    def test_rate_limit_default(self):
        """Test rate limit has reasonable default."""
        settings = Settings(telegram_bot_token="test", telegram_admin_id=123)
        assert settings.rate_limit_enabled is True
        assert settings.rate_limit_per_minute >= 10

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
