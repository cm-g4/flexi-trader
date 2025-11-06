"""Channel model for Telegram channel/group storage."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func

from app.database import Base

class Channel(Base):
    """
    Represents a Telegram channel or group that broadcasts trading signals.
    
    Attributes:
        id: Unique channel identifier (UUID)
        user_id: User who added this channel
        name: Display name for the channel
        description: Channel description
        telegram_channel_id: Telegram's channel/group ID
        telegram_chat_id: Telegram's chat ID for message access
        is_active: Whether channel is currently monitored
        provider_name: Signal provider name
        created_at: When channel was added
        updated_at: Last update timestamp
        signal_count: Total signals captured from this channel
        last_signal_at: Timestamp of last signal received
    """

    __tablename__ = "channels"

    # Primary key
    id = String(36), primary_key=True

    # User relationship (to be added in Phase 2 with user management)
    user_id = String(36)

    # Channel information
    name = String(255, nullable=False)
    description = Text(nullable=True)
    telegram_channel_id = Integer(nullable=False)
    telegram_chat_id = Integer(nullable=False)
    
    # Status
    is_active = Boolean(default=True)
    provider_name = String(255, nullable=False)

    # Timestamps
    created_at = DateTime(
        timezone=True, 
        default=datetime.now(datetime.timezone.utc), 
        nullable=False,
    )
    updated_at = DateTime(
        timezone=True, 
        default=datetime.now(datetime.timezone.utc),
        onupdate=datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Statistics
    signal_count = Integer(default=0)
    last_signal_at = DateTime(nullable=True)

    # Relationships (to be populated in future sprints)
    # messages = relationship("Message", back_populates="channel")
    # templates = relationship("Template", back_populates="channel")
    # signals = relationship("Signal", back_populates="channel")

    def __repr__(self) -> str:
        return (
            f"<Channel(id={self.id}, name='{self.name}', "
            f"telegram_id={self.telegram_channel_id}, active={self.is_active})>"
        )

__all__ = ["Channel"]