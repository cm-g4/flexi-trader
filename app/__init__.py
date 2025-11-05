"""Telegram Trading Signal Bot - Main application package."""

from app.config import settings, get_settings
from app.logging_config import logger, setup_logging
from app.exceptions import FlexiTraderException
from app.database import Base, engine, SessionLocal, get_db, init_db

__version__ = "0.1.0"
__author__ = "Gigman2"

__all__ = [
    "settings",
    "get_settings",
    "logger",
    "setup_logging",
    "FlexiTraderException",
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
]