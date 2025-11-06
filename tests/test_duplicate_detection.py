"""Tests for duplicate detection service."""

import pytest
from sqlalchemy.orm import Session

from app.models.message import Message
from app.services.channel_service import ChannelService
from app.services.duplicate_detection import DuplicateDetectionService
from app.services.message_receiver import MessageReceiverService


class TestDuplicateDetection:
    """Test duplicate message detection."""

    def test_detect_exact_duplicate(self, test_db: Session):
        """Test detecting exact duplicate messages."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        # First message
        msg1 = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950",
        )
        test_db.commit()

        # Try to receive same message again
        is_dup = DuplicateDetectionService.is_duplicate_message(
            test_db, channel.id, telegram_message_id=999
        )

        assert is_dup is True

    def test_no_duplicate_different_message(self, test_db: Session):
        """Test different messages are not marked as duplicates."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="Message 1",
        )
        test_db.commit()

        is_dup = DuplicateDetectionService.is_duplicate_message(
            test_db, channel.id, telegram_message_id=1000
        )

        assert is_dup is False

    def test_duplicate_across_channels(self, test_db: Session):
        """Test duplicates are detected per-channel."""
        channel1 = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=11111,
            telegram_chat_id=22222,
            name="Channel 1",
            user_id="user1",
        )
        channel2 = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=33333,
            telegram_chat_id=44444,
            name="Channel 2",
            user_id="user1",
        )
        test_db.commit()

        # Same telegram message ID in different channels - should both be allowed
        MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel1.id,
            telegram_message_id=999,
            telegram_chat_id=22222,
            text="Message 1",
        )
        test_db.commit()

        # Should not be duplicate in channel2
        is_dup = DuplicateDetectionService.is_duplicate_message(
            test_db, channel2.id, telegram_message_id=999
        )

        assert is_dup is False

    def test_prevent_duplicate_reception(self, test_db: Session):
        """Test that receive_message returns None for duplicates."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        # First reception
        msg1 = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="Message",
        )
        test_db.commit()
        assert msg1 is not None

        # Second reception (duplicate)
        msg2 = MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="Message",
        )
        test_db.commit()
        assert msg2 is None


class TestSimilarityDetection:
    """Test similar message detection."""

    def test_detect_identical_text_similarity(self, test_db: Session):
        """Test detecting identical messages."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / 1.1000 / SL 1.0900",
        )
        test_db.commit()

        similar = DuplicateDetectionService.is_similar_message(
            test_db,
            channel.id,
            "EURUSD @ 1.0950 / 1.1000 / SL 1.0900",
        )

        assert similar is not None

    def test_detect_very_similar_messages(self, test_db: Session):
        """Test detecting very similar messages with minor differences."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / 1.1000 / SL 1.0900",
        )
        test_db.commit()

        # Very similar but with extra whitespace/minor changes
        similar = DuplicateDetectionService.is_similar_message(
            test_db,
            channel.id,
            "EURUSD @  1.0950  / 1.1000  / SL 1.0900",
            similarity_threshold=0.90,
        )

        assert similar is not None

    def test_no_similarity_different_content(self, test_db: Session):
        """Test different messages are not similar."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950",
        )
        test_db.commit()

        similar = DuplicateDetectionService.is_similar_message(
            test_db,
            channel.id,
            "XAUUSD completely different signal",
            similarity_threshold=0.80,
        )

        assert similar is None

    def test_similarity_threshold(self, test_db: Session):
        """Test similarity threshold works correctly."""
        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        MessageReceiverService.receive_message(
            session=test_db,
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950 / 1.1000 / SL 1.0900",
        )
        test_db.commit()

        # High threshold - should not match slightly different text
        similar = DuplicateDetectionService.is_similar_message(
            test_db,
            channel.id,
            "EURUSD @ 1.0951 / 1.1001 / SL 1.0901",
            similarity_threshold=0.99,
        )

        assert similar is None


class TestTextSimilarityCalculation:
    """Test text similarity calculation."""

    def test_exact_match(self):
        """Test exact match returns 1.0."""
        text1 = "EURUSD @ 1.0950"
        text2 = "EURUSD @ 1.0950"

        similarity = DuplicateDetectionService._calculate_similarity(text1, text2)
        assert similarity == 1.0

    def test_case_insensitive(self):
        """Test similarity is case insensitive."""
        text1 = "EURUSD @ 1.0950"
        text2 = "eurusd @ 1.0950"

        similarity = DuplicateDetectionService._calculate_similarity(text1, text2)
        assert similarity == 1.0

    def test_whitespace_normalized(self):
        """Test whitespace is normalized."""
        text1 = "EURUSD @ 1.0950"
        text2 = "eurusd @  1.0950  "

        similarity = DuplicateDetectionService._calculate_similarity(text1, text2)
        assert similarity > 0.95

    def test_different_texts(self):
        """Test completely different texts."""
        text1 = "EURUSD signal"
        text2 = "XAUUSD completely different"

        similarity = DuplicateDetectionService._calculate_similarity(text1, text2)
        assert similarity < 0.5


class TestCleanupOldDuplicates:
    """Test cleanup of old messages."""

    def test_cleanup_old_non_signal_messages(self, test_db: Session):
        """Test cleanup removes old non-signal messages."""
        from datetime import datetime, timedelta

        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        # Create old non-signal message
        old_message = Message(
            id="old_msg_1",
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="Old message",
            is_signal=False,
            created_at=datetime.utcnow() - timedelta(days=35),
        )
        test_db.add(old_message)
        test_db.commit()

        # Cleanup with 30-day retention
        deleted = DuplicateDetectionService.cleanup_old_duplicates(
            test_db, days_to_keep=30
        )

        assert deleted > 0

    def test_cleanup_preserves_signal_messages(self, test_db: Session):
        """Test cleanup preserves old signal messages."""
        from datetime import datetime, timedelta

        channel = ChannelService.create_channel(
            session=test_db,
            telegram_channel_id=12345,
            telegram_chat_id=67890,
            name="Test Channel",
            user_id="user1",
        )
        test_db.commit()

        # Create old signal message
        signal_message = Message(
            id="old_signal_1",
            channel_id=channel.id,
            telegram_message_id=999,
            telegram_chat_id=67890,
            text="EURUSD @ 1.0950",
            is_signal=True,
            created_at=datetime.utcnow() - timedelta(days=35),
        )
        test_db.add(signal_message)
        test_db.commit()

        initial_count = test_db.query(Message).count()

        # Cleanup should not delete signal message
        DuplicateDetectionService.cleanup_old_duplicates(test_db, days_to_keep=30)

        final_count = test_db.query(Message).count()
        assert final_count == initial_count