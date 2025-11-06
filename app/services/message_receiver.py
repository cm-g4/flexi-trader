"""Message receiver service for Telegram message handling."""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.exceptions import ChannelError, DatabaseError
from app.logging_config import logger
from app.models.channel import Channel
from app.models.message import Message
from app.services.duplicate_detection import DuplicateDetectionService

class MessageReceiverService:
    """
    Service for receiving and storing Telegram messages.
    
    Handles:
    - Message storage from Telegram
    - Deduplication
    - Metadata capture
    - Error handling
    """

    @staticmethod
    def receive_message(
        session: Session,
        channel_id: str,
        telegram_message_id: int,
        telegram_chat_id: int,
        text: str,
        telegram_sender_id: Optional[int] = None,
        raw_data: Optional[dict] = None,
    ) -> Optional[Message]:
        """
        Receive and store a message from Telegram.
        
        Args:
            session: Database session
            channel_id: Channel identifier (internal)
            telegram_message_id: Telegram message ID
            telegram_chat_id: Telegram chat ID
            text: Message text
            telegram_sender_id: Sender ID (optional)
            raw_data: Additional metadata as JSON (optional)
        
        Returns:
            Stored Message object if successful, None if duplicate
        
        Raises:
            ChannelError: If channel not found
            DatabaseError: If storage fails
        """
        try:
            # Verify channel exists
            channel = session.query(Channel).filter_by(id=channel_id).first()
            if not channel:
                raise ChannelError(f"Channel not found: {channel_id}")
            
            # Check for duplicate
            if DuplicateDetectionService.is_duplicate_message(
                session, channel_id, telegram_message_id
            ):
                logger.debug(
                    f"Duplicate message skipped: channel={channel_id}, "
                    f"telegram_id={telegram_message_id}"
                )
                return None

            # Create message record
            message = Message(
                id=MessageReceiverService._generate_message_id(),
                channel_id=channel_id,
                telegram_message_id=telegram_message_id,
                telegram_chat_id=telegram_chat_id,
                telegram_sender_id=telegram_sender_id,
                text=text,
                raw_data=raw_data or {},
            )

            session.add(message)
            session.flush()  # Get the ID before commit

            logger.debug(
                f"Message received: id={message.id}, "
                f"channel={channel_id}, "
                f"telegram_id={telegram_message_id}, "
                f"text_length={len(text)}"
            )

            return message

        except ChannelError:
            raise
        except Exception as e:
            logger.error(f"Failed to receive message: {e}")
            raise DatabaseError(f"Failed to store message: {e}")

    @staticmethod
    def mark_message_processed(
        session: Session,
        message_id: str,
        is_signal: bool = False,
    ) -> Message:
        """
        Mark a message as processed.
        
        Args:
            session: Database session
            message_id: Message ID
            is_signal: Whether message contains a trading signal
        
        Returns:
            Updated Message object
        
        Raises:
            DatabaseError: If update fails
        """
        try:
            message = session.query(Message).filter_by(id=message_id).first()
            if not message:
                raise DatabaseError(f"Message not found: {message_id}")

            if is_signal:
                message.mark_as_signal()

            message.mark_as_processed()
            session.add(message)
            session.flush()

            logger.debug(
                f"Message marked processed: id={message_id}, "
                f"is_signal={is_signal}"
            )

            return message

        except Exception as e:
            logger.error(f"Failed to mark message processed: {e}")
            raise DatabaseError(f"Failed to update message: {e}")
    
    @staticmethod
    def record_extraction_attempt(
        session: Session,
        message_id: str,
        success: bool = False,
    ) -> Message:
        """
        Record an extraction attempt on a message.
        
        Args:
            session: Database session
            message_id: Message ID
            success: Whether extraction was successful
        
        Returns:
            Updated Message object
        
        Raises:
            DatabaseError: If update fails
        """
        try:
            message = session.query(Message).filter_by(id=message_id).first()
            if not message:
                raise DatabaseError(f"Message not found: {message_id}")

            message.increment_extraction_attempts()
            if success:
                message.mark_as_signal()
                message.mark_as_processed()

            session.add(message)
            session.flush()

            logger.debug(
                f"Extraction attempt recorded: id={message_id}, "
                f"success={success}, attempts={message.extraction_attempts}"
            )

            return message

        except Exception as e:
            logger.error(f"Failed to record extraction attempt: {e}")
            raise DatabaseError(f"Failed to update message: {e}")
    
    @staticmethod
    def get_unprocessed_messages(
        session: Session,
        channel_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[Message]:
        """
        Get unprocessed messages for extraction.
        
        Args:
            session: Database session
            channel_id: Filter by channel (optional)
            limit: Maximum number of messages to return
        
        Returns:
            List of unprocessed Message objects
        """
        query = session.query(Message).filter(Message.processed == False)

        if channel_id:
            query = query.filter(Message.channel_id == channel_id)

        messages = query.order_by(Message.created_at).limit(limit).all()
        return messages

    @staticmethod
    def get_recent_messages(
        session: Session,
        channel_id: str,
        limit: int = 50,
    ) -> list[Message]:
        """
        Get recent messages from a channel.
        
        Args:
            session: Database session
            channel_id: Channel identifier
            limit: Maximum number of messages
        
        Returns:
            List of recent Message objects
        """
        messages = (
            session.query(Message)
            .filter(Message.channel_id == channel_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        return messages
    
    @staticmethod
    def _generate_message_id() -> str:
        """
        Generate unique message ID.
        
        Returns:
            UUID string
        """
        import uuid

        return str(uuid.uuid4())

__all__ = ["MessageReceiverService"]








