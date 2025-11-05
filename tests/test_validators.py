"""Tests for validation module."""

import pytest
from decimal import Decimal

from app.validators import Validators
from app.exceptions import ValidationError

class TestSymbolValidation:
    """Test symbol validation."""

    def test_valid_symbols(self):
        """Test valid symbol formats."""
        valid_symbols = ["EURUSD", "XAUUSD", "BTC/USD", "EUR/USD"]
        for symbol in valid_symbols:
            result = Validators.validate_symbol(symbol)
            assert result == symbol.upper()

    def test_symbol_normalization(self):
        """Test symbol is normalized to uppercase."""
        result = Validators.validate_symbol("eurusd")
        assert result == "EURUSD"

    def test_invalid_symbol_empty(self):
        """Test empty symbol validation."""
        with pytest.raises(ValidationError) as exc_info:
            Validators.validate_symbol("")
        assert exc_info.value.field == "symbol"

    def test_invalid_symbol_format(self):
        """Test invalid symbol format."""
        invalid_symbols = ["EU", "EURUSD12", "EUR@USD", ""]
        for symbol in invalid_symbols:
            with pytest.raises(ValidationError):
                Validators.validate_symbol(symbol)

    def test_symbol_with_slash(self):
        """Test symbol with slash."""
        result = Validators.validate_symbol("eur/usd")
        assert result == "EUR/USD"


class TestPriceValidation:
    """Test price validation."""

    def test_valid_prices(self):
        """Test valid price values."""
        valid_prices = ["1.0950", 1.0950, 1, 100.5]
        for price in valid_prices:
            result = Validators.validate_price(price)
            assert isinstance(result, Decimal)
            assert result > 0

    def test_price_conversion_to_decimal(self):
        """Test price is converted to Decimal."""
        result = Validators.validate_price("1.0950")
        assert isinstance(result, Decimal)
        assert result == Decimal("1.0950")

    def test_negative_price(self):
        """Test negative price validation."""
        with pytest.raises(ValidationError):
            Validators.validate_price(-1.0)

    def test_zero_price(self):
        """Test zero price validation."""
        with pytest.raises(ValidationError):
            Validators.validate_price(0)

    def test_invalid_price_format(self):
        """Test invalid price format."""
        invalid_prices = ["not_a_number", None, ""]
        for price in invalid_prices:
            with pytest.raises(ValidationError):
                Validators.validate_price(price)

    def test_price_precision(self):
        """Test price with too many decimal places."""
        # Price with more than 10 decimal places should fail
        with pytest.raises(ValidationError):
            Validators.validate_price("1.12345678901")

class TestSignalTypeValidation:
    """Test signal type validation."""

    def test_valid_signal_types(self):
        """Test valid signal types."""
        valid_types = ["BUY", "SELL", "LONG", "SHORT"]
        for sig_type in valid_types:
            result = Validators.validate_signal_type(sig_type)
            assert result == sig_type

    def test_signal_type_normalization(self):
        """Test signal type is normalized."""
        result = Validators.validate_signal_type("buy")
        assert result == "BUY"

    def test_invalid_signal_type(self):
        """Test invalid signal types."""
        invalid_types = ["HOLD", "NEUTRAL", "BUY/SELL", ""]
        for sig_type in invalid_types:
            with pytest.raises(ValidationError):
                Validators.validate_signal_type(sig_type)


class TestTimeframeValidation:
    """Test timeframe validation."""

    def test_valid_timeframes(self):
        """Test valid timeframes."""
        valid_timeframes = ["5M", "15M", "1H", "4H", "1D", "1W", "1M"]
        for tf in valid_timeframes:
            result = Validators.validate_timeframe(tf)
            assert result == tf

    def test_timeframe_normalization(self):
        """Test timeframe normalization."""
        result = Validators.validate_timeframe("1h")
        assert result == "1H"

    def test_invalid_timeframe(self):
        """Test invalid timeframes."""
        invalid_timeframes = ["2H", "3D", "1Y", ""]
        for tf in invalid_timeframes:
            with pytest.raises(ValidationError):
                Validators.validate_timeframe(tf)


class TestSignalLogicValidation:
    """Test signal logic validation."""

    def test_valid_buy_signal(self):
        """Test valid BUY signal."""
        result = Validators.validate_buy_signal(
            entry=Decimal("1.0950"),
            stop_loss=Decimal("1.0900"),
            take_profit=Decimal("1.1000")
        )
        assert result is True

    def test_invalid_buy_signal_entry_less_than_sl(self):
        """Test BUY signal with entry <= SL."""
        with pytest.raises(ValidationError):
            Validators.validate_buy_signal(
                entry=Decimal("1.0900"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.1000")
            )

    def test_invalid_buy_signal_tp_less_than_entry(self):
        """Test BUY signal with TP <= entry."""
        with pytest.raises(ValidationError):
            Validators.validate_buy_signal(
                entry=Decimal("1.0950"),
                stop_loss=Decimal("1.0900"),
                take_profit=Decimal("1.0950")
            )

    def test_valid_sell_signal(self):
        """Test valid SELL signal."""
        result = Validators.validate_sell_signal(
            entry=Decimal("1.0950"),
            stop_loss=Decimal("1.1000"),
            take_profit=Decimal("1.0900")
        )
        assert result is True

    def test_invalid_sell_signal_entry_greater_than_sl(self):
        """Test SELL signal with entry >= SL."""
        with pytest.raises(ValidationError):
            Validators.validate_sell_signal(
                entry=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                take_profit=Decimal("1.0900")
            )


class TestRiskRewardCalculation:
    """Test risk/reward ratio calculation."""

    def test_buy_signal_risk_reward(self):
        """Test risk/reward for BUY signal."""
        ratio = Validators.validate_risk_reward(
            entry=Decimal("1.0950"),
            stop_loss=Decimal("1.0900"),
            take_profit=Decimal("1.1000"),
            signal_type="BUY"
        )
        # Risk = 1.0950 - 1.0900 = 0.0050
        # Reward = 1.1000 - 1.0950 = 0.0050
        # Ratio = 0.0050 / 0.0050 = 1.00
        assert ratio == Decimal("1.00")

    def test_sell_signal_risk_reward(self):
        """Test risk/reward for SELL signal."""
        ratio = Validators.validate_risk_reward(
            entry=Decimal("1.0950"),
            stop_loss=Decimal("1.1000"),
            take_profit=Decimal("1.0900"),
            signal_type="SELL"
        )
        # Risk = 1.1000 - 1.0950 = 0.0050
        # Reward = 1.0950 - 1.0900 = 0.0050
        # Ratio = 0.0050 / 0.0050 = 1.00
        assert ratio == Decimal("1.00")

    def test_higher_reward_risk_reward(self):
        """Test risk/reward with higher reward."""
        ratio = Validators.validate_risk_reward(
            entry=Decimal("100.00"),
            stop_loss=Decimal("95.00"),
            take_profit=Decimal("110.00"),
            signal_type="BUY"
        )
        # Risk = 100 - 95 = 5
        # Reward = 110 - 100 = 10
        # Ratio = 10 / 5 = 2.00
        assert ratio == Decimal("2.00")

    def test_invalid_risk_reward(self):
        """Test invalid risk/reward setup."""
        with pytest.raises(ValidationError):
            Validators.validate_risk_reward(
                entry=Decimal("100.00"),
                stop_loss=Decimal("100.00"),
                take_profit=Decimal("110.00"),
                signal_type="BUY"
            )
