"""Duplicate detection service for identifying duplicate trading signals."""

from typing import Optional, Tuple
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import Message, Signal
from app.exceptions import DuplicateSignalError


class DuplicateDetectionService:
    """
    Detects duplicate signals to prevent storing the same signal multiple times.
    
    Strategies:
    1. Exact message ID match (fastest)
    2. Text similarity with fuzzy matching (handles minor variations)
    3. Signal data matching (entry price, SL, symbol within time window)
    """

    def __init__(
        self,
        similarity_threshold: float = 0.90,
        lookback_hours: int = 24,
    ):
        """
        Initialize duplicate detection service.

        Args:
            similarity_threshold: Similarity threshold for fuzzy matching (0-1)
            lookback_hours: How many hours back to look for duplicates
        """
        self.similarity_threshold = similarity_threshold
        self.lookback_hours = lookback_hours

    def is_duplicate(
        self,
        session: Session,
        message: Message,
        channel_id: UUID,
        lookback_hours: Optional[int] = None,
    ) -> bool:
        """
        Check if a message is a duplicate of a recently processed message.

        Args:
            session: Database session
            message: Message to check
            channel_id: Channel ID
            lookback_hours: How many hours back to look (uses default if None)

        Returns:
            True if duplicate detected, False otherwise
        """
        lookback = lookback_hours or self.lookback_hours

        # Strategy 1: Exact match by telegram_message_id
        if self._check_exact_message_id_match(session, message, channel_id):
            return True

        # Strategy 2: Fuzzy text similarity
        if self._check_fuzzy_text_match(
            session, message, channel_id, lookback
        ):
            return True

        # Strategy 3: Check for signal data duplicates
        if self._check_signal_data_match(
            session, message, channel_id, lookback
        ):
            return True

        return False

    def detect_or_raise(
        self,
        session: Session,
        message: Message,
        channel_id: UUID,
    ) -> None:
        """
        Check for duplicates and raise error if found.

        Args:
            session: Database session
            message: Message to check
            channel_id: Channel ID

        Raises:
            DuplicateSignalError: If duplicate detected
        """
        if self.is_duplicate(session, message, channel_id):
            error_msg = (
                f"Duplicate signal detected for message "
                f"{message.telegram_message_id} in channel {channel_id}"
            )
            logger.warning(error_msg)
            raise DuplicateSignalError(error_msg)

    def _check_exact_message_id_match(
        self,
        session: Session,
        message: Message,
        channel_id: UUID,
    ) -> bool:
        """
        Check if exact message ID already exists.

        Args:
            session: Database session
            message: Message to check
            channel_id: Channel ID

        Returns:
            True if exact match found
        """
        existing = (
            session.query(Message)
            .filter(
                Message.channel_id == channel_id,
                Message.telegram_message_id == message.telegram_message_id,
                Message.id != message.id,  # Exclude self
            )
            .first()
        )

        if existing:
            logger.debug(
                f"Exact message ID match found: "
                f"{message.telegram_message_id}"
            )
            return True

        return False

    def _check_fuzzy_text_match(
        self,
        session: Session,
        message: Message,
        channel_id: UUID,
        lookback_hours: int,
    ) -> bool:
        """
        Check for similar messages using text similarity.

        Args:
            session: Database session
            message: Message to check
            channel_id: Channel ID
            lookback_hours: How many hours back to look

        Returns:
            True if similar message found
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        # Get recent messages from same channel
        recent_messages = (
            session.query(Message)
            .filter(
                Message.channel_id == channel_id,
                Message.created_at >= cutoff_time,
                Message.id != message.id,  # Exclude self
            )
            .all()
        )

        for existing_msg in recent_messages:
            similarity = self._calculate_similarity(message.text, existing_msg.text)

            if similarity >= self.similarity_threshold:
                logger.debug(
                    f"Fuzzy match found with similarity {similarity:.2f}: "
                    f"{message.telegram_message_id}"
                )
                return True

        return False

    def _check_signal_data_match(
        self,
        session: Session,
        message: Message,
        channel_id: UUID,
        lookback_hours: int,
    ) -> bool:
        """
        Check for duplicate signal data (same symbol, entry, SL).

        Args:
            session: Database session
            message: Message to check
            channel_id: Channel ID
            lookback_hours: How many hours back to look

        Returns:
            True if signal data duplicate found
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        # Parse signal from message text (simple heuristic)
        parsed_signal = self._parse_signal_from_text(message.text)

        if not parsed_signal:
            return False

        symbol = parsed_signal.get("symbol")
        entry = parsed_signal.get("entry")

        if not symbol or not entry:
            return False

        # Look for similar signals
        recent_signals = (
            session.query(Signal)
            .filter(
                Signal.channel_id == channel_id,
                Signal.symbol == symbol,
                Signal.created_at >= cutoff_time,
                Signal.status.in_(["PENDING", "OPEN"]),  # Active signals
            )
            .all()
        )

        for signal in recent_signals:
            # Check if entry prices match (within 0.1%)
            if self._prices_match(entry, signal.entry_price):
                logger.debug(
                    f"Signal data duplicate found: {symbol} @ {entry}"
                )
                return True

        return False

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using SequenceMatcher.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        matcher = SequenceMatcher(None, text1.lower(), text2.lower())
        return matcher.ratio()

    def _parse_signal_from_text(self, text: str) -> Optional[dict]:
        """
        Parse basic signal data from message text.

        Args:
            text: Message text

        Returns:
            Dictionary with symbol and entry, or None
        """
        import re

        # Simple regex patterns to extract symbol and entry
        symbol_pattern = r"\b([A-Z]{3}USD|XAU/USD|XAUUSD)\b"
        entry_pattern = r"(?:entry|@|\()\s*([0-9]+\.[0-9]+)"

        symbol_match = re.search(symbol_pattern, text, re.IGNORECASE)
        entry_match = re.search(entry_pattern, text, re.IGNORECASE)

        if not symbol_match or not entry_match:
            return None

        return {
            "symbol": symbol_match.group(1).upper().replace("/", ""),
            "entry": float(entry_match.group(1)),
        }

    def _prices_match(self, price1: float, price2: float, tolerance: float = 0.001) -> bool:
        """
        Check if two prices match within tolerance (0.1%).

        Args:
            price1: First price
            price2: Second price
            tolerance: Tolerance as decimal (0.001 = 0.1%)

        Returns:
            True if prices match within tolerance
        """
        if price1 == 0 or price2 == 0:
            return False

        difference = abs(price1 - price2) / price1
        return difference <= tolerance

    def cleanup_old_messages(
        self,
        session: Session,
        days_to_keep: int = 30,
    ) -> int:
        """
        Clean up old non-signal messages to maintain database size.

        Args:
            session: Database session
            days_to_keep: Days of message history to keep

        Returns:
            Number of messages deleted
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
        logger.info(f"Cleaned up {deleted_count} old messages")
        return deleted_count

    def get_duplicate_stats(
        self,
        session: Session,
        channel_id: UUID,
        lookback_hours: int = 24,
    ) -> dict:
        """
        Get statistics on duplicate detection.

        Args:
            session: Database session
            channel_id: Channel ID
            lookback_hours: Lookback period

        Returns:
            Statistics dictionary
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        total_messages = (
            session.query(Message)
            .filter(
                Message.channel_id == channel_id,
                Message.created_at >= cutoff_time,
            )
            .count()
        )

        signal_messages = (
            session.query(Message)
            .filter(
                Message.channel_id == channel_id,
                Message.created_at >= cutoff_time,
                Message.is_signal == True,
            )
            .count()
        )

        return {
            "total_messages": total_messages,
            "signal_messages": signal_messages,
            "non_signal_messages": total_messages - signal_messages,
            "lookback_hours": lookback_hours,
            "period": f"Last {lookback_hours} hours",
        }


__all__ = ["DuplicateDetectionService"]