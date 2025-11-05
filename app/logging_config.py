"""Logging setup for flexi trader application"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from app.config import settings


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
    use_json: bool = False,
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        use_json: Use JSON formatting (optional)

    Returns:
        configured logger instance
    """

    level = level or settings.app_log_level
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger("flexi_trader")
    logger.setLevel(log_level)
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is None:
        log_file = settings.logs_dir / "bot.log"

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        logger.error(f"Could not create log file {log_file}: {e}")

    return logger


logger = setup_logging()

__all__ = ["setup_logging", "logger"]
