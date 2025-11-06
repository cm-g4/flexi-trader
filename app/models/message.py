"""Message model for raw Telegram message storage."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, 
    BigInteger,
    Boolean, 
    DateTime,
    ForeignKey, 
    Index,
    Integer, 
    String, 
    Text,
)

from app.database import Base

class Message(Base):
    """
    Represents a raw Telegram message received from a channel.
    
    Stores the original message data for reference, auditing, and 
    re-extraction with updated templates.
    
    Attributes:
        id: Unique message identifier
        channel_id: Reference to Channel
        telegram_message_id: Telegram's unique message ID
        telegram_chat_id: Telegram chat ID where message was posted
        telegram_sender_id: ID of message sender (if accessible)
        text: Full message text content
        is_signal: Whether this message was identified as a signal
        processed: Whether message has been processed for extraction
        processed_at: When message was processed
        extraction_attempts: Number of extraction attempts
        created_at: When message was received
        updated_at: Last update timestamp
        raw_data: Additional Telegram message metadata (JSON)
    """

    __tablename__ = "messages"


    # Primary key
    id = String(36), primary_key=True


    # Foreign keys
    channel_id = String(36, ForeignKey("channels.id"), nullable=False)


    # Telegram identifiers
    telegram_message_id = BigInteger(nullable=False)
    telegram_chat_id = BigInteger(nullable=False)
    telegram_sender_id = BigInteger(nullable=True)

    # Message content
    text = Text(nullable=True)

    # Processing status
    is_signal = Boolean(default=False, nullable=False)
    processed = Boolean(default=False, nullable=False)
    processed_at = DateTime(timezone=True, nullable=True)
    extraction_attempts = Integer(default=0, nullable=False)

    # Timestamps
    created_at = DateTime(timezone=True, default=datetime.timezone.utc, nullable=False)
    updated_at = DateTime(timezone=True, default=datetime.timezone.utc, onupdate=datetime.timezone.utc, nullable=False)

    # Additional metadata
    raw_data = JSON(nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Message(id={self.id}, "
            f"telegram_id={self.telegram_message_id}, "
            f"is_signal={self.is_signal}, processed={self.processed})>"
        )
    
    def mark_as_signal(self) -> None:
        """Mark message as a valid signal."""
        self.is_signal = True
        self.updated_at = datetime.timezone.utc

    def mark_as_processed(self) -> None:
        """Mark message as processed."""
        self.processed = True
        self.processed_at = datetime.timezone.utc
        self.updated_at = datetime.timezone.utc

    def increment_extraction_attempts(self) -> None:
        """Increment extraction attempt counter."""
        self.extraction_attempts += 1
        self.updated_at = datetime.timezone.utc

__all__ = ["Message"]