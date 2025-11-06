"""Database models for template management."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, String, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

class Template(Base):
    """Database model for a template."""

    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)

    # Extraction configuration as JSON
    extraction_config = Column(JSON, nullable=False)

    # Sample message for testing
    test_message = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Tracking 
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
    )
    created_by = Column(UUID(as_uuid=True), nullable=False)

    # Metrics
    extraction_success_rate = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    channel = relationship("Channel", back_populates="templates")
    extraction_history = relationship("ExtractionHistory", back_populates="template")

    def __repr__(self):
        return f"<Template(id={self.id}, name={self.name}, channel_id={self.channel_id})>"

class ExtractionHistory(Base):
    """History of template extractions for tracking success rate."""

    __tablename__ = "extraction_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"), nullable=False)

    # Extraation attempt details
    was_successful = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    extracted_data = Column(JSON, nullable=True)
    original_message = Column(Text, nullable=True)

    # Tracking
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), nullable=False)

    # Relationships
    template = relationship("Template", back_populates="extraction_history")

    def __repr__(self) -> str:
        """Return a string representation of the extraction history."""
        return f"<ExtractionHistory(id={self.id}, template_id={self.template_id}, success={self.was_successful})>"

__all__ = ["Template", "ExtractionHistory"]