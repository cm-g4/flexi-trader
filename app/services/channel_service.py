"""Channel management service for Telegram channel operations."""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.exceptions import ChannelError, DatabaseError, ValidationError
from app.logging_config import logger
from app.models.channel import Channel

class ChannelService:
    """
    Service for managing Telegram channels.
    
    Handles:
    - Channel registration
    - Channel configuration
    - Channel activation/deactivation
    - Channel metadata and statistics
    """

    @staticmethod
    def create_channel(
        session: Session,
        telegram_channel_id: int,
        telegram_chat_id: int,
        name: str,
        user_id: str,
        description: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> Channel:
        """
        Create a new channel record.
        
        Args:
            session: Database session
            telegram_channel_id: Telegram's channel/group ID (can be negative for private channels)
            telegram_chat_id: Telegram's chat ID
            name: Display name for channel
            user_id: User who added the channel
            description: Optional channel description
            provider_name: Optional provider name
        
        Returns:
            Created Channel object
        
        Raises:
            ChannelError: If channel creation fails
            ValidationError: If validation fails
        """

        try:
            # Validate inputs
            if not name or not name.strip():
                raise ValidationError("Channel name cannot be empty", field="name")

            # Telegram IDs can be negative (for private channels) or positive (for public)
            # Both are valid - just validate they're integers
            if not isinstance(telegram_channel_id, int) or not isinstance(telegram_chat_id, int):
                raise ValidationError(
                    "Channel IDs must be valid integers",
                    field="telegram_channel_id",
                )
            
            # Check if channel already exists
            existing = (
                session.query(Channel)
                .filter(Channel.telegram_channel_id == telegram_channel_id)
                .first()
            )
            if existing:
                raise ChannelError(
                    f"Channel already registered: {telegram_channel_id}"
                )
            
            # Create channel
            channel = Channel(
                id=ChannelService._generate_channel_id(),
                user_id=user_id,
                name=name.strip(),
                description=description.strip() if description else None,
                telegram_channel_id=telegram_channel_id,
                telegram_chat_id=telegram_chat_id,
                provider_name=provider_name,
                is_active=True,
                signal_count=0,
            )

            session.add(channel)
            session.flush()

            logger.info(
                f"Channel created: id={channel.id}, "
                f"name={channel.name}, "
                f"telegram_id={telegram_channel_id}"
            )

            return channel

        except (ValidationError, ChannelError):
            raise
        except Exception as e:
            logger.error(f"Failed to create channel: {e}")
            raise DatabaseError(f"Failed to create channel: {e}")
    
    @staticmethod
    def get_channel(session: Session, channel_id: str) -> Optional[Channel]:
        """
        Retrieve a channel by ID.
        
        Args:
            session: Database session
            channel_id: Channel identifier
        
        Returns:
            Channel object if found, None otherwise
        """
        return session.query(Channel).filter(Channel.id == channel_id).first()

    @staticmethod
    def get_channel_by_telegram_id(
        session: Session,
        telegram_channel_id: int,
    ) -> Optional[Channel]:
        """
        Retrieve a channel by Telegram channel ID.
        
        Args:
            session: Database session
            telegram_channel_id: Telegram's channel ID (can be negative)
        
        Returns:
            Channel object if found, None otherwise
        """
        return (
            session.query(Channel)
            .filter(Channel.telegram_channel_id == telegram_channel_id)
            .first()
        )

    @staticmethod
    def get_active_channels(
        session: Session,
        user_id: Optional[str] = None,
    ) -> List[Channel]:
        """
        Get all active channels.
        
        Args:
            session: Database session
            user_id: Filter by user (optional)
        
        Returns:
            List of active Channel objects
        """
        query = session.query(Channel).filter(Channel.is_active == True)

        if user_id:
            query = query.filter(Channel.user_id == user_id)

        return query.order_by(Channel.created_at.desc()).all()

    @staticmethod
    def get_all_channels(session: Session, user_id: Optional[str] = None) -> List[Channel]:
        """
        Get all channels (active and inactive).
        
        Args:
            session: Database session
            user_id: Filter by user (optional)
        
        Returns:
            List of Channel objects
        """
        query = session.query(Channel)

        if user_id:
            query = query.filter(Channel.user_id == user_id)

        return query.order_by(Channel.created_at.desc()).all()

    @staticmethod
    def activate_channel(session: Session, channel_id: str) -> Channel:
        """
        Activate a channel.
        
        Args:
            session: Database session
            channel_id: Channel identifier
        
        Returns:
            Updated Channel object
        
        Raises:
            ChannelError: If channel not found
        """
        channel = ChannelService.get_channel(session, channel_id)
        if not channel:
            raise ChannelError(f"Channel not found: {channel_id}")

        channel.is_active = True
        channel.updated_at = datetime.now(timezone.utc)
        session.add(channel)
        session.flush()

        logger.info(f"Channel activated: id={channel_id}, name={channel.name}")
        return channel
    
    @staticmethod
    def deactivate_channel(session: Session, channel_id: str) -> Channel:
        """
        Deactivate a channel (does not delete data).
        
        Args:
            session: Database session
            channel_id: Channel identifier
        
        Returns:
            Updated Channel object
        
        Raises:
            ChannelError: If channel not found
        """
        channel = ChannelService.get_channel(session, channel_id)
        if not channel:
            raise ChannelError(f"Channel not found: {channel_id}")

        channel.is_active = False
        channel.updated_at = datetime.now(timezone.utc)
        session.add(channel)
        session.flush()

        logger.info(f"Channel deactivated: id={channel_id}, name={channel.name}")
        return channel

    @staticmethod
    def update_channel_metadata(
        session: Session,
        channel_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> Channel:
        """
        Update channel metadata.
        
        Args:
            session: Database session
            channel_id: Channel identifier
            name: New name (optional)
            description: New description (optional)
            provider_name: New provider name (optional)
        
        Returns:
            Updated Channel object
        
        Raises:
            ChannelError: If channel not found
        """
        channel = ChannelService.get_channel(session, channel_id)
        if not channel:
            raise ChannelError(f"Channel not found: {channel_id}")

        if name:
            channel.name = name.strip()
        if description:
            channel.description = description.strip()
        if provider_name:
            channel.provider_name = provider_name.strip()

        channel.updated_at = datetime.now(timezone.utc)
        session.add(channel)
        session.flush()

        logger.info(f"Channel metadata updated: id={channel_id}")
        return channel

    @staticmethod
    def increment_signal_count(
        session: Session,
        channel_id: str,
    ) -> Channel:
        """
        Increment the signal count for a channel.
        
        Args:
            session: Database session
            channel_id: Channel identifier
        
        Returns:
            Updated Channel object
        
        Raises:
            ChannelError: If channel not found
        """
        channel = ChannelService.get_channel(session, channel_id)
        if not channel:
            raise ChannelError(f"Channel not found: {channel_id}")

        channel.signal_count += 1
        channel.last_signal_at = datetime.now(timezone.utc)
        channel.updated_at = datetime.now(timezone.utc)
        session.add(channel)
        session.flush()

        return channel

    @staticmethod
    def _generate_channel_id() -> str:
        """
        Generate unique channel ID.
        
        Returns:
            UUID string
        """
        import uuid

        return str(uuid.uuid4())

__all__ = ["ChannelService"]