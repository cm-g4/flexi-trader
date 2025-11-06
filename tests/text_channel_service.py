"""Tests for channel service."""

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.exceptions import ChannelError, ValidationError
from app.models.channel import Channel
from app.services.channel_service import ChannelService


class TestChannelCreation:
    """Test channel creation functionality."""

    def test_create_channel_success(self, test_db: Session):
        """Test successful channel creation."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user123",
            description="Test description",
            provider_name="Provider A",
        )

        assert channel is not None
        assert channel.name == "Test Channel"
        assert channel.telegram_channel_id == 12345
        assert channel.telegram_chat_id == 67890
        assert channel.is_active is True
        assert channel.signal_count == 0
        assert channel.user_id == "user123"

    def test_create_channel_with_minimal_data(self, test_db: Session):
        """Test channel creation with minimal required data."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=11111,
            telegram_chat_id=22222,
            name="Minimal Channel",
            user_id="user456",
        )

        assert channel.name == "Minimal Channel"
        assert channel.description is None
        assert channel.provider_name is None

    def test_create_duplicate_channel(self, test_db: Session):
        """Test creating duplicate channel raises error."""
        ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Channel 1",
            user_id="user1",
        )
        test_db.commit()

        with pytest.raises(ChannelError):
            ChannelService.create_channel(
                session=test_db,
                telegram_channel_id=12345,  # Same telegram ID
                telegram_chat_id=67890,
                name="Channel 2",
                user_id="user1",
            )

    def test_create_channel_empty_name(self, test_db: Session):
        """Test channel creation with empty name fails."""
        with pytest.raises(ValidationError):
            ChannelService.create_channel(
                session=test_db,
                telegram_channel_id=12345,
                telegram_chat_id=67890,
                name="",
                user_id="user1",
            )

    def test_create_channel_invalid_ids(self, test_db: Session):
        """Test channel creation with invalid IDs fails."""
        with pytest.raises(ValidationError):
            ChannelService.create_channel(
                session=test_db,
                telegram_channel_id=-1,  # Invalid
                telegram_chat_id=67890,
                name="Channel",
                user_id="user1",
            )

        with pytest.raises(ValidationError):
            ChannelService.create_channel(
                session=test_db,
                telegram_channel_id=12345,
                telegram_chat_id=0,  # Invalid
                name="Channel",
                user_id="user1",
            )


class TestChannelRetrieval:
    """Test channel retrieval functionality."""

    def test_get_channel_by_id(self, test_db: Session):
        """Test retrieving channel by ID."""
        created = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        retrieved = ChannelService.get_channel(test_db, created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Test Channel"

    def test_get_channel_by_telegram_id(self, test_db: Session):
        """Test retrieving channel by Telegram ID."""
        created = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        retrieved = ChannelService.get_channel_by_telegram_id(
            test_db, telegram_channel_id=12345
        )

        assert retrieved is not None
        assert retrieved.telegram_channel_id == 12345

    def test_get_nonexistent_channel(self, test_db: Session):
        """Test retrieving nonexistent channel returns None."""
        retrieved = ChannelService.get_channel(test_db, "nonexistent_id")
        assert retrieved is None

    def test_get_active_channels(self, test_db: Session):
        """Test retrieving active channels."""
        # Create multiple channels
        channel1 = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=11111,
            telegram_chat_id=22222,
            name="Active 1",
            user_id="user1",
        )
        channel2 = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=33333,
            telegram_chat_id=44444,
            name="Active 2",
            user_id="user1",
        )
        test_db.commit()

        # Deactivate one
        ChannelService.deactivate_channel(test_db, channel2.id)
        test_db.commit()

        # Get active channels
        active = ChannelService.get_active_channels(test_db, user_id="user1")

        assert len(active) == 1
        assert active[0].id == channel1.id


class TestChannelActivation:
    """Test channel activation/deactivation."""

    def test_activate_channel(self, test_db: Session):
        """Test activating a channel."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test",
            user_id="user1",
        )
        test_db.commit()

        # Deactivate then reactivate
        ChannelService.deactivate_channel(test_db, channel.id)
        test_db.commit()

        activated = ChannelService.activate_channel(test_db, channel.id)
        test_db.commit()

        assert activated.is_active is True

    def test_deactivate_channel(self, test_db: Session):
        """Test deactivating a channel."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test",
            user_id="user1",
        )
        test_db.commit()

        deactivated = ChannelService.deactivate_channel(test_db, channel.id)
        test_db.commit()

        assert deactivated.is_active is False

    def test_activate_nonexistent_channel(self, test_db: Session):
        """Test activating nonexistent channel fails."""
        with pytest.raises(ChannelError):
            ChannelService.activate_channel(test_db, "nonexistent")


class TestChannelMetadataUpdate:
    """Test updating channel metadata."""

    def test_update_channel_name(self, test_db: Session):
        """Test updating channel name."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Original Name",
            user_id="user1",
        )
        test_db.commit()

        updated = ChannelService.update_channel_metadata(
            test_db, channel.id, name="New Name"
        )
        test_db.commit()

        assert updated.name == "New Name"

    def test_update_channel_description(self, test_db: Session):
        """Test updating channel description."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Channel",
            user_id="user1",
        )
        test_db.commit()

        updated = ChannelService.update_channel_metadata(
            test_db, channel.id, description="New description"
        )
        test_db.commit()

        assert updated.description == "New description"

    def test_update_channel_provider(self, test_db: Session):
        """Test updating channel provider name."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Channel",
            user_id="user1",
        )
        test_db.commit()

        updated = ChannelService.update_channel_metadata(
            test_db, channel.id, provider_name="New Provider"
        )
        test_db.commit()

        assert updated.provider_name == "New Provider"


class TestChannelSignalCounting:
    """Test signal count increment."""

    def test_increment_signal_count(self, test_db: Session):
        """Test incrementing signal count."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Channel",
            user_id="user1",
        )
        assert channel.signal_count == 0
        test_db.commit()

        # Increment multiple times
        for _ in range(5):
            ChannelService.increment_signal_count(test_db, channel.id)
            test_db.commit()

        retrieved = ChannelService.get_channel(test_db, channel.id)
        assert retrieved.signal_count == 5
        assert retrieved.last_signal_at is not None