"""Database models for signal storage."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Signal(Base):
    """Signal model for storing extracted trading signals."""   

    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)
    user_id = Column(String(50), nullable=False)

    # Original message reference
    original_message_id = Column(Integer, nullable=True)
    original_message_text = Column(Text, nullable=False)

    # Trading information
    symbol = Column(String(50), nullable=False, index=True)
    entry_price = Column(Numeric(20, 8), nullable=False)

    # Take profits (as JSON)
    # Format: [{"level": "TP1", "price": 1.1000, "hit": false, "hit_at": null}, ...]
    take_profits = Column(JSON, nullable=True, default=list)  

    # Stop loss (as JSON)
    stop_loss = Column(JSON, nullable=True, default=list)  

    # Signal details
    signal_type = Column(String(10), nullable=False) # BUY, SELL, LONG, SHORT
    timeframe = Column(String(10), nullable=True) # 1M, 5M, 15M, 30M, 1H, 4H, 1D
    status = Column(String(10), nullable=False, default="PENDING") # PENDING, FILLED, CANCELLED, EXPIRED
    
    # Confidence and metadata
    confidence_score = Column(Numeric(3, 2), default=1.0, nullable=False)  
    extraction_metadata = Column(JSON, nullable=True)
    risk_reward_ratio = Column(Numeric(5, 2), nullable=True)

    # Tracking
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )

    # User notes and performance tracking
    user_notes = Column(Text, nullable=True)
    
    # Performance data
    performance_outcome = Column(String(20), nullable=True)  # WIN, LOSS, PENDING
    close_price = Column(Numeric(20, 8), nullable=True)
    pnl = Column(Numeric(20, 8), nullable=True)
    pnl_percent = Column(Numeric(10, 2), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    channel = relationship("Channel", back_populates="signals")
    template = relationship("Template", foreign_keys=[template_id])

    def __repr__(self) -> str:
        return (
            f"<Signal(id={self.id}, symbol={self.symbol}, entry={self.entry_price}, "
            f"type={self.signal_type}, status={self.status})>"
        )

    def get_risk_reward_ratio(self) -> Decimal:
        """Calculate risk/reward ratio for this signal."""
        if not self.take_profits or self.stop_loss is None or self.entry_price is None:
            return Decimal(0)
        
        entry = Decimal(str(self.entry_price))
        sl = Decimal(str(self.stop_loss))
        
        if self.signal_type == "BUY":
            risk = entry - sl
            # Use first TP for calculation
            if self.take_profits:
                tp = Decimal(str(self.take_profits[0].get("price", entry)))
                reward = tp - entry
            else:
                return Decimal(0)
        else:  # SELL
            risk = sl - entry
            if self.take_profits:
                tp = Decimal(str(self.take_profits[0].get("price", entry)))
                reward = entry - tp
            else:
                return Decimal(0)
        
        if risk == 0:
            return Decimal(0)
        
        return (reward / risk).quantize(Decimal("0.01"))

__all__ = ["Signal"]