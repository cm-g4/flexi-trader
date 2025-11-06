"""Channel model for Telegram channel/group storage."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

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
    id = Column(String(36), primary_key=True)

    # User relationship (to be added in Phase 2 with user management)
    user_id = Column(String(36))

    # Channel information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    telegram_channel_id = Column(Integer, nullable=False)
    telegram_chat_id = Column(Integer, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    provider_name = Column(String(255), nullable=False)

    # Timestamps
    created_at = Column(DateTime,
        timezone=True, 
        default=datetime.now(datetime.timezone.utc), 
        nullable=False,
    )
    updated_at = Column(DateTime,
        timezone=True, 
        default=datetime.now(datetime.timezone.utc),
        onupdate=datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Statistics
    signal_count = Column(Integer, default=0)
    last_signal_at = Column(DateTime, nullable=True)

    # Relationships (to be populated in future sprints)
    # messages = relationship("Message", back_populates="channel")
    # templates = relationship("Template", back_populates="channel")
    # signals = relationship("Signal", back_populates="channel")

    def __repr__(self) -> str:
        return (
            f"<Channel(id={self.id}, name='{self.name}', "
            f"telegram_id={self.telegram_channel_id}, active={self.is_active})>"
        )
    
    def to_dict(self) -> dict:
        """Convert channel to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "telegram_channel_id": self.telegram_channel_id,
            "telegram_chat_id": self.telegram_chat_id,
            "is_active": self.is_active,
            "provider_name": self.provider_name,
            "signal_count": self.signal_count,
            "last_signal_at": self.last_signal_at.isoformat() if self.last_signal_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

__all__ = ["Channel"]