"""Tests for parser engine - core signal extraction component."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal

from app.services.parser_engine import ParserEngine
from app.exceptions import ExtractionError, ValidationError


class TestParserEngine:
    """Tests for ParserEngine."""

    @pytest.fixture
    def parser_engine(self):
        """Create parser engine instance."""
        return ParserEngine()

    def test_parser_initialization(self, parser_engine):
        """Test parser engine initializes correctly."""
        assert parser_engine is not None
        assert parser_engine.extraction_engine is not None
        assert parser_engine.signal_validator is not None

    def test_normalize_take_profits_single_value(self, parser_engine):
        """Test normalizing single take profit value."""
        result = parser_engine._normalize_take_profits("1.1000")

        assert len(result) == 1
        assert result[0]["level"] == "TP1"
        assert result[0]["price"] == Decimal("1.1000")
        assert result[0]["hit"] is False

    def test_normalize_take_profits_list(self, parser_engine):
        """Test normalizing list of take profits."""
        tp_list = [1.1000, 1.1100, 1.1200]
        result = parser_engine._normalize_take_profits(tp_list)

        assert len(result) == 3
        assert result[0]["level"] == "TP1"
        assert result[1]["level"] == "TP2"
        assert result[2]["level"] == "TP3"

    def test_normalize_take_profits_dict_list(self, parser_engine):
        """Test normalizing list of TP dictionaries."""
        tp_list = [
            {"level": "TP1", "price": 1.1000, "hit": False},
            {"level": "TP2", "price": 1.1100, "hit": False},
        ]
        result = parser_engine._normalize_take_profits(tp_list)

        assert len(result) == 2
        assert result[0]["level"] == "TP1"
        assert result[1]["price"] == Decimal("1.1100")

    def test_normalize_take_profits_empty(self, parser_engine):
        """Test normalizing empty take profits."""
        result = parser_engine._normalize_take_profits(None)
        assert result == []

    def test_confidence_score_full_signal(self, parser_engine):
        """Test confidence score calculation for complete signal."""
        data = {
            "symbol": "EURUSD",
            "entry_price": 1.0850,
            "stop_loss": 1.0800,
            "take_profits": [1.0900],
            "signal_type": "BUY",
            "timeframe": "1H",
        }

        score = parser_engine._calculate_confidence_score(data)
        assert score == Decimal("1.0")

    def test_confidence_score_missing_sl(self, parser_engine):
        """Test confidence score with missing stop loss."""
        data = {
            "symbol": "EURUSD",
            "entry_price": 1.0850,
            "take_profits": [1.0900],
            "signal_type": "BUY",
            "timeframe": "1H",
        }

        score = parser_engine._calculate_confidence_score(data)
        assert score == Decimal("0.85")  # 1.0 - 0.15 for missing SL

    def test_confidence_score_minimal_signal(self, parser_engine):
        """Test confidence score for minimal signal."""
        data = {
            "symbol": "EURUSD",
            "entry_price": 1.0850,
        }

        score = parser_engine._calculate_confidence_score(data)
        # 1.0 - 0.15 (no SL) - 0.15 (no TPs) - 0.05 (no TF) - 0.05 (no type) = 0.6
        assert score == Decimal("0.60")

    def test_validate_extracted_data_missing_symbol(self, parser_engine):
        """Test validation fails for missing symbol."""
        data = {
            "entry_price": 1.0850,
        }

        with pytest.raises(ValidationError) as exc:
            parser_engine._validate_extracted_data(data)
        assert "Symbol is required" in str(exc.value)

    def test_validate_extracted_data_missing_entry(self, parser_engine):
        """Test validation fails for missing entry price."""
        data = {
            "symbol": "EURUSD",
        }

        with pytest.raises(ValidationError) as exc:
            parser_engine._validate_extracted_data(data)
        assert "Entry price is required" in str(exc.value)

    def test_validate_extracted_data_valid(self, parser_engine):
        """Test validation succeeds for valid data."""
        data = {
            "symbol": "eurusd",
            "entry_price": 1.0850,
            "stop_loss": 1.0800,
            "take_profits": [1.0900],
            "signal_type": "buy",
            "timeframe": "1h",
        }

        result = parser_engine._validate_extracted_data(data)

        assert result["symbol"] == "EURUSD"
        assert result["signal_type"] == "BUY"
        assert result["timeframe"] == "1H"

    def test_validate_extracted_data_invalid_timeframe_removed(self, parser_engine):
        """Test invalid timeframe is removed gracefully."""
        data = {
            "symbol": "EURUSD",
            "entry_price": 1.0850,
            "timeframe": "invalid",
        }

        result = parser_engine._validate_extracted_data(data)
        assert "timeframe" not in result

    def test_validate_extracted_data_invalid_signal_type_defaults(self, parser_engine):
        """Test invalid signal type defaults to BUY."""
        data = {
            "symbol": "EURUSD",
            "entry_price": 1.0850,
            "signal_type": "invalid",
        }

        result = parser_engine._validate_extracted_data(data)
        assert result["signal_type"] == "BUY"

    def test_create_signal_from_data(self, parser_engine):
        """Test creating Signal object from extracted data."""
        validated_data = {
            "symbol": "EURUSD",
            "entry_price": Decimal("1.0850"),
            "stop_loss": Decimal("1.0800"),
            "take_profits": [{"price": Decimal("1.0900"), "level": "TP1"}],
            "signal_type": "BUY",
            "timeframe": "1H",
        }

        # Create mock objects
        message = type("Message", (), {
            "id": uuid4(),
            "telegram_message_id": 123,
            "text": "BUY EURUSD Entry: 1.0850 SL: 1.0800 TP1: 1.0900",
        })()

        template = type("Template", (), {
            "id": uuid4(),
            "name": "Test Template",
        })()

        channel_id = uuid4()
        user_id = "test_user"

        signal = parser_engine._create_signal_from_data(
            validated_data=validated_data,
            message=message,
            template=template,
            channel_id=channel_id,
            user_id=user_id,
        )

        assert signal.symbol == "EURUSD"
        assert signal.entry_price == Decimal("1.0850")
        assert signal.signal_type == "BUY"
        assert signal.status == "PENDING"
        assert signal.confidence_score == Decimal("1.0")

    def test_create_signal_with_partial_data(self, parser_engine):
        """Test creating signal with missing optional fields."""
        validated_data = {
            "symbol": "EURUSD",
            "entry_price": Decimal("1.0850"),
            "signal_type": "BUY",
        }

        message = type("Message", (), {
            "id": uuid4(),
            "telegram_message_id": 123,
            "text": "BUY EURUSD Entry: 1.0850",
        })()

        template = type("Template", (), {
            "id": uuid4(),
            "name": "Test Template",
        })()

        signal = parser_engine._create_signal_from_data(
            validated_data=validated_data,
            message=message,
            template=template,
            channel_id=uuid4(),
            user_id="test_user",
        )

        assert signal.symbol == "EURUSD"
        assert signal.stop_loss is None
        assert signal.take_profits == []
        # Confidence should be reduced for missing fields
        assert signal.confidence_score < Decimal("1.0")

    def test_parser_batch_processing(self, parser_engine):
        """Test batch processing multiple messages."""
        # This would require full database setup
        # Placeholder for integration test
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])