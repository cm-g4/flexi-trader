"""Message processor service for processing received Telegram messages."""

from typing import Optional

from app.logging_config import logger
from app.models import Message, Channel
from app.services.rate_limiter import RateLimiterService
from app.database import SessionLocal


class MessageProcessorService:
    """
    Process messages received from Telegram.
    
    Responsibilities:
    - Rate limiting checks
    - Message validation
    - Status updates
    - Error handling
    - Logging
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimiterService] = None,
        session_factory=SessionLocal,
    ):
        """
        Initialize message processor.
        
        Args:
            rate_limiter: Rate limiter service instance
            session_factory: Database session factory
        """
        self.rate_limiter = rate_limiter
        self.session_factory = session_factory

    def process_message(self, message: Message) -> bool:
        """
        Process a received message.
        
        Args:
            message: Message to process
            
        Returns:
            True if successful, False otherwise
        """
        session = self.session_factory()
        try:
            logger.info(f"Processing message: id={message.id}")
            
            # Get channel
            channel = session.query(Channel).filter_by(id=message.channel_id).first()
            if not channel:
                logger.error(f"Channel not found: {message.channel_id}")
                return False
            
            # Check rate limits if configured
            if self.rate_limiter:
                user_id = str(message.telegram_sender_id) if message.telegram_sender_id else None
                is_allowed, reason = self.rate_limiter.check_all_limits(
                    str(message.channel_id), user_id
                )
                if not is_allowed:
                    logger.warning(f"Rate limit exceeded: {reason}")
                    return False
                
                # Record the message
                self.rate_limiter.record_message(str(message.channel_id), user_id)
            
            # Update message status
            message.mark_as_processed()
            session.add(message)
            session.commit()
            
            logger.info(f"Message processed successfully: id={message.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            session.rollback()
            return False
        finally:
            session.close()


__all__ = ["MessageProcessorService"]