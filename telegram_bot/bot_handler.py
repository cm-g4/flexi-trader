"""Telegram bot message handler with channel management."""

import logging
from typing import Optional
from uuid import uuid4

# Import from python-telegram-bot library
from telegram import Update
from telegram.ext import Application, ContextTypes, ConversationHandler

from app.config import settings
from app.database import SessionLocal
from app.exceptions import ChannelError, DatabaseError, ValidationError
from app.logging_config import logger
from app.services.channel_service import ChannelService
from app.services.message_queue import MessageQueueService
from app.services.message_processor import MessageProcessorService
from app.services.message_receiver import MessageReceiverService


# Conversation states for add_channel
ADD_CHANNEL_ID = 1
ADD_CHANNEL_NAME = 2
ADD_CHANNEL_DESCRIPTION = 3
ADD_CHANNEL_PROVIDER = 4


class TelegramBotHandler:
    """
    Handles Telegram bot interactions and message reception.
    
    Responsible for:
    - Bot initialization
    - Message routing
    - Command handling
    - Channel management
    - Error handling
    """

    def __init__(
        self, 
        message_queue: MessageQueueService, 
        message_processor: MessageProcessorService,
    ):
        """Initialize the Telegram bot handlers """
        self.application: Optional[Application] = None
        self.message_queue = message_queue
        self.message_processor = message_processor
        self.session_factory = None

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

        # Create application
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

        from telegram.ext import CommandHandler, MessageHandler, filters

        # Command handlers
        self.application.add_handler(
            CommandHandler("start", self.command_start)
        )
        self.application.add_handler(
            CommandHandler("help", self.command_help)
        )
        self.application.add_handler(
            CommandHandler("channels", self.command_channels)
        )
        self.application.add_handler(
            CommandHandler("signals", self.command_signals)
        )
        
        # Add channel conversation handler
        add_channel_handler = ConversationHandler(
            entry_points=[CommandHandler("add_channel", self.command_add_channel)],
            states={
                ADD_CHANNEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_channel_get_id)],
                ADD_CHANNEL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_channel_get_name)],
                ADD_CHANNEL_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_channel_get_description)],
                ADD_CHANNEL_PROVIDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_channel_get_provider)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_add_channel)],
        )
        self.application.add_handler(add_channel_handler)

        # Message handler (must be last)
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
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
        
        Routes message to queue for processing.
        
        Args:
            update: The incoming update from Telegram
            context: The context of the message
        """
        if not update.message or not update.message.text:
            return
        
        if self.session_factory:
            session = self.session_factory()
        else:
            from app.database import SessionLocal
            session = SessionLocal()
        
        try:
            message_text = update.message.text
            chat_id = update.message.chat.id
            message_id = update.message.message_id
            sender_id = update.message.from_user.id if update.message.from_user else None


            logger.debug(
                f"Received message: chat_id={chat_id}, "
                f"message_id={message_id}, sender_id={sender_id}, "
                f"text_length={len(message_text)}"
            )

            # Get channel by chat ID
            channel = ChannelService.get_channel_by_telegram_id(
                session, telegram_channel_id=abs(chat_id)
            )

            if not channel:
                logger.warning(
                    f"Message from unknown channel: chat_id={chat_id}, "
                    f"message_id={message_id}"
                )
                return

            if not channel.is_active:
                logger.debug(
                    f"Message from inactive channel: channel={channel.id}, "
                    f"skipping..."
                )
                return

            # Receive message (checks for duplicates)
            message = MessageReceiverService.receive_message(
                session=session,
                channel_id=str(channel.id),
                telegram_message_id=message_id,
                telegram_chat_id=chat_id,
                text=message_text,
                telegram_sender_id=sender_id,
                raw_data={
                    "chat_type": update.message.chat.type if update.message.chat else None,
                    "message_type": update.message.type if update.message else None,
                },
            )

            if message is None:
                logger.debug(f"Duplicate message skipped: id={message_id}")
                session.commit()
                return

            session.commit()

            logger.info(
                f"Message received and stored: id={message.id}, "
                f"channel_id={channel.id}"
            )
            
            # Queue message for processing if queue available
            if self.message_queue:
                try:
                    import asyncio
                    await self.message_queue.enqueue_message(message)
                    logger.debug(
                        f"Message queued: id={message.id}, "
                        f"queue_size={self.message_queue.get_queue_size()}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to queue message: id={message.id}, error={e}",
                        exc_info=True
                    )
            else:
                # Fallback: process directly if no queue
                if self.message_processor:
                    try:
                        success = self.message_processor.process_message(message)
                        if success:
                            logger.info(f"Message processed directly: id={message.id}")
                        else:
                            logger.warning(f"Failed to process message: id={message.id}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
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
            "/add_channel - Add a new channel\n"
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
            "• /add_channel - Add a new trading signal channel\n"
            "• /signals - Show recent trading signals\n"
            "• /help - Show this help message\n\n"
            "Features:\n"
            "• Monitor multiple Telegram channels\n"
            "• Automatic signal extraction\n"
            "• Centralized signal dashboard\n"
            "• Performance tracking\n\n"
            "To add a channel:\n"
            "1. /add_channel\n"
            "2. Follow the prompts\n"
            "3. Provide: Channel ID, Name, Description, Provider\n\n"
            "Need help? Contact support!"
        )

        await update.message.reply_text(help_text)
        logger.info(f"Help command from user: {update.effective_user.id}")

    async def command_add_channel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle /add_channel command - start channel addition process.
        
        Args:
            update: Telegram update object
            context: Callback context
            
        Returns:
            Next conversation state
        """
        if not update.message:
            return ConversationHandler.END

        help_text = (
            "📝 Add New Channel\n\n"
            "I'll guide you through adding a trading signal channel.\n\n"
            "Step 1️⃣: What is the Telegram Channel ID?\n"
            "(To find it, use @username_to_id_bot or check channel details)\n\n"
            "Type /cancel to stop."
        )

        await update.message.reply_text(help_text)
        logger.info(f"Add channel started by user: {update.effective_user.id}")
        
        return ADD_CHANNEL_ID

    async def add_channel_get_id(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Get channel ID from user."""
        if not update.message or not update.message.text:
            return ADD_CHANNEL_ID

        try:
            channel_id = int(update.message.text.strip())
            
            # For private channels, Telegram uses negative IDs starting with -100
            # Convert if needed
            if channel_id > 0:
                channel_id = -100 * 1000000 - channel_id if channel_id < 1000000000 else -channel_id
            
            context.user_data["channel_id"] = channel_id
            
            await update.message.reply_text(
                "✅ Got it!\n\n"
                "Step 2️⃣: What is the channel name?\n"
                "(e.g., 'Gold Trading Signals', 'Forex Daily')"
            )
            
            return ADD_CHANNEL_NAME
            
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid channel ID. Please enter a valid number.\n\n"
                "Type the Telegram Channel ID:"
            )
            return ADD_CHANNEL_ID

    async def add_channel_get_name(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Get channel name from user."""
        if not update.message or not update.message.text:
            return ADD_CHANNEL_NAME

        name = update.message.text.strip()
        
        if not name or len(name) < 3:
            await update.message.reply_text(
                "❌ Channel name too short. Please use at least 3 characters."
            )
            return ADD_CHANNEL_NAME
        
        context.user_data["name"] = name
        
        await update.message.reply_text(
            "✅ Got it!\n\n"
            "Step 3️⃣: Channel description (optional)\n"
            "(e.g., 'Daily gold signals, high accuracy')\n\n"
            "Type /skip to skip this step."
        )
        
        return ADD_CHANNEL_DESCRIPTION

    async def add_channel_get_description(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Get channel description from user."""
        if not update.message or not update.message.text:
            return ADD_CHANNEL_DESCRIPTION

        text = update.message.text.strip()
        
        if text.lower() == "/skip":
            context.user_data["description"] = None
        else:
            context.user_data["description"] = text
        
        await update.message.reply_text(
            "✅ Got it!\n\n"
            "Step 4️⃣: Provider name (who provides these signals?)\n"
            "(e.g., 'John Trading', 'Signal Masters')\n\n"
            "Type /skip to use default."
        )
        
        return ADD_CHANNEL_PROVIDER

    async def add_channel_get_provider(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Get provider name and create channel."""
        if not update.message or not update.message.text:
            return ADD_CHANNEL_PROVIDER

        text = update.message.text.strip()
        
        if text.lower() == "/skip":
            provider_name = "Unknown Provider"
        else:
            provider_name = text
        
        context.user_data["provider_name"] = provider_name
        
        # Now create the channel in database
        session = SessionLocal()
        try:
            user_id = str(update.effective_user.id)
            
            print(context.user_data)
            channel = ChannelService.create_channel(
                session=session,
                telegram_channel_id=context.user_data["channel_id"],
                telegram_chat_id=context.user_data["channel_id"],  # Same for channels
                name=context.user_data["name"],
                user_id=user_id,
                description=context.user_data.get("description"),
                provider_name=provider_name,
            )
            
            session.commit()
            
            success_text = (
                f"✅ Channel Added Successfully!\n\n"
                f"📺 Channel: {channel.name}\n"
                f"👤 Provider: {provider_name}\n"
                f"🆔 ID: {channel.id}\n\n"
                f"The bot is now monitoring this channel for trading signals.\n\n"
                f"Use /channels to see all your channels."
            )
            
            await update.message.reply_text(success_text)
            logger.info(f"Channel created: {channel.id} by user {user_id}")
            
        except ValidationError as e:
            await update.message.reply_text(
                f"❌ Validation Error:\n{e.message}\n\n"
                "Please try again with /add_channel"
            )
            logger.warning(f"Validation error: {e.message}")
            
        except ChannelError as e:
            await update.message.reply_text(
                f"❌ Error:\n{e.message}\n\n"
                "This channel might already be registered."
            )
            logger.warning(f"Channel error: {e.message}")
            
        except Exception as e:
            await update.message.reply_text(
                "❌ Error adding channel. Please try again."
            )
            logger.error(f"Error creating channel: {e}", exc_info=True)
            
        finally:
            session.close()
        
        # Clear user data
        context.user_data.clear()
        
        return ConversationHandler.END

    async def cancel_add_channel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle /cancel command in add_channel conversation."""
        if not update.message:
            return ConversationHandler.END

        await update.message.reply_text(
            "❌ Cancelled.\n\n"
            "To add a channel later, use /add_channel"
        )
        
        context.user_data.clear()
        logger.info(f"Add channel cancelled by user: {update.effective_user.id}")
        
        return ConversationHandler.END

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
            user_id = str(update.effective_user.id)
            
            # Get all active channels for this user
            channels = ChannelService.get_all_channels(session, user_id=user_id)

            if not channels:
                await update.message.reply_text(
                    "📭 No channels connected yet.\n\n"
                    "Use /add_channel to start monitoring signals!"
                )
                return
            
            # Format channel list
            channel_list = "📡 Your Connected Channels:\n\n"
            for i, channel in enumerate(channels, 1):
                status_emoji = "✅" if channel.is_active else "⛔"
                channel_list += (
                    f"{status_emoji} {i}. {channel.name}\n"
                    f"   👤 Provider: {channel.provider_name or 'Unknown'}\n"
                    f"   📊 Signals: {channel.signal_count}\n"
                    f"   📅 Added: {channel.created_at.strftime('%Y-%m-%d')}\n\n"
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
            user_id = str(update.effective_user.id)
            
            # Get all channels for this user
            channels = ChannelService.get_all_channels(session, user_id=user_id)

            if not channels:
                await update.message.reply_text("📭 No channels connected yet.")
                return

            # Count total signals
            total_signals = sum(channel.signal_count for channel in channels)

            signals_text = f"📊 Signal Summary:\n\n"
            signals_text += f"Total Signals: {total_signals}\n"
            signals_text += f"Active Channels: {len([c for c in channels if c.is_active])}\n\n"

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

    async def stop_bot(self) -> None:
        """Stop the bot gracefully."""
        if self.application:
            try:
                await self.application.stop()
                logger.info("Telegram bot stopped")
            except RuntimeError as e:
                if "not running" in str(e).lower():
                    logger.info("Bot already stopped")
                else:
                    logger.error(f"Error stopping bot: {e}")

__all__ = ["TelegramBotHandler"]