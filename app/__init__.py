"""Telegram Trading Signal Bot - Main application package."""

from app.config import get_settings, settings
from app.database import Base, SessionLocal, engine, get_db, init_db
from app.exceptions import FlexiTraderException
from app.logging_config import logger, setup_logging

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
