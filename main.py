"""Main entry point for the trading signal bot."""

import asyncio
from app.logging_config import logger
from app.config import settings
from app.database import init_db


async def main():
    """Initialize and run the application."""
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug mode: {settings.app_debug}")
    
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully")
        
        # More initialization to be added in future sprints
        # - Telegram bot setup (Sprint 2)
        # - Template system (Sprint 3)
        # - FastAPI app (Sprint 6)
        
        logger.info("Application initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())