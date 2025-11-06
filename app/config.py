"""Configuration management for the trading signal bot application."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Telegram Trading Signal Bot"
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_debug: bool = Field(default=True, validation_alias="APP_DEBUG")
    app_log_level: str = Field(
        default="INFO", validation_alias="APP_LOG_LEVEL",
    )

    # Server
    server_host: str = Field(default="0.0.0.0", validation_alias="SERVER_HOST")
    server_port: int = Field(default=8000, validation_alias="SERVER_PORT")

    # Telegram
    telegram_bot_token: str = Field(
        default="", validation_alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_admin_id: Optional[int] = Field(
        default=None, validation_alias="TELEGRAM_ADMIN_ID"
    )

    # Database
    db: str = "postgresql://user:password@localhost:5432/flexitrader_db"
    database_url: str = Field(
        default=db,
        validation_alias="DATABASE_URL",
    )
    sqlalchemy_echo: bool = Field(
        default=False, validation_alias="SQLALCHEMY_ECHO"
    )

    # Rate Limiting
    rate_limit_enabled: bool = Field(
        default=True, validation_alias="RATE_LIMIT_ENABLED"
    )
    rate_limit_per_minute: int = Field(
        default=60, validation_alias="RATE_LIMIT_PER_MINUTE"
    )

    # Paths
    project_root: Path = Path(__file__).parent.parent
    logs_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "logs"
    )

    # Message Queue Configuration
    message_queue_max_size: int = Field(
        default=1000, 
        validation_alias="MESSAGE_QUEUE_MAX_SIZE"
    )
    message_queue_timeout: int = Field(
        default=30,
        validation_alias="MESSAGE_QUEUE_TIMEOUT"
    )
    max_concurrent_workers: int = Field(
        default=5,
        validation_alias="MAX_CONCURRENT_WORKERS"
    )

    # Rate Limiting Configuration  
    rate_limit_channel: int = Field(
        default=30,
        validation_alias="RATE_LIMIT_CHANNEL"
    )
    rate_limit_user: int = Field(
        default=100,
        validation_alias="RATE_LIMIT_USER"
    )


    class Config:
        # Load .env.test during testing, .env otherwise
        if os.getenv("PYTEST_RUNNING"):
            env_file = ".env.test"
        else:
            env_file = ".env"
        case_sensitive = False
        extra = "allow"

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure logs directory exists
        self.logs_dir.mkdir(exist_ok=True, parents=True)


def get_settings() -> Settings:
    """Get the application settings singleton."""
    return Settings()


settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
