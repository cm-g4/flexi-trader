"""Parser engine for extracting trading signals from messages using templates."""

from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID
from decimal import Decimal
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import Template, Signal, Channel, Message
from app.exceptions import ExtractionError, ValidationError, TemplateError
from app.services.extraction_engine import ExtractionEngine
from app.services.signal_validator import SignalValidator


class ParserEngine:
    """
    Main parser engine that orchestrates signal extraction from Telegram messages.
    
    Responsibilities:
    1. Template matching - determine which template(s) to apply
    2. Message parsing - extract fields using template extraction config
    3. Signal validation - validate extracted data
    4. Signal creation - create Signal objects from validated data
    5. Error handling - log and handle extraction failures
    """

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize parser engine.

        Args:
            db: Database session (optional)
        """
        self.db = db
        self.extraction_engine = ExtractionEngine()
        self.signal_validator = SignalValidator()

    def parse_message(
        self,
        message: Message,
        channel_id: UUID,
        user_id: str,
        session: Session,
    ) -> Tuple[Optional[Signal], Optional[str]]:
        """
        Parse a message to extract a trading signal.

        Args:
            message: Message object from database
            channel_id: Channel ID
            user_id: User ID
            session: Database session

        Returns:
            Tuple of (Signal object or None, error_message or None)
        """
        try:
            # Step 1: Get applicable templates for this channel
            templates = self._get_applicable_templates(channel_id, session)
            
            if not templates:
                error_msg = f"No active templates found for channel {channel_id}"
                logger.warning(error_msg)
                return None, error_msg

            # Step 2: Try each template until one succeeds
            for template in templates:
                try:
                    signal = self._extract_from_template(
                        message=message,
                        template=template,
                        channel_id=channel_id,
                        user_id=user_id,
                        session=session,
                    )
                    
                    if signal:
                        logger.info(
                            f"Successfully extracted signal: {signal.symbol} "
                            f"from message {message.id} using template {template.id}"
                        )
                        return signal, None
                        
                except Exception as e:
                    logger.debug(
                        f"Template {template.id} failed: {str(e)}. "
                        f"Trying next template..."
                    )
                    continue

            # No template succeeded
            error_msg = f"No template successfully extracted signal from message {message.id}"
            logger.warning(error_msg)
            return None, error_msg

        except Exception as e:
            error_msg = f"Parser error: {str(e)}"
            logger.error(error_msg)
            return None, error_msg

    def _get_applicable_templates(
        self,
        channel_id: UUID,
        session: Session,
    ) -> List[Template]:
        """
        Get applicable templates for a channel, ordered by priority.

        Args:
            channel_id: Channel ID
            session: Database session

        Returns:
            List of active templates, ordered by priority
        """
        templates = (
            session.query(Template)
            .filter(
                Template.channel_id == channel_id,
                Template.is_active == True,
            )
            .all()
        )

        # Sort by priority (higher priority first)
        # Priority is stored in extraction_config['priority']
        def get_priority(template: Template) -> int:
            try:
                return template.extraction_config.get("priority", 0)
            except:
                return 0

        return sorted(templates, key=get_priority, reverse=True)

    def _extract_from_template(
        self,
        message: Message,
        template: Template,
        channel_id: UUID,
        user_id: str,
        session: Session,
    ) -> Optional[Signal]:
        """
        Extract signal using a specific template.

        Args:
            message: Message to extract from
            template: Template to use
            channel_id: Channel ID
            user_id: User ID
            session: Database session

        Returns:
            Signal object or None if extraction fails
        """
        # Step 1: Extract all fields from message
        extracted_data, errors = self.extraction_engine.extract_all_fields(
            message.text,
            template.extraction_config,
        )

        if errors:
            logger.debug(f"Extraction errors: {errors}")
            raise ExtractionError(f"Extraction failed: {', '.join(errors)}")

        if not extracted_data:
            raise ExtractionError("No data extracted from message")

        # Step 2: Validate extracted data
        validated_data = self._validate_extracted_data(extracted_data)

        # Step 3: Create Signal object
        signal = self._create_signal_from_data(
            validated_data=validated_data,
            message=message,
            template=template,
            channel_id=channel_id,
            user_id=user_id,
        )

        return signal

    def _validate_extracted_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate extracted data.

        Args:
            extracted_data: Dictionary of extracted fields

        Returns:
            Validated and normalized data

        Raises:
            ValidationError: If validation fails
        """
        # Required fields
        if not extracted_data.get("symbol"):
            raise ValidationError("Symbol is required", field="symbol")

        if "entry_price" not in extracted_data:
            raise ValidationError("Entry price is required", field="entry_price")

        # Validate signal type if present
        signal_type = extracted_data.get("signal_type", "BUY").upper()
        try:
            validated_type = self.signal_validator.validate_signal_type(signal_type)
            extracted_data["signal_type"] = validated_type
        except ValidationError:
            logger.debug(f"Invalid signal type '{signal_type}', defaulting to BUY")
            extracted_data["signal_type"] = "BUY"

        # Validate timeframe if present
        if extracted_data.get("timeframe"):
            try:
                validated_tf = self.signal_validator.validate_timeframe(
                    extracted_data["timeframe"]
                )
                extracted_data["timeframe"] = validated_tf
            except ValidationError:
                logger.debug("Invalid timeframe, removing")
                extracted_data.pop("timeframe", None)

        # Validate price levels
        entry = Decimal(str(extracted_data.get("entry_price", 0)))
        stop_loss = extracted_data.get("stop_loss")
        take_profits = extracted_data.get("take_profits", [])

        signal_type = extracted_data.get("signal_type", "BUY")

        if stop_loss:
            stop_loss = Decimal(str(stop_loss))
            try:
                if signal_type == "BUY":
                    self.signal_validator.validate_buy_signal(
                        entry, stop_loss, entry  # dummy TP for validation
                    )
                else:
                    self.signal_validator.validate_sell_signal(
                        entry, stop_loss, entry
                    )
            except ValidationError as e:
                logger.warning(f"Price validation failed: {e}")
                # Don't fail on validation - signal may have partial data
                pass

        return extracted_data

    def _create_signal_from_data(
        self,
        validated_data: Dict[str, Any],
        message: Message,
        template: Template,
        channel_id: UUID,
        user_id: str,
    ) -> Signal:
        """
        Create a Signal object from validated extracted data.

        Args:
            validated_data: Validated extracted data
            message: Original message
            template: Template used
            channel_id: Channel ID
            user_id: User ID

        Returns:
            Signal object
        """
        entry_price = Decimal(str(validated_data["entry_price"]))
        stop_loss = validated_data.get("stop_loss")
        take_profits_data = validated_data.get("take_profits", [])

        # Normalize take profits to list of dicts
        take_profits = self._normalize_take_profits(take_profits_data)

        # Normalize stop loss
        if stop_loss:
            stop_loss = {
                "price": Decimal(str(stop_loss)),
                "hit": False,
                "hit_at": None,
            }

        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(validated_data)

        # Create signal object
        signal = Signal(
            channel_id=channel_id,
            template_id=template.id,
            user_id=user_id,
            original_message_id=message.telegram_message_id,
            original_message_text=message.text,
            symbol=validated_data["symbol"].upper(),
            entry_price=entry_price,
            take_profits=take_profits,
            stop_loss=stop_loss,
            signal_type=validated_data.get("signal_type", "BUY"),
            timeframe=validated_data.get("timeframe"),
            status="PENDING",
            confidence_score=confidence_score,
            extraction_metadata={
                "template_id": str(template.id),
                "template_name": template.name,
                "extraction_method": "template_based",
                "extracted_fields": list(validated_data.keys()),
            },
        )

        return signal

    def _normalize_take_profits(
        self, take_profits_data: Any
    ) -> List[Dict[str, Any]]:
        """
        Normalize take profits to standard format.

        Args:
            take_profits_data: Raw take profits data

        Returns:
            List of normalized TP dicts
        """
        if not take_profits_data:
            return []

        normalized = []

        # Handle single value
        if isinstance(take_profits_data, (int, float, Decimal, str)):
            normalized.append({
                "level": "TP1",
                "price": Decimal(str(take_profits_data)),
                "hit": False,
                "hit_at": None,
            })
        # Handle list of values
        elif isinstance(take_profits_data, list):
            for idx, tp in enumerate(take_profits_data, start=1):
                if isinstance(tp, dict):
                    normalized.append({
                        "level": tp.get("level", f"TP{idx}"),
                        "price": Decimal(str(tp.get("price", 0))),
                        "hit": tp.get("hit", False),
                        "hit_at": tp.get("hit_at"),
                    })
                else:
                    normalized.append({
                        "level": f"TP{idx}",
                        "price": Decimal(str(tp)),
                        "hit": False,
                        "hit_at": None,
                    })

        return normalized

    def _calculate_confidence_score(self, data: Dict[str, Any]) -> Decimal:
        """
        Calculate confidence score based on data completeness and quality.

        Args:
            data: Extracted and validated data

        Returns:
            Confidence score (0-1)
        """
        score = Decimal("1.0")

        # Deduct for missing optional fields
        if not data.get("stop_loss"):
            score -= Decimal("0.15")

        if not data.get("take_profits"):
            score -= Decimal("0.15")

        if not data.get("timeframe"):
            score -= Decimal("0.05")

        if not data.get("signal_type") or data.get("signal_type") == "BUY":
            score -= Decimal("0.05")

        # Ensure score is between 0 and 1
        score = max(Decimal("0"), min(Decimal("1"), score))

        return score

    def parse_batch(
        self,
        messages: List[Message],
        channel_id: UUID,
        user_id: str,
        session: Session,
    ) -> Tuple[List[Signal], Dict[str, Any]]:
        """
        Parse multiple messages and return batch statistics.

        Args:
            messages: List of messages to parse
            channel_id: Channel ID
            user_id: User ID
            session: Database session

        Returns:
            Tuple of (list of signals, statistics dict)
        """
        signals = []
        stats = {
            "total_messages": len(messages),
            "successful_extractions": 0,
            "failed_extractions": 0,
            "errors": [],
        }

        for message in messages:
            signal, error = self.parse_message(
                message=message,
                channel_id=channel_id,
                user_id=user_id,
                session=session,
            )

            if signal:
                signals.append(signal)
                stats["successful_extractions"] += 1
            else:
                stats["failed_extractions"] += 1
                if error:
                    stats["errors"].append(error)

        return signals, stats


__all__ = ["ParserEngine"]