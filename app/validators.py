"""Validation utilities for data validation."""

import re
from typing import Any
from decimal import Decimal

from app.exceptions import ValidationError

class Validators:
    """Validation utilities for common data types and business rules."""


    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """
        Validate trading symbol format.

        Args:
            symbol: Trading symbol (e.g., EURUSD, XAUUSD)

        Returns:
            Normalized symbol (uppercase)

        Raises:
            ValidationError: If symbol format is invalid
        """
        if not symbol or not isinstance(symbol, str):
            raise ValidationError("Symbol must be a non-empty string", field="symbol")
        
        symbol = symbol.upper().strip()


        # Allow  alphanumeric characters and slashes
        if not re.match(r"^[A-Z0-9/]{3,10}$", symbol):
            raise ValidationError(
                f"Invalid symbol format: {symbol}. Must be 3-10 alphanumeric characters or contain slashes.",
                field="symbol"
            )

        return symbol

    @staticmethod
    def validate_price(price: Any, field_name: str = "price") -> Decimal:
        """
        Validate price value.

        Args:
            price: Price value (int, float, or str)
            field_name: Name of the field for error message

        Returns:
            Decimal price value

        Raises:
            ValidationError: If price is invalid
        """
        try:
            price_decimal = Decimal(str(price))
            
            if price_decimal <= 0:
                raise ValidationError(
                    f"Price must be position but got : {price}",
                    field=field_name
                )

            if price_decimal.as_tuple().exponent < -10:
                raise ValidationError(
                    f"{field_name} has too many decimal places",
                    field=field_name
                )

            return price_decimal

        except (ValueError, TypeError):
            raise ValidationError(
                f"{field_name} must be a valid number, got {price}",
                field=field_name
            )

    def validate_signal_type(signal_type: str) -> str:
        """
        Validate signal type.

        Args:
            signal_type: Signal type (BUY, SELL, LONG, SHORT)

        Returns:
            Normalized signal type (uppercase)

        Raises:
            ValidationError: If signal type is invalid
        """
        valid_types = ["BUY", "SELL", "LONG", "SHORT"]
        signal_type = signal_type.upper().strip()

        if signal_type not in valid_types:
            raise ValidationError(
                f"Invalid signal type: {signal_type}. Must be one of: {valid_types}",
                field="signal_type"
            )

        return signal_type


    def validate_price(price: int, field_name: str = "price") -> Decimal:
        """
        Validate price value.

        Args:
            price: Price value (int, float, or str)
            field_name: Name of the field for error message

        Returns:
            Decimal price value

        Raises:
            ValidationError: If price is invalid
        """
        try:
            price_decimal = Decimal(str(price))

            if price_decimal <= 0:
                raise ValidationError(
                    f"{field_name} must be positive, got {price}",
                    field=field_name
                )

            # Check for reasonable precision (max 10 decimal places)
            if price_decimal.as_tuple().exponent < -10:
                raise ValidationError(
                    f"{field_name} has too many decimal places",
                    field=field_name
                )

            return price_decimal
        except (ValueError, TypeError):
            raise ValidationError(
                f"{field_name} must be a valid number, got {price}",
                field=field_name
            )


    @staticmethod
    def validate_signal_type(signal_type: str) -> str:
        """
        Validate signal type.

        Args:
            signal_type: Signal type (BUY, SELL, LONG, SHORT)

        Returns:
            Normalized signal type (uppercase)

        Raises:
            ValidationError: If signal type is invalid
        """
        valid_types = {"BUY", "SELL", "LONG", "SHORT"}
        signal_type = signal_type.upper().strip()

        if signal_type not in valid_types:
            raise ValidationError(
                f"Invalid signal type: {signal_type}. Must be one of {valid_types}",
                field="signal_type"
            )

        return signal_type

    @staticmethod
    def validate_timeframe(timeframe: str) -> str:
        """
        Validate trading timeframe.

        Args:
            timeframe: Timeframe string (5m, 15m, 1h, 4h, 1d, 1w, 1M)

        Returns:
            Normalized timeframe

        Raises:
            ValidationError: If timeframe is invalid
        """
        valid_timeframes = {"5M", "15M", "30M", "1H", "4H", "1D", "1W", "1M"}
        timeframe = timeframe.upper().strip()

        if timeframe not in valid_timeframes:
            raise ValidationError(
                f"Invalid timeframe: {timeframe}. Must be one of {valid_timeframes}",
                field="timeframe"
            )

        return timeframe

    @staticmethod
    def validate_buy_signal(entry: Decimal, stop_loss: Decimal, take_profit: Decimal) -> bool:
        """
        Validate BUY signal logic: entry > SL and TPs > entry.

        Args:
            entry: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            True if valid

        Raises:
            ValidationError: If logic is invalid
        """
        if entry <= stop_loss:
            raise ValidationError(
                f"BUY signal: entry ({entry}) must be greater than stop loss ({stop_loss})"
            )

        if take_profit <= entry:
            raise ValidationError(
                f"BUY signal: take profit ({take_profit}) must be greater than entry ({entry})"
            )

        return True

    @staticmethod
    def validate_sell_signal(entry: Decimal, stop_loss: Decimal, take_profit: Decimal) -> bool:
        """
        Validate SELL signal logic: entry < SL and TPs < entry.

        Args:
            entry: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            True if valid

        Raises:
            ValidationError: If logic is invalid
        """
        if entry >= stop_loss:
            raise ValidationError(
                f"SELL signal: entry ({entry}) must be less than stop loss ({stop_loss})"
            )

        if take_profit >= entry:
            raise ValidationError(
                f"SELL signal: take profit ({take_profit}) must be less than entry ({entry})"
            )

        return True

    @staticmethod
    def validate_risk_reward(
        entry: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        signal_type: str = "BUY"
    ) -> Decimal:
        """
        Calculate and validate risk/reward ratio.

        Args:
            entry: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            signal_type: BUY or SELL

        Returns:
            Risk/reward ratio

        Raises:
            ValidationError: If ratio is invalid or unreasonable
        """
        try:
            if signal_type == "BUY":
                risk = entry - stop_loss
                reward = take_profit - entry
            else:  # SELL
                risk = stop_loss - entry
                reward = entry - take_profit

            if risk <= 0 or reward <= 0:
                raise ValidationError("Risk and reward must be positive")

            ratio = reward / risk
            return Decimal(str(ratio)).quantize(Decimal("0.01"))
        except Exception as e:
            raise ValidationError(f"Failed to calculate risk/reward ratio: {str(e)}")


__all__ = ["Validator"]






