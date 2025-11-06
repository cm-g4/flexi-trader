"""Duplicate detection service for messages and signals."""


from datetime import datetime, timedelta, timezone
from token import OP
from typing import Optional

from sqlalchemy.orm import Session

from app.exceptions import DuplicateSignalError
from app.logging_config import logger
from app.models import Message


class DuplicateDetectionService:
    """Service for detecting duplicate messages."""

    # Lookback window for duplication detection (hours)
    LOOKBACK_HOURS = 24

    @staticmethod
    def is_duplicate_message(
        session: Session,
        channel_id: str,
        telegram_message_id: int,
        lookback_hours: Optional[int] = None,
    ) -> bool:
        """
        Check if a message has already been received.
        
        Uses telegram_message_id for exact duplicate detection, as each
        message in Telegram has a unique ID within a chat.
        
        Args:
            session: Database session
            channel_id: Channel identifier
            telegram_message_id: Telegram's message ID
            lookback_hours: Hours to look back (default: LOOKBACK_HOURS)
        
        Returns:
            True if duplicate found, False otherwise
        """
        lookback_hours = lookback_hours or DuplicateDetectionService.LOOKBACK_HOURS
        lookback_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        existing_message = (
            session.query(Message)
            .filter(
                Message.channel_id == channel_id,
                Message.telegram_message_id == telegram_message_id,
                Message.created_at >= lookback_time,
            )
            .first()
        )

        is_duplicate = existing_message is not None
        if is_duplicate:
            logger.warning(
                f"Duplicate message detected: channel_id={channel_id}, "
                f"telegram_message_id={telegram_message_id}, "
                f"created_at={existing_message.created_at}"
            )

        return is_duplicate


    @staticmethod
    def is_similar_message(
        session: Session,
        channel_id: str,
        message_text: str,
        lookback_hours: Optional[int] = None,
        similarity_threshold: float = 0.95,
    ) -> Optional[Message]:
        """
        Check for similar messages using text similarity.
        
        Useful for detecting near-duplicates that might have minor changes
        but represent the same signal.
        
        Args:
            session: Database session
            channel_id: Channel identifier
            message_text: New message text
            lookback_hours: Hours to look back
            similarity_threshold: Similarity threshold (0-1)
        
        Returns:
            Similar message if found, None otherwise
        """
        lookback_hours = lookback_hours or DuplicateDetectionService.LOOKBACK_HOURS
        lookback_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        recent_messages = (
            session.query(Message)
            .filter(
                Message.channel_id == channel_id,
                Message.created_at >= lookback_time,
            )
            .order_by(Message.created_at.desc())
            .limit(100)  # Check last 100 messages for performance
            .all()
        )

        for existing_msg in recent_messages:
            similarity = DuplicateDetectionService._calculate_similarity(
                message_text, existing_msg.text
            )
            if similarity >= similarity_threshold:
                logger.debug(
                    f"Similar message detected: similarity={similarity:.2%}, "
                    f"message_id={existing_msg.telegram_message_id}"
                )
                return existing_msg

        return None


    @staticmethod
    def _calculate_similarity(text1: str, text2: str) -> float:
        """
        Calculate text similarity using simple ratio.
        
        Args:
            text1: First text
            text2: Second text
        
        Returns:
            Similarity ratio (0-1)
        """

        from difflib import SequenceMatcher

        text1 = text1.lower().strip()
        text2 = text2.lower().strip()

        # Quick exact match
        if text1 == text2:
            return 1.0

        # Use sequence matcher
        matcher = SequenceMatcher(None, text1, text2)
        return matcher.ratio()

    @staticmethod
    def cleanup_old_duplicates(
        session: Session, days_to_keep: int = 30
    ) -> int:
        """
        Clean up old messages for storage optimization.
        
        Keeps messages that are signals or recent, deletes old non-signal messages.
        
        Args:
            session: Database session
            days_to_keep: Days of history to keep
        
        Returns:
            Number of messages deleted
        
        Note:
            Only deletes messages that are NOT signals to preserve signal history.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        deleted_count = (
            session.query(Message)
            .filter(
                Message.created_at < cutoff_date,
                Message.is_signal == False,  # Don't delete signal messages
            )
            .delete()
        )

        session.commit()
        logger.info(f"Deleted {deleted_count} old non-signal messages")
        return deleted_count

    @staticmethod
    def is_duplicate(
        session: Session,
        message: Message,
        channel_id: str,
        lookback_hours: Optional[int] = None,
        similarity_threshold: float = 0.95,
    ) -> bool:
        """
        Check if a message is a duplicate based on text similarity.
        
        Checks both exact matches (by telegram_message_id) and similar messages
        (by text content). Excludes the message being checked if it has an ID.
        
        Args:
            session: Database session
            message: Message object to check
            channel_id: Channel identifier
            lookback_hours: Hours to look back (default: LOOKBACK_HOURS)
            similarity_threshold: Similarity threshold for fuzzy matching (0-1)
        
        Returns:
            True if duplicate found, False otherwise
        """
        lookback_hours = lookback_hours or DuplicateDetectionService.LOOKBACK_HOURS
        lookback_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        # Check for exact duplicate by telegram_message_id, excluding this message
        query = session.query(Message).filter(
            Message.channel_id == channel_id,
            Message.telegram_message_id == message.telegram_message_id,
            Message.created_at >= lookback_time,
        )
        # Exclude the message being checked if it has an ID
        if message.id:
            query = query.filter(Message.id != message.id)
        
        existing_message = query.first()
        if existing_message:
            return True
        
        # Then check for similar text content, excluding this message
        if message.text:
            recent_messages = (
                session.query(Message)
                .filter(
                    Message.channel_id == channel_id,
                    Message.created_at >= lookback_time,
                )
            )
            # Exclude the message being checked if it has an ID
            if message.id:
                recent_messages = recent_messages.filter(Message.id != message.id)
            
            recent_messages = (
                recent_messages
                .order_by(Message.created_at.desc())
                .limit(100)
                .all()
            )
            
            for existing_msg in recent_messages:
                if existing_msg.text:
                    similarity = DuplicateDetectionService._calculate_similarity(
                        message.text, existing_msg.text
                    )
                    if similarity >= similarity_threshold:
                        return True
        
        return False

    @staticmethod
    def detect_or_raise(
        session: Session,
        message: Message,
        channel_id: str,
        lookback_hours: Optional[int] = None,
        similarity_threshold: float = 0.95,
    ) -> None:
        """
        Detect duplicate and raise exception if found.
        
        Args:
            session: Database session
            message: Message object to check
            channel_id: Channel identifier
            lookback_hours: Hours to look back (default: LOOKBACK_HOURS)
            similarity_threshold: Similarity threshold for fuzzy matching (0-1)
        
        Raises:
            DuplicateSignalError: If duplicate is detected
        """
        if DuplicateDetectionService.is_duplicate(
            session, message, channel_id, lookback_hours, similarity_threshold
        ):
            raise DuplicateSignalError(
                f"Duplicate message detected: channel_id={channel_id}, "
                f"telegram_message_id={message.telegram_message_id}"
            )

__all__ = ["DuplicateDetectionService"]