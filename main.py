"""Main entry point for the trading signal bot."""

import asyncio
import signal
import sys
from typing import Optional

from app.config import settings
from app.database import SessionLocal, init_db
from app.logging_config import logger
from app.services import (
    MessageProcessorService,
    MessageQueueService,
    get_rate_limiter,
)
from telegram_bot.bot_handler import TelegramBotHandler


class Application:
    """Main application manager."""

    def __init__(self):
        """Initialize application."""
        self.bot_handler: Optional[TelegramBotHandler] = None
        self.message_queue: Optional[MessageQueueService] = None
        self.message_processor: Optional[MessageProcessorService] = None
        self.rate_limiter = None

    async def initialize(self) -> None:
        """Initialize application components."""
        logger.info(f"Initializing {settings.app_name}")
        logger.info(f"Environment: {settings.app_env}")
        logger.info(f"Debug mode: {settings.app_debug}")

        try:
            # Initialize database
            logger.info("Initializing database...")
            init_db()
            logger.info("Database initialized successfully")

            # Initialize rate limiter
            logger.info("Initializing rate limiter...")
            self.rate_limiter = get_rate_limiter(
                global_rate=settings.rate_limit_per_minute,
                channel_rate=settings.rate_limit_channel,
                user_rate=settings.rate_limit_user,
            )
            logger.info("Rate limiter initialized")

            # Initialize message processor
            logger.info("Initializing message processor...")
            self.message_processor = MessageProcessorService(
                rate_limiter=self.rate_limiter,
                session_factory=SessionLocal,
            )
            logger.info("Message processor initialized")

            # Initialize message queue
            logger.info("Initializing message queue...")
            self.message_queue = MessageQueueService(
                max_queue_size=settings.message_queue_max_size,
                max_concurrent_workers=settings.max_concurrent_workers,
                worker_timeout=settings.message_queue_timeout,
            )
            # Register message processor as callback
            self.message_queue.register_callback(self.message_processor.process_message)
            logger.info("Message queue initialized with processor callback")

            # Initialize Telegram bot
            logger.info("Initializing Telegram bot...")
            self.bot_handler = TelegramBotHandler(
                message_queue=self.message_queue,
                message_processor=self.message_processor,
            )
            # Inject session factory for fallback processing
            self.bot_handler.session_factory = SessionLocal
            await self.bot_handler.initialize_bot()
            logger.info("Telegram bot initialized successfully")

            logger.info("Application initialization complete")

        except Exception as e:
            logger.error(f"Failed to initialize application: {e}", exc_info=True)
            raise

    async def run(self) -> None:
        """Run the application (main event loop)."""
        try:
            logger.info("Starting application services...")

            # Start message queue workers
            if self.message_queue:
                await self.message_queue.start_workers()
                logger.info("Message queue workers started")

            logger.info("Starting Telegram bot...")
            # Use start() instead of run_polling() to work with existing event loop
            if self.bot_handler and self.bot_handler.application:
                # Initialize the application first (CRITICAL STEP!)
                await self.bot_handler.application.initialize()
                logger.info("Telegram application initialized")
                
                await self.bot_handler.application.start()
                logger.info("Telegram bot started")
                
                # Start polling with updater
                await self.bot_handler.application.updater.start_polling(
                    allowed_updates=["message", "edited_message", "channel_post"]
                )
                logger.info("Bot polling started")
                
                # Keep running until interrupted
                try:
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    logger.info("Polling interrupted")

        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown application gracefully."""
        try:
            logger.info("Shutting down application...")

            # Stop message queue
            if self.message_queue:
                await self.message_queue.stop_workers()
                logger.info("Message queue workers stopped")

            # Stop bot
            if self.bot_handler and self.bot_handler.application:
                try:
                    await self.bot_handler.application.updater.stop_polling()
                    logger.info("Bot polling stopped")
                except Exception as e:
                    logger.warning(f"Error stopping polling: {e}")
                
                try:
                    await self.bot_handler.application.stop()
                    logger.info("Telegram bot stopped")
                except Exception as e:
                    logger.warning(f"Error stopping application: {e}")

            logger.info("Application shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)


async def main():
    """Main entry point - initialize and run the application."""
    app = Application()

    try:
        # Initialize all components
        await app.initialize()
        
        # Run the application
        await app.run()

    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        # Run the async main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)