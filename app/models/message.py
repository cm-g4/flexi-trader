"""Message model for raw Telegram message storage."""

from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from uuid import uuid4

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
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)


    # Foreign keys
    channel_id = Column(UUID[UUID](as_uuid=True), ForeignKey("channels.id"), nullable=False)


    # Telegram identifiers
    telegram_message_id = Column(BigInteger, nullable=False)
    telegram_chat_id = Column(BigInteger, nullable=False)
    telegram_sender_id = Column(BigInteger, nullable=True)

    # Message content
    text = Column(Text, nullable=True)

    # Processing status
    is_signal = Column(Boolean, default=False, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    extraction_attempts = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    # Additional metadata
    raw_data = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Message(id={self.id}, "
            f"telegram_id={self.telegram_message_id}, "
            f"is_signal={self.is_signal}, processed={self.processed})>"
        )
    
    def mark_as_signal(self) -> None:
        """Mark message as a valid signal."""
        self.is_signal = True
        self.updated_at = datetime.now(timezone.utc)

    def mark_as_processed(self) -> None:
        """Mark message as processed."""
        self.processed = True
        self.processed_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def increment_extraction_attempts(self) -> None:
        """Increment extraction attempt counter."""
        self.extraction_attempts += 1
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "telegram_message_id": self.telegram_message_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "message_text": self.message_text,
            "is_duplicate": self.is_duplicate,
            "duplicate_of_id": self.duplicate_of_id,
            "is_signal": self.is_signal,
            "created_at": self.created_at.isoformat(),
            "received_at": self.received_at.isoformat(),
        }

__all__ = ["Message"]