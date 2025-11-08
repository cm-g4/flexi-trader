"""Signal validation service for validating trading signals."""

from decimal import Decimal
from typing import Dict, Tuple, Optional, Any

from app.logging_config import logger
from app.exceptions import ValidationError


class SignalValidator:
    """
    Validates extracted trading signals for data integrity and correctness.
    
    Validates:
    - Price levels (entry, SL, TPs)
    - Signal types (BUY, SELL, LONG, SHORT)
    - Timeframes (5M, 15M, 1H, 4H, 1D, etc.)
    - Risk/Reward ratios
    - Type detection and normalization
    """

    # Valid signal types
    VALID_SIGNAL_TYPES = {"BUY", "SELL", "LONG", "SHORT"}

    # Valid timeframes
    VALID_TIMEFRAMES = {
        "1M", "5M", "15M", "30M",  # Minutes
        "1H", "4H",                 # Hours
        "1D", "1W", "1M",           # Days and larger (note: month)
    }

    def validate_signal_type(self, signal_type: str) -> str:
        """
        Validate and normalize signal type.

        Args:
            signal_type: Signal type string (e.g., "BUY", "buy", "SELL")

        Returns:
            Normalized signal type (uppercase)

        Raises:
            ValidationError: If signal type is invalid
        """
        normalized = signal_type.upper().strip()

        if normalized not in self.VALID_SIGNAL_TYPES:
            raise ValidationError(
                f"Invalid signal type: '{signal_type}'. "
                f"Must be one of: {', '.join(self.VALID_SIGNAL_TYPES)}",
                field="signal_type",
            )

        return normalized

    def validate_timeframe(self, timeframe: str) -> str:
        """
        Validate and normalize timeframe.

        Args:
            timeframe: Timeframe string (e.g., "1H", "1h", "4H")

        Returns:
            Normalized timeframe (uppercase)

        Raises:
            ValidationError: If timeframe is invalid
        """
        normalized = timeframe.upper().strip()

        if normalized not in self.VALID_TIMEFRAMES:
            raise ValidationError(
                f"Invalid timeframe: '{timeframe}'. "
                f"Must be one of: {', '.join(sorted(self.VALID_TIMEFRAMES))}",
                field="timeframe",
            )

        return normalized

    def validate_buy_signal(
        self,
        entry: Decimal,
        stop_loss: Decimal,
        take_profit: Optional[Decimal] = None,
    ) -> bool:
        """
        Validate BUY signal logic.
        
        For BUY: entry > stop_loss AND take_profit > entry (if provided)

        Args:
            entry: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price (optional)

        Returns:
            True if valid

        Raises:
            ValidationError: If logic is invalid
        """
        entry = Decimal(str(entry))
        stop_loss = Decimal(str(stop_loss))

        if entry <= stop_loss:
            raise ValidationError(
                f"BUY signal: entry price ({entry}) must be greater than "
                f"stop loss ({stop_loss})",
                field="price_logic",
            )

        if take_profit is not None:
            take_profit = Decimal(str(take_profit))
            if take_profit <= entry:
                raise ValidationError(
                    f"BUY signal: take profit ({take_profit}) must be greater "
                    f"than entry ({entry})",
                    field="price_logic",
                )

        return True

    def validate_sell_signal(
        self,
        entry: Decimal,
        stop_loss: Decimal,
        take_profit: Optional[Decimal] = None,
    ) -> bool:
        """
        Validate SELL signal logic.
        
        For SELL: entry < stop_loss AND take_profit < entry (if provided)

        Args:
            entry: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price (optional)

        Returns:
            True if valid

        Raises:
            ValidationError: If logic is invalid
        """
        entry = Decimal(str(entry))
        stop_loss = Decimal(str(stop_loss))

        if entry >= stop_loss:
            raise ValidationError(
                f"SELL signal: entry price ({entry}) must be less than "
                f"stop loss ({stop_loss})",
                field="price_logic",
            )

        if take_profit is not None:
            take_profit = Decimal(str(take_profit))
            if take_profit >= entry:
                raise ValidationError(
                    f"SELL signal: take profit ({take_profit}) must be less "
                    f"than entry ({entry})",
                    field="price_logic",
                )

        return True

    def validate_price_levels(
        self,
        entry: Decimal,
        stop_loss: Decimal,
        take_profits: list,
        signal_type: str = "BUY",
    ) -> Tuple[bool, list]:
        """
        Validate all price levels for a signal.

        Args:
            entry: Entry price
            stop_loss: Stop loss price
            take_profits: List of take profit prices
            signal_type: BUY or SELL

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        try:
            if signal_type == "BUY":
                self.validate_buy_signal(entry, stop_loss)
            else:
                self.validate_sell_signal(entry, stop_loss)
        except ValidationError as e:
            errors.append(str(e))
            return False, errors

        # Validate each take profit
        for idx, tp in enumerate(take_profits, start=1):
            try:
                tp_price = tp.get("price") if isinstance(tp, dict) else tp
                if signal_type == "BUY":
                    self.validate_buy_signal(entry, stop_loss, tp_price)
                else:
                    self.validate_sell_signal(entry, stop_loss, tp_price)
            except ValidationError as e:
                errors.append(f"TP{idx}: {str(e)}")

        return len(errors) == 0, errors

    def calculate_risk_reward_ratio(
        self,
        entry: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        signal_type: str = "BUY",
    ) -> Decimal:
        """
        Calculate risk/reward ratio for a signal.

        Args:
            entry: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            signal_type: BUY or SELL

        Returns:
            Risk/Reward ratio as Decimal

        Raises:
            ValidationError: If calculation fails
        """
        try:
            entry = Decimal(str(entry))
            stop_loss = Decimal(str(stop_loss))
            take_profit = Decimal(str(take_profit))

            if signal_type == "BUY":
                risk = entry - stop_loss
                reward = take_profit - entry
            else:  # SELL
                risk = stop_loss - entry
                reward = entry - take_profit

            if risk <= 0:
                raise ValidationError("Risk must be positive (entry != stop loss)")

            if reward <= 0:
                raise ValidationError("Reward must be positive")

            ratio = reward / risk
            return ratio.quantize(Decimal("0.01"))

        except Exception as e:
            raise ValidationError(
                f"Failed to calculate risk/reward ratio: {str(e)}",
                field="risk_reward",
            )

    def detect_signal_type(self, message: str) -> Optional[str]:
        """
        Detect signal type from message text.

        Args:
            message: Message text

        Returns:
            Detected signal type (BUY, SELL, LONG, SHORT) or None

        Raises:
            ValidationError: If multiple conflicting types detected
        """
        message_upper = message.upper()
        detected_types = []

        # Check for each signal type
        if "BUY" in message_upper:
            detected_types.append("BUY")

        if "SELL" in message_upper:
            detected_types.append("SELL")

        if "LONG" in message_upper and "BUY" not in detected_types:
            detected_types.append("LONG")

        if "SHORT" in message_upper and "SELL" not in detected_types:
            detected_types.append("SHORT")

        # Check for conflicts
        if len(detected_types) > 1:
            logger.warning(
                f"Multiple signal types detected: {detected_types}. "
                f"Using first: {detected_types[0]}"
            )

        return detected_types[0] if detected_types else None

    def detect_timeframe(self, message: str) -> Optional[str]:
        """
        Detect trading timeframe from message text.

        Args:
            message: Message text

        Returns:
            Detected timeframe or None

        Raises:
            None - returns None if no timeframe detected
        """
        import re

        # Pattern to match timeframes
        # Matches: 5m, 5M, 5min, 15M, 1H, 4H, 1D, 1d, etc.
        pattern = r"\b(\d+(?:M|H|D|W|m|h|d|w)(?:in)?)\b"
        matches = re.findall(pattern, message)

        if not matches:
            return None

        # Take the first match and normalize
        detected = matches[0].upper()

        # Normalize minute notation
        if "MIN" in detected:
            detected = detected.replace("MIN", "M")

        try:
            return self.validate_timeframe(detected)
        except ValidationError:
            logger.debug(f"Detected timeframe '{detected}' is invalid")
            return None

    def validate_symbol(self, symbol: str) -> str:
        """
        Validate and normalize trading symbol.

        Args:
            symbol: Trading symbol (e.g., "EURUSD", "XAU/USD")

        Returns:
            Normalized symbol (uppercase, no slashes)

        Raises:
            ValidationError: If symbol is empty or too long
        """
        if not symbol:
            raise ValidationError("Symbol cannot be empty", field="symbol")

        # Remove slashes and normalize
        normalized = symbol.upper().replace("/", "").strip()

        if len(normalized) < 3:
            raise ValidationError(
                f"Symbol '{symbol}' is too short (minimum 3 characters)",
                field="symbol",
            )

        if len(normalized) > 20:
            raise ValidationError(
                f"Symbol '{symbol}' is too long (maximum 20 characters)",
                field="symbol",
            )

        return normalized

    def validate_price(self, price: Any, field_name: str = "price") -> Decimal:
        """
        Validate and convert price to Decimal.

        Args:
            price: Price value (can be string, int, float, Decimal)
            field_name: Field name for error messages

        Returns:
            Price as Decimal

        Raises:
            ValidationError: If price is invalid
        """
        try:
            price_decimal = Decimal(str(price))

            if price_decimal <= 0:
                raise ValidationError(
                    f"{field_name} must be positive (got {price})",
                    field=field_name,
                )

            if price_decimal > Decimal("1000000"):  # Sanity check
                logger.warning(
                    f"Large price detected: {price_decimal} for {field_name}"
                )

            return price_decimal

        except (ValueError, TypeError) as e:
            raise ValidationError(
                f"Invalid {field_name}: '{price}' is not a valid number",
                field=field_name,
            )

    def validate_partial_signal(
        self, data: Dict[str, Any]
    ) -> Tuple[bool, list]:
        """
        Validate a potentially partial signal (with missing optional fields).

        Args:
            data: Extracted signal data

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Required fields
        if not data.get("symbol"):
            errors.append("Missing required field: symbol")

        if not data.get("entry_price"):
            errors.append("Missing required field: entry_price")

        # Optional but recommended
        if not data.get("stop_loss"):
            logger.debug("Signal missing stop loss")

        if not data.get("take_profits"):
            logger.debug("Signal missing take profits")

        return len(errors) == 0, errors


__all__ = ["SignalValidator"]