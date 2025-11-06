"""Main entry point for the trading signal bot."""

import asyncio
from app.logging_config import logger
from app.config import settings
from app.database import init_db
from telegram.bot_handler import TelegramBotHandler


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
        
        # Initialize Telegram bot
        bot_handler = TelegramBotHandler()
        await bot_handler.initialize_bot()
        logger.info("Telegram bot initialized")

        from app.services import get_rate_limiter, MessageQueueService
        rate_limiter = get_rate_limiter(
            global_rate=settings.rate_limit_per_minute,
            channel_rate=30,
        )
        message_queue = MessageQueueService(max_queue_size=settings.message_queue_max_size)

        # Register message processor callback
        from app.services import MessageProcessorService
        processor = MessageProcessorService(session_factory=SessionLocal)
        message_queue.register_callback(processor.process_message)

        
        # Start queue workers
        await message_queue.start_workers()
        logger.info("Message queue workers started")
        
        # Create polling task
        polling_task = asyncio.create_task(bot_handler.start_polling())
        
        logger.info("Application running...")
        
        # Wait for polling to complete (handles Ctrl+C)
        await polling_task

        
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        if 'message_queue' in locals():
            await message_queue.stop_workers()
        logger.info("Application stopped")


if __name__ == "__main__":
    asyncio.run(main())