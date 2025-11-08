"""Extraction history tracking and logging service."""

from typing import Dict, Optional, Any
from uuid import UUID
from datetime import datetime, timezone
import logging

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.logging_config import logger
from app.models import ExtractionHistory

logger = logging.getLogger(__name__)


class ExtractionHistoryService:
    """
    Service for tracking and logging signal extraction attempts.
    
    Stores information about:
    - Each extraction attempt
    - Success/failure status
    - Errors encountered
    - Template used
    - Confidence scores
    """

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize extraction history service.
        
        Args:
            db: Database session (optional, will create if not provided)
        """
        self.db = db or SessionLocal()

    def log_extraction_attempt(
        self,
        channel_id: UUID,
        message_id: Optional[int],
        sender_id: Optional[int],
        message: str,
        template_id: Optional[UUID],
        success: bool,
        extracted_data: Optional[Dict[str, Any]] = None,
        errors: Optional[list] = None,
        confidence_score: float = 0.0,
    ) -> Optional[UUID]:
        """
        Log an extraction attempt.
        
        Args:
            channel_id: Source channel UUID
            message_id: Telegram message ID
            sender_id: Telegram user ID
            message: Raw message text
            template_id: Template used (if any)
            success: Whether extraction succeeded
            extracted_data: Extracted signal data (if successful)
            errors: List of errors (if failed)
            confidence_score: Confidence score of extraction
            
        Returns:
            ID of created ExtractionHistory record
        """
        try:
            history = ExtractionHistory(
                channel_id=channel_id,
                message_id=message_id,
                sender_id=sender_id,
                message_text=message[:2000],  # Limit message length in DB
                template_id=template_id,
                success=success,
                extracted_data=extracted_data or {},
                errors=errors or [],
                confidence_score=confidence_score,
                created_at=datetime.now(timezone.utc),
            )
            
            self.db.add(history)
            self.db.commit()
            
            logger.info(
                f"Logged extraction attempt for channel {channel_id}: "
                f"success={success}, confidence={confidence_score:.2f}"
            )
            
            return history.id
            
        except Exception as e:
            logger.error(f"Error logging extraction history: {e}")
            self.db.rollback()
            return None

    def get_extraction_stats(
        self,
        channel_id: Optional[UUID] = None,
        template_id: Optional[UUID] = None,
        limit_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get extraction statistics for a channel or template.
        
        Args:
            channel_id: Channel UUID (optional)
            template_id: Template UUID (optional)
            limit_days: Only include records from last N days
            
        Returns:
            Dictionary with statistics
        """
        from datetime import timedelta
        
        try:
            query = self.db.query(ExtractionHistory)
            
            # Apply filters
            if channel_id:
                query = query.filter(ExtractionHistory.channel_id == channel_id)
            
            if template_id:
                query = query.filter(ExtractionHistory.template_id == template_id)
            
            # Time filter
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=limit_days)
            query = query.filter(ExtractionHistory.created_at >= cutoff_date)
            
            records = query.all()
            
            if not records:
                return {
                    "total_attempts": 0,
                    "successful_extractions": 0,
                    "failed_extractions": 0,
                    "success_rate": 0.0,
                    "average_confidence": 0.0,
                }
            
            # Calculate stats
            total = len(records)
            successful = len([r for r in records if r.success])
            failed = total - successful
            success_rate = (successful / total * 100) if total > 0 else 0
            avg_confidence = sum(r.confidence_score for r in records) / total
            
            return {
                "total_attempts": total,
                "successful_extractions": successful,
                "failed_extractions": failed,
                "success_rate": success_rate,
                "average_confidence": avg_confidence,
                "period_days": limit_days,
            }
            
        except Exception as e:
            logger.error(f"Error calculating extraction stats: {e}")
            return {}

    def get_common_errors(
        self,
        channel_id: Optional[UUID] = None,
        limit_days: int = 30,
        top_n: int = 10,
    ) -> list:
        """
        Get most common extraction errors.
        
        Args:
            channel_id: Channel UUID (optional)
            limit_days: Only include records from last N days
            top_n: Number of top errors to return
            
        Returns:
            List of tuples (error_message, count)
        """
        from datetime import timedelta
        from collections import Counter
        
        try:
            query = self.db.query(ExtractionHistory).filter(
                ExtractionHistory.success == False
            )
            
            if channel_id:
                query = query.filter(ExtractionHistory.channel_id == channel_id)
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=limit_days)
            query = query.filter(ExtractionHistory.created_at >= cutoff_date)
            
            records = query.all()
            
            # Flatten errors
            all_errors = []
            for record in records:
                if record.errors:
                    all_errors.extend(record.errors)
            
            # Count and sort
            error_counts = Counter(all_errors)
            
            return error_counts.most_common(top_n)
            
        except Exception as e:
            logger.error(f"Error getting common errors: {e}")
            return []

    def cleanup_old_records(
        self,
        days_to_keep: int = 90,
    ) -> int:
        """
        Delete old extraction history records.
        
        Args:
            days_to_keep: Keep records from last N days
            
        Returns:
            Number of records deleted
        """
        from datetime import timedelta
        
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            
            deleted = self.db.query(ExtractionHistory).filter(
                ExtractionHistory.created_at < cutoff_date
            ).delete()
            
            self.db.commit()
            
            logger.info(f"Deleted {deleted} old extraction history records")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error cleaning up old records: {e}")
            self.db.rollback()
            return 0


class ErrorHandler:
    """Centralized error handling for parsing and extraction."""
    
    @staticmethod
    def handle_extraction_error(
        error: Exception,
        message: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle an extraction error.
        
        Args:
            error: The exception that occurred
            message: Original message being processed
            context: Context dictionary with channel_id, template_id, etc.
            
        Returns:
            Error details dictionary
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        error_details = {
            "error_type": error_type,
            "error_message": error_message,
            "context": context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_length": len(message) if message else 0,
        }
        
        logger.error(f"Extraction error: {error_type} - {error_message}", exc_info=True)
        
        return error_details

    @staticmethod
    def handle_validation_error(
        errors: list,
        warnings: list,
        signal: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle validation errors/warnings.
        
        Args:
            errors: List of critical errors
            warnings: List of non-critical warnings
            signal: The signal being validated
            
        Returns:
            Validation result dictionary
        """
        result = {
            "is_valid": len(errors) == 0,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "signal_summary": {
                "symbol": signal.get("symbol"),
                "entry_price": signal.get("entry_price"),
                "stop_loss": signal.get("stop_loss"),
                "signal_type": signal.get("signal_type"),
            }
        }
        
        if not result["is_valid"]:
            logger.warning(
                f"Signal validation failed: {len(errors)} errors, "
                f"{len(warnings)} warnings"
            )
        elif result["warning_count"] > 0:
            logger.info(f"Signal validation passed with {len(warnings)} warnings")
        
        return result

    @staticmethod
    def handle_rate_limit_exceeded(
        channel_id: UUID,
        current_count: int,
        limit: int,
        time_window: str,
    ) -> Dict[str, Any]:
        """
        Handle rate limit exceeded situation.
        
        Args:
            channel_id: Channel UUID
            current_count: Current message count
            limit: Rate limit
            time_window: Time window (e.g., 'per minute', 'per hour')
            
        Returns:
            Rate limit details
        """
        details = {
            "channel_id": str(channel_id),
            "current_count": current_count,
            "limit": limit,
            "time_window": time_window,
            "exceeded_by": current_count - limit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        logger.warning(
            f"Rate limit exceeded for channel {channel_id}: "
            f"{current_count} {time_window} (limit: {limit})"
        )
        
        return details

    @staticmethod
    def handle_duplicate_detected(
        channel_id: UUID,
        new_signal: Dict[str, Any],
        duplicate_signal_id: UUID,
    ) -> Dict[str, Any]:
        """
        Handle duplicate signal detection.
        
        Args:
            channel_id: Channel UUID
            new_signal: New signal data
            duplicate_signal_id: ID of matching existing signal
            
        Returns:
            Duplicate detection details
        """
        details = {
            "channel_id": str(channel_id),
            "duplicate_signal_id": str(duplicate_signal_id),
            "new_signal_summary": {
                "symbol": new_signal.get("symbol"),
                "entry_price": new_signal.get("entry_price"),
                "stop_loss": new_signal.get("stop_loss"),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "signal_skipped",
        }
        
        logger.info(
            f"Duplicate signal detected for channel {channel_id}: "
            f"matches {duplicate_signal_id}"
        )
        
        return details


__all__ = [
    "ExtractionHistoryService",
    "ErrorHandler",
]