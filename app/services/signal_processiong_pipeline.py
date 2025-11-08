"""Signal processing pipeline - orchestrates message to signal conversion."""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from uuid import UUID
from decimal import Decimal
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import Message, Signal, Channel
from app.exceptions import (
    ValidationError,
    DuplicateSignalError,
    RateLimitError,
)
from app.services.parser_engine import ParserEngine
from app.services.duplicate_detection import DuplicateDetectionService
from app.services.rate_limiter import RateLimiterService


class SignalProcessingPipeline:
    """
    Main signal processing pipeline that orchestrates the complete flow:
    
    Message → Duplicate Check → Extraction → Validation → Storage
    
    With comprehensive error handling, logging, and rate limiting.
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        rate_limiter: Optional[RateLimiterService] = None,
    ):
        """
        Initialize signal processing pipeline.

        Args:
            db: Database session
            rate_limiter: Rate limiter service (optional)
        """
        self.db = db
        self.parser_engine = ParserEngine(db=db)
        self.duplicate_detector = DuplicateDetectionService()
        self.rate_limiter = rate_limiter

    def process_message(
        self,
        message: Message,
        session: Session,
        check_duplicates: bool = True,
        check_rate_limit: bool = True,
    ) -> Tuple[Optional[Signal], Dict[str, Any]]:
        """
        Process a single message through the complete pipeline.

        Args:
            message: Message to process
            session: Database session
            check_duplicates: Whether to check for duplicates
            check_rate_limit: Whether to apply rate limiting

        Returns:
            Tuple of (Signal object or None, result dictionary with status and metadata)
        """
        result = {
            "status": "pending",
            "message_id": message.id,
            "telegram_message_id": message.telegram_message_id,
            "channel_id": str(message.channel_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "steps": {},
            "signal": None,
            "error": None,
            "error_stage": None,
        }

        try:
            # Step 1: Rate limiting check
            if check_rate_limit and self.rate_limiter:
                try:
                    self._check_rate_limit(message.channel_id, session)
                    result["steps"]["rate_limit"] = "passed"
                except RateLimitError as e:
                    result["status"] = "rate_limited"
                    result["error"] = str(e)
                    result["error_stage"] = "rate_limit"
                    logger.warning(f"Rate limit exceeded: {e}")
                    return None, result

            # Step 2: Duplicate detection
            if check_duplicates:
                try:
                    self._check_duplicate(message, session)
                    result["steps"]["duplicate_check"] = "passed"
                except DuplicateSignalError as e:
                    result["status"] = "duplicate_detected"
                    result["error"] = str(e)
                    result["error_stage"] = "duplicate_check"
                    logger.debug(f"Duplicate detected: {e}")
                    return None, result

            # Step 3: Extract signal using parser engine
            signal, extraction_error = self.parser_engine.parse_message(
                message=message,
                channel_id=message.channel_id,
                user_id=message.telegram_sender_id,
                session=session,
            )

            if extraction_error:
                result["steps"]["extraction"] = "failed"
                result["error"] = extraction_error
                result["error_stage"] = "extraction"
                logger.debug(f"Extraction failed: {extraction_error}")
                return None, result

            result["steps"]["extraction"] = "success"

            # Step 4: Validate extracted signal
            try:
                self._validate_signal(signal)
                result["steps"]["validation"] = "passed"
            except ValidationError as e:
                result["status"] = "validation_failed"
                result["error"] = str(e)
                result["error_stage"] = "validation"
                logger.debug(f"Signal validation failed: {e}")
                return None, result

            # Step 5: Persist signal and mark message
            try:
                signal = self._persist_signal(signal, message, session)
                result["status"] = "success"
                result["signal"] = self._signal_to_dict(signal)
                result["steps"]["persistence"] = "success"

                # Mark message as successfully processed
                message.is_signal = True
                message.extracted_signal_id = signal.id
                session.commit()

                logger.info(
                    f"Successfully processed signal: {signal.symbol} "
                    f"from message {message.id}"
                )

            except Exception as e:
                result["status"] = "persistence_failed"
                result["error"] = str(e)
                result["error_stage"] = "persistence"
                logger.error(f"Failed to persist signal: {e}")
                session.rollback()
                return None, result

            return signal, result

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["error_stage"] = "unknown"
            logger.error(f"Pipeline error: {e}")
            return None, result

    def process_batch(
        self,
        messages: List[Message],
        session: Session,
        check_duplicates: bool = True,
        check_rate_limit: bool = True,
    ) -> Dict[str, Any]:
        """
        Process multiple messages through the pipeline.

        Args:
            messages: List of messages to process
            session: Database session
            check_duplicates: Whether to check for duplicates
            check_rate_limit: Whether to apply rate limiting

        Returns:
            Batch result dictionary with statistics
        """
        batch_result = {
            "total_messages": len(messages),
            "successful_signals": 0,
            "failed_messages": 0,
            "duplicates_detected": 0,
            "rate_limited": 0,
            "signals": [],
            "errors": [],
            "start_time": datetime.now(timezone.utc).isoformat(),
            "statistics": {},
        }

        for message in messages:
            signal, result = self.process_message(
                message=message,
                session=session,
                check_duplicates=check_duplicates,
                check_rate_limit=check_rate_limit,
            )

            if signal:
                batch_result["successful_signals"] += 1
                batch_result["signals"].append(self._signal_to_dict(signal))
            else:
                batch_result["failed_messages"] += 1
                batch_result["errors"].append(result)

                if result["status"] == "duplicate_detected":
                    batch_result["duplicates_detected"] += 1
                elif result["status"] == "rate_limited":
                    batch_result["rate_limited"] += 1

        batch_result["end_time"] = datetime.now(timezone.utc).isoformat()

        # Calculate statistics
        batch_result["statistics"] = {
            "success_rate": (
                batch_result["successful_signals"] / len(messages) * 100
                if messages
                else 0
            ),
            "failure_rate": (
                batch_result["failed_messages"] / len(messages) * 100
                if messages
                else 0
            ),
            "duplicate_rate": (
                batch_result["duplicates_detected"] / len(messages) * 100
                if messages
                else 0
            ),
        }

        logger.info(
            f"Batch processing complete: {batch_result['successful_signals']}/"
            f"{batch_result['total_messages']} signals extracted"
        )

        return batch_result

    def _check_rate_limit(self, channel_id: UUID, session: Session) -> None:
        """
        Check rate limiting for a channel.

        Args:
            channel_id: Channel ID
            session: Database session

        Raises:
            RateLimitError: If rate limit exceeded
        """
        if not self.rate_limiter:
            return

        # Check per-channel rate limit
        if not self.rate_limiter.check_rate_limit(
            key=f"channel:{channel_id}",
            max_requests=100,
            time_window=60,
        ):
            raise RateLimitError(
                f"Rate limit exceeded for channel {channel_id}",
                retry_after=60,
            )

    def _check_duplicate(self, message: Message, session: Session) -> None:
        """
        Check for duplicate messages.

        Args:
            message: Message to check
            session: Database session

        Raises:
            DuplicateSignalError: If duplicate detected
        """
        self.duplicate_detector.detect_or_raise(
            session=session,
            message=message,
            channel_id=message.channel_id,
        )

    def _validate_signal(self, signal: Signal) -> None:
        """
        Validate signal data.

        Args:
            signal: Signal to validate

        Raises:
            ValidationError: If validation fails
        """
        if not signal.symbol:
            raise ValidationError("Signal missing symbol", field="symbol")

        if not signal.entry_price or signal.entry_price <= 0:
            raise ValidationError(
                "Signal missing or invalid entry price",
                field="entry_price",
            )

        if signal.signal_type not in {"BUY", "SELL", "LONG", "SHORT"}:
            raise ValidationError(
                f"Invalid signal type: {signal.signal_type}",
                field="signal_type",
            )

    def _persist_signal(
        self,
        signal: Signal,
        message: Message,
        session: Session,
    ) -> Signal:
        """
        Persist signal to database.

        Args:
            signal: Signal object to persist
            message: Original message
            session: Database session

        Returns:
            Persisted signal object

        Raises:
            Exception: If persistence fails
        """
        session.add(signal)
        session.flush()  # Flush to get the ID

        # Update channel stats
        channel = session.query(Channel).filter_by(id=message.channel_id).first()
        if channel:
            channel.signal_count = (channel.signal_count or 0) + 1
            channel.last_signal_at = datetime.now(timezone.utc)

        session.commit()
        return signal

    def _signal_to_dict(self, signal: Signal) -> Dict[str, Any]:
        """
        Convert Signal object to dictionary.

        Args:
            signal: Signal object

        Returns:
            Dictionary representation
        """
        return {
            "id": str(signal.id),
            "symbol": signal.symbol,
            "entry_price": str(signal.entry_price),
            "stop_loss": signal.stop_loss,
            "take_profits": signal.take_profits,
            "signal_type": signal.signal_type,
            "timeframe": signal.timeframe,
            "status": signal.status,
            "confidence_score": float(signal.confidence_score),
            "created_at": signal.created_at.isoformat(),
        }

    def get_pipeline_stats(self, session: Session) -> Dict[str, Any]:
        """
        Get pipeline statistics.

        Args:
            session: Database session

        Returns:
            Statistics dictionary
        """
        total_signals = session.query(Signal).count()
        pending_signals = session.query(Signal).filter_by(status="PENDING").count()
        
        return {
            "total_signals_processed": total_signals,
            "pending_signals": pending_signals,
            "signal_extraction_success_rate": (
                self._calculate_success_rate(session) * 100
            ),
        }

    def _calculate_success_rate(self, session: Session) -> float:
        """
        Calculate signal extraction success rate.

        Args:
            session: Database session

        Returns:
            Success rate (0-1)
        """
        from app.models import Message

        total_messages = session.query(Message).count()
        if total_messages == 0:
            return 0.0

        signal_messages = (
            session.query(Message).filter_by(is_signal=True).count()
        )

        return signal_messages / total_messages


__all__ = ["SignalProcessingPipeline"]