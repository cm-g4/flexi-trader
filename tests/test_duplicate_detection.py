"""Tests for duplicate detection service."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models import Message, Channel
from app.services.channel_service import ChannelService
from app.services.duplicate_detection import DuplicateDetectionService
from app.services.message_receiver import MessageReceiverService
from app.exceptions import DuplicateSignalError


class TestDuplicateDetector:
    """Test duplicate message detection."""

    @pytest.fixture
    def channel(self, test_db):
        channel = Channel(
            id=str(uuid4()),
            user_id="user1",
            name="Test Channel",
            description="Test Channel Description",
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            is_active=True,
            provider_name="Test Provider",
        )
        test_db.add(channel)
        test_db.commit()
        return channel

    @pytest.fixture
    def duplicate_detector(self):
        return DuplicateDetectionService()

    def test_detect_exact_duplicate(self, test_db: Session, channel: Channel, duplicate_detector: DuplicateDetectionService):
        """Test detecting exact duplicate messages."""
        message1 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=123,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
        )
        test_db.add(message1)
        test_db.commit()
        # First message
        # Create identical second message
        message2 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=124,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
        )
        test_db.add(message2)
        test_db.commit()

        # Try to receive same message again
        is_duplicate = duplicate_detector.is_duplicate(
            test_db, message2, channel.id
        )
        assert is_duplicate is True

    def test_not_duplicate_different_content(self, test_db, channel, duplicate_detector):
        """Test that different messages are not flagged as duplicates."""
        message1 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=123,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
        )
        test_db.add(message1)
        test_db.commit()

        message2 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=124,
            telegram_chat_id=67890,
            text="GBPUSD @ 1.2700 / TP1: 1.2800 / SL: 1.2600",
            telegram_sender_id=999,
        )
        test_db.add(message2)
        test_db.commit()

        is_duplicate = duplicate_detector.is_duplicate(
            test_db, message2, channel.id
        )
        assert is_duplicate is False
    
    def test_duplicate_with_whitespace_variation(self, test_db, channel, duplicate_detector):
        """Test that minor whitespace differences are detected as duplicates."""
        message1 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=123,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
        )
        test_db.add(message1)
        test_db.commit()

        # Same content but with extra spaces
        message2 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=124,
            telegram_chat_id=67890,
            text="EURUSD  @  1.0950  /  TP1:  1.1000  /  SL:  1.0900",
            telegram_sender_id=999,
        )
        test_db.add(message2)
        test_db.commit()

        is_duplicate = duplicate_detector.is_duplicate(
            test_db, message2, channel.id
        )
        # Should detect as duplicate with fuzzy matching
        assert is_duplicate is True

    def test_duplicate_detection_within_time_window(self, test_db, channel, duplicate_detector):
        """Test that duplicates within time window are detected."""
        now = datetime.now(timezone.utc)
        
        message1 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=123,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
            created_at=now,
        )
        test_db.add(message1)
        test_db.commit()

        # Create duplicate within 5 minutes
        message2 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=124,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
            created_at=now + timedelta(minutes=2),
        )
        test_db.add(message2)
        test_db.commit()

        is_duplicate = duplicate_detector.is_duplicate(
            test_db, message2, channel.id
        )
        assert is_duplicate is True

    def test_no_duplicate_outside_time_window(self, test_db, channel, duplicate_detector):
        """Test that duplicates outside time window are not detected."""
        now = datetime.now(timezone.utc)
        
        message1 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=123,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
            created_at=now,
        )
        test_db.add(message1)
        test_db.commit()

        # Create duplicate outside 5 minute window
        message2 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=124,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
            created_at=now + timedelta(minutes=10),
        )
        test_db.add(message2)
        test_db.commit()

        is_duplicate = duplicate_detector.is_duplicate(
            test_db, message2, channel.id
        )
        assert is_duplicate is False

    def test_duplicate_per_channel(self, test_db, duplicate_detector):
        """Test that duplicate detection is per-channel."""
        # Create two channels
        channel1 = Channel(
            id=str(uuid4()),
            user_id="test_user",
            name="Channel 1",
            telegram_channel_id=111,
            telegram_chat_id=1111,
            is_active=True,
            provider_name="Provider 1",
        )
        channel2 = Channel(
            id=str(uuid4()),
            user_id="test_user",
            name="Channel 2",
            telegram_channel_id=222,
            telegram_chat_id=2222,
            is_active=True,
            provider_name="Provider 2",
        )
        test_db.add_all([channel1, channel2])
        test_db.commit()

        # Create message in channel1
        message1 = Message(
            id=str(uuid4()),
            channel_id=channel1.id,
            telegram_message_id=123,
            telegram_chat_id=1111,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
        )
        test_db.add(message1)
        test_db.commit()

        # Create identical message in channel2
        message2 = Message(
            id=str(uuid4()),
            channel_id=channel2.id,
            telegram_message_id=124,
            telegram_chat_id=2222,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
        )
        test_db.add(message2)
        test_db.commit()

        # Should NOT be flagged as duplicate (different channels)
        is_duplicate = duplicate_detector.is_duplicate(
            test_db, message2, channel2.id
        )
        assert is_duplicate is False

    def test_duplicate_error_raised(self, test_db, channel):
        """Test that DuplicateSignalError is raised when duplicate detected."""
        message = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=123,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
        )

        detector = DuplicateDetectionService()
        test_db.add(message)
        test_db.commit()

        # Create duplicate
        duplicate_message = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=124,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
        )

        with pytest.raises(DuplicateSignalError):
            detector.detect_or_raise(test_db, duplicate_message, channel.id)
    
    def test_similarity_threshold(self, test_db, channel, duplicate_detector):
        """Test similarity threshold for fuzzy matching."""
        message1 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=123,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / TP1: 1.1000 / SL: 1.0900",
            telegram_sender_id=999,
        )
        test_db.add(message1)
        test_db.commit()

        # Similar but different message
        message2 = Message(
            id=str(uuid4()),
            channel_id=channel.id,
            telegram_message_id=124,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0955 / TP1: 1.1005 / SL: 1.0895",
            telegram_sender_id=999,
        )
        test_db.add(message2)
        test_db.commit()

        is_duplicate = duplicate_detector.is_duplicate(
            test_db, message2, channel.id
        )
        # Should not be duplicate (different prices)
        assert is_duplicate is False


__all__ = ["TestDuplicateDetector"]