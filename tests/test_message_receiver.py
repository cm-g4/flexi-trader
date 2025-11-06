"""Tests for message receiver service."""

import pytest
from sqlalchemy.orm import Session

from app.exceptions import ChannelError, DatabaseError
from app.models.message import Message
from app.services.channel_service import ChannelService
from app.services.message_receiver import MessageReceiverService


class TestMessageReception:
    """Test message reception and storage."""

    def test_receive_message_success(self, test_db: Session):
        """Test successful message reception."""
        # Create channel first
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        # Receive message
        message = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="Test signal message",
            telegram_sender_id=111,
        )

        assert message is not None
        assert message.channel_id == channel.id
        assert message.text == "Test signal message"
        assert message.telegram_message_id == 999
        assert message.is_signal is False
        assert message.processed is False

    def test_receive_message_with_metadata(self, test_db: Session):
        """Test receiving message with metadata."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        metadata = {"chat_type": "group", "message_type": "text"}

        message = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="Test message",
            telegram_sender_id=111,
            raw_data=metadata,
        )

        assert message.raw_data == metadata

    def test_receive_message_nonexistent_channel(self, test_db: Session):
        """Test receiving message from nonexistent channel fails."""
        with pytest.raises(ChannelError):
            MessageReceiverService.receive_message(
                session=test_db,
                channel_id="nonexistent_channel",
                telegram_message_id=999,
                telegram_chat_id=67890,
                text="Test message",
            )


class TestMessageProcessing:
    """Test message processing status."""

    def test_mark_message_processed(self, test_db: Session):
        """Test marking message as processed."""
        # Create channel and message
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        message = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="Test message",
        )
        test_db.commit()

        assert message.processed is False

        # Mark as processed
        updated = MessageReceiverService.mark_message_processed(
            test_db, message.id, is_signal=False
        )
        test_db.commit()

        assert updated.processed is True
        assert updated.processed_at is not None

    def test_mark_message_as_signal_and_processed(self, test_db: Session):
        """Test marking message as signal and processed."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        message = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / 1.1000 / SL 1.0900",
        )
        test_db.commit()

        updated = MessageReceiverService.mark_message_processed(
            test_db, message.id, is_signal=True
        )
        test_db.commit()

        assert updated.is_signal is True
        assert updated.processed is True


class TestExtractionAttempts:
    """Test extraction attempt recording."""

    def test_record_failed_extraction(self, test_db: Session):
        """Test recording failed extraction attempt."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        message = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="Invalid message",
        )
        test_db.commit()

        assert message.extraction_attempts == 0

        # Record failed attempt
        updated = MessageReceiverService.record_extraction_attempt(
            test_db, message.id, success=False
        )
        test_db.commit()

        assert updated.extraction_attempts == 1
        assert updated.processed is False

    def test_record_successful_extraction(self, test_db: Session):
        """Test recording successful extraction."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        message = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950",
        )
        test_db.commit()

        updated = MessageReceiverService.record_extraction_attempt(
            test_db, message.id, success=True
        )
        test_db.commit()

        assert updated.extraction_attempts == 1
        assert updated.is_signal is True
        assert updated.processed is True

    def test_multiple_extraction_attempts(self, test_db: Session):
        """Test multiple extraction attempts."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        message = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="Test message",
        )
        test_db.commit()

        # Try extraction 3 times
        for i in range(3):
            MessageReceiverService.record_extraction_attempt(
                test_db, message.id, success=False
            )
            test_db.commit()

        retrieved = test_db.query(Message).filter_by(id=message.id).first()
        assert retrieved.extraction_attempts == 3


class TestMessageRetrieval:
    """Test message retrieval functionality."""

    def test_get_unprocessed_messages(self, test_db: Session):
        """Test retrieving unprocessed messages."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        # Create 3 messages
        for i in range(3):
            MessageReceiverService.receive_message(
                session=test_db,
                channel_id=channel.id,
                telegram_message_id=1000 + i,
                telegram_chat_id=67890,
                text=f"Message {i}",
            )
        test_db.commit()

        # Mark one as processed
        messages = test_db.query(Message).all()
        MessageReceiverService.mark_message_processed(
            test_db, messages[0].id
        )
        test_db.commit()

        unprocessed = MessageReceiverService.get_unprocessed_messages(
            test_db, channel_id=channel.id
        )

        assert len(unprocessed) == 2

    def test_get_recent_messages(self, test_db: Session):
        """Test retrieving recent messages."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        # Create 5 messages
        for i in range(5):
            MessageReceiverService.receive_message(
                session=test_db,
                channel_id=channel.id,
                telegram_message_id=1000 + i,
                telegram_chat_id=67890,
                text=f"Message {i}",
            )
        test_db.commit()

        recent = MessageReceiverService.get_recent_messages(
            test_db, channel_id=channel.id, limit=3
        )

        assert len(recent) == 3
        # Verify they're in reverse chronological order
        assert recent[0].telegram_message_id > recent[1].telegram_message_id


class TestMessageFlags:
    """Test message flag methods."""

    def test_mark_as_signal(self, test_db: Session):
        """Test marking message as signal."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        message = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950",
        )
        assert message.is_signal is False
        test_db.commit()

        message.mark_as_signal()
        test_db.add(message)
        test_db.commit()

        retrieved = test_db.query(Message).filter_by(id=message.id).first()
        assert retrieved.is_signal is True

    def test_mark_as_processed_sets_timestamp(self, test_db: Session):
        """Test marking processed sets timestamp."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        message = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="Test",
        )
        assert message.processed_at is None
        test_db.commit()

        message.mark_as_processed()
        test_db.add(message)
        test_db.commit()

        retrieved = test_db.query(Message).filter_by(id=message.id).first()
        assert retrieved.processed_at is not None