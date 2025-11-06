"""Telegram bot message handler."""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, ContextTypes

from app.config import settings
from app.database import SessionLocal
from app.exceptions import ChannelError, DatabaseError
from app.logging_config import logger
from app.services.channel_service import ChannelService
from app.services.message_receiver import MessageReceiverService

class TelegramBotHandler:
    """
    Handles Telegram bot interactions and message reception.
    
    Responsible for:
    - Bot initialization
    - Message routing
    - Command handling
    - Error handling
    """

    def __init__(self):
        """Initialize the Telegram bot handlers """
        self.application: Optional[Application] = None

    async def initialize_bot(self) -> None:
        """
        Initialize the Telegram bot application.
        
        Raises:
            ValueError: If bot token is not configured
        """
        if not settings.telegram_bot_token:
            raise ValueError(
                "Telegram bot token is not configured. Please set the "
                "TELEGRAM_BOT_TOKEN environment variable."
            )
        
        logger.info("Initializing Telegram bot...")

        #Create application
        self.application = Application.builder().token(
            settings.telegram_bot_token
        ).build()

        # Add handlers
        self._setup_handlers()

        logger.info("Telegram bot initialized successfully")

    def _setup_handlers(self) -> None:
        """Set up bot handlers for commands and messages."""
        if not self.application:
            raise RuntimeError("Application not initialized")

        # Command handlers
        self.application.add_handler(
            __import__("telegram.ext", fromlist=["CommandHandler"]).CommandHandler(
                "start", self.command_start
            )
        )
        self.application.add_handler(
            __import__("telegram.ext", fromlist=["CommandHandler"]).CommandHandler(
                "help", self.command_help
            )
        )
        self.application.add_handler(
            __import__("telegram.ext", fromlist=["CommandHandler"]).CommandHandler(
                "channels", self.command_channels
            )
        )
        self.application.add_handler(
            __import__("telegram.ext", fromlist=["CommandHandler"]).CommandHandler(
                "signals", self.command_signals
            )
        )

        # Message handler (must be last)
        self.application.add_handler(
            __import__("telegram.ext", fromlist=["MessageHandler"]).MessageHandler(
                __import__("telegram.ext", fromlist=["filters"]).filters.TEXT 
                & ~__import__("telegram.ext", fromlist=["filters"]).filters.COMMAND,
                self.handle_message
            )
        )

        logger.debug("Telegram bot handlers setup completed")


    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming messages from Telegram.
        
        Args:
            update: The incoming update from Telegram
            context: The context of the message
        """
        if not update.message or not update.message.text:
            return
        
        session = SessionLocal()
        try:
            message_text = update.message.text
            chat_id = update.message.chat_id
            message_id = update.message.message_id
            sender_id = update.message.from_user.id if update.message.from_user else None

            logger.debug(
                f"Received message: chat_id={chat_id}, "
                f"message_id={message_id}, sender_id={sender_id}"
                f"length={len(message_text)}"
            )

            # Get channel by chat ID
            channel = ChannelService.get_channel_by_telegram_id(
                session, telegram_channel_id=abs(chat_id)
            )

            if not channel:
                logger.warning(
                    f"Message from unknown channel: chat_id={chat_id}"
                )
                return

            if not channel.is_active:
                logger.warning(
                    f"Message from inactive channel: channel={channel.id}, "
                    f"skipping..."
                )
                return

            message = MessageReceiverService.receive_message(
                session=session,
                channel_id=channel.id,
                telegram_message_id=message_id,
                telegram_chat_id=chat_id,
                text=message_text,
                telegram_sender_id=sender_id,
                raw_data={
                    "chat_type": update.message.chat.type if update.message.chat else None,
                    "message_type": update.message.type if update.message else None,
                },
            )

            if message:
                logger.info(
                    f"Message stored: id={message.id}, "
                    f"channel_id={channel.id}"
                )
                session.commit()
            else:
                session.rollback()

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            session.rollback()
        finally:
            session.close()


    async def command_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /start command.
        
        Args:
            update: Telegram update object
            context: Callback context
        """
        if not update.message:
            return

        welcome_text = (
            "👋 Welcome to FlexiTrader Telegram Bot!\n\n"
            "I help you monitor and organize trading signals from multiple "
            "Telegram channels.\n\n"
            "Available commands:\n"
            "/channels - List your channels\n"
            "/signals - View recent signals\n"
            "/help - Show detailed help\n"
        )

        await update.message.reply_text(welcome_text)
        logger.info(
            f"Start command from user: {update.effective_user.id}"
        )

    async def command_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /help command.
        
        Args:
            update: Telegram update object
            context: Callback context
        """
        if not update.message:
            return
        
        help_text = (
            "📖 Help - FlexiTrader Telegram Bot\n\n"
            "Commands:\n"
            "• /start - Show welcome message\n"
            "• /channels - List all your connected channels\n"
            "• /signals - Show recent trading signals\n"
            "• /help - Show this help message\n\n"
            "Features:\n"
            "• Monitor multiple Telegram channels\n"
            "• Automatic signal extraction\n"
            "• Centralized signal dashboard\n"
            "• Performance tracking\n\n"
            "Need help? Contact support!"
        )

        await update.message.reply_text(help_text)
        logger.info(f"Help command from user: {update.effective_user.id}")

    async def command_channels(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /channels command - list connected channels.
        
        Args:
            update: Telegram update object
            context: Callback context
        """
        if not update.message:
            return

        session = SessionLocal()
        try:
            # Get all active channels
            channels = ChannelService.get_active_channels(session)

            if not channels:
                await update.message.reply_text(
                    "📭 No channels connected yet.\n\n"
                    "Add a channel to start monitoring signals!"
                )
                return
            
            # Format channel list
            channel_list = "📡 Connected Channels:\n\n"
            for channel in channels:
                status_emoji = "✅" if channel.is_active else "⛔"
                channel_list += (
                    f"{status_emoji} {channel.name}\n"
                    f"   Provider: {channel.provider_name or 'Unknown'}\n"
                    f"   Signals: {channel.signal_count}\n"
                    f"   Added: {channel.created_at.strftime('%Y-%m-%d')}\n\n"
                )

            await update.message.reply_text(channel_list)
            logger.info(
                f"Channels command: user={update.effective_user.id}, "
                f"count={len(channels)}"
            )

        except Exception as e:
            logger.error(f"Error in channels command: {e}")
            await update.message.reply_text(
                "❌ Error retrieving channels. Please try again."
            )
        finally:
            session.close()

    async def command_signals(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /signals command - list recent signals.
        
        Args:
            update: Telegram update object
            context: Callback context
        """
        if not update.message:
            return

        session = SessionLocal()
        try:
            # Get all channels
            channels = ChannelService.get_active_channels(session)

            if not channels:
                await update.message.reply_text("📭 No channels connected yet.")
                return

            # Count total signals
            total_signals = sum(channel.signal_count for channel in channels)

            signals_text = f"📊 Signal Summary:\n\n"
            signals_text += f"Total Signals: {total_signals}\n"
            signals_text += f"Active Channels: {len(channels)}\n\n"

            for channel in channels[:5]:  # Show top 5
                signals_text += (
                    f"• {channel.name}: {channel.signal_count} signals\n"
                )

            if len(channels) > 5:
                signals_text += f"... and {len(channels) - 5} more channels\n"

            await update.message.reply_text(signals_text)
            logger.info(f"Signals command: user={update.effective_user.id}")

        except Exception as e:
            logger.error(f"Error in signals command: {e}")
            await update.message.reply_text(
                "❌ Error retrieving signals. Please try again."
            )
        finally:
            session.close()

    async def start_polling(self) -> None:
        """
        Start the bot in polling mode.
        
        Raises:
            RuntimeError: If bot not initialized
        """
        if not self.application:
            raise RuntimeError("Bot not initialized. Call initialize_bot() first.")

        logger.info("Starting Telegram bot polling...")
        await self.application.run_polling()

    async def stop_bot(self) -> None:
        """Stop the bot gracefully."""
        if self.application:
            await self.application.stop()
            logger.info("Telegram bot stopped")

__all__ = ["TelegramBotHandler"]