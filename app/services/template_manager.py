"""Template management service for CRUD operations and validation."""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.exceptions import TemplateError, ValidationError
from app.logging_config import logger
from app.models import Template, ExtractionHistory
from app.services.extraction_engine import ExtractionEngine
from app.validators import Validator

class TemplateManager:
    """Manages template creation, validation, and testing."""


    def __init__(self):
        """Initialize template manager."""
        self.extraction_engine = ExtractionEngine()

    @staticmethod
    def validate_template_config(
        template_config: Dict[str, Any]
        ) -> bool:
        """
        Validate template extraction configuration structure.

        Args:
            config: Extraction configuration dict

        Returns:
            True if valid

        Raises:
            TemplateError: If configuration is invalid
        """
        required_keys = {"fields"}

        if not isinstance(template_config, dict):
            raise TemplateError("Template configuration must be a dictionary")
        
        missing_keys = required_keys - set(template_config.keys())
        if missing_keys:
            raise TemplateError(
                f"Missing required keys in extraction config: {missing_keys}"
            )
        
        fields = template_config.get("fields", {})
        if not isinstance(fields, dict):
            raise TemplateError("'fields' must be a dictionary")

        if not fields:
            raise TemplateError("At least one field must be defined")

        # Validate each field
        for field_name, field_config in fields.items():
            if not isinstance(field_config, dict):
                raise TemplateError(
                    f"Field '{field_name}' config must be a dictionary"
                )
            
            extraction_method = field_config.get("extraction_method", "regex")
            if extraction_method not in {"regex", "line", "marker", "position"}:
                raise TemplateError(
                    f"Invalid extraction method '{extraction_method}' for "
                    f"field '{field_name}'"
                )
            
            # Regex method requires a pattern
            if extraction_method == "regex" and "regex_pattern" not in field_config:
                raise TemplateError(
                    f"Regex method requires 'regex_pattern' for field '{field_name}'"
                )

        return True

    def create_template(
        self,
        channel_id: UUID,
        name: str,
        extraction_config: Dict[str, Any],
        created_by: UUID,
        description: Optional[str] = None,
        test_message: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Template:
        """
        Create a new template.

        Args:
            channel_id: Channel ID this template belongs to
            name: Template name
            extraction_config: Extraction configuration
            created_by: User ID creating the template
            description: Optional description
            test_message: Optional sample message for testing
            db: Database session

        Returns:
            Created Template object

        Raises:
            TemplateError: If configuration is invalid
            ValidationError: If inputs are invalid
        """
        # Validate inputs
        if not name or not isinstance(name, str):
            raise ValidationError("Template name must be a non-empty string")
        
        if len(name) > 255:
            raise ValidationError("Template name must be max 255 characters")
        
        # Validate config
        self.validate_template_config(extraction_config)
        
        db = db or SessionLocal()
        
        try:
            template = Template(
                channel_id=channel_id,
                name=name.strip(),
                description=description,
                extraction_config=extraction_config,
                test_message=test_message,
                created_by=created_by,
                is_active=True,
                extraction_success_rate=0,
            )
            
            db.add(template)
            db.commit()
            db.refresh(template)
            
            logger.info(f"Template created: {template.id} - {name}")
            return template
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create template: {e}")
            raise TemplateError(f"Failed to create template: {str(e)}")

    def test_template(
        self,
        template: Template,
        test_message: str,
    ) -> Dict[str, Any]:
        """
        Test a template against a sample message.

        Args:
            template: Template to test
            test_message: Sample message to test with

        Returns:
            Dict with 'success', 'extracted_data', and 'errors'
        """
        if not test_message or not isinstance(test_message, str):
            raise ValidationError("Test message must be a non-empty string")
        
        logger.info(f"Testing template {template.id} with sample message")
        
        result = self.extraction_engine.test_extraction(
            test_message,
            template.extraction_config,
        )
        
        return result

    def update_template(
        self,
        template_id: UUID,
        updates: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Template:
        """
        Update a template.

        Args:
            template_id: Template to update
            updates: Dictionary of fields to update
            db: Database session

        Returns:
            Updated Template object

        Raises:
            TemplateError: If update fails
        """
        db = db or SessionLocal()
        
        try:
            template = db.query(Template).filter(Template.id == template_id).first()
            
            if not template:
                raise TemplateError(f"Template {template_id} not found")
            
            # Validate extraction_config if being updated
            if "extraction_config" in updates:
                self.validate_template_config(updates["extraction_config"])
                # Increment version
                template.version += 1
            
            # Update allowed fields
            allowed_fields = {
                "name", "description", "extraction_config", "test_message", "is_active"
            }
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(template, field, value)
            
            template.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(template)
            
            logger.info(f"Template updated: {template_id}")
            return template
        except TemplateError:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update template: {e}")
            raise TemplateError(f"Failed to update template: {str(e)}")

    def get_template(
        self,
        template_id: UUID,
        db: Optional[Session] = None,
    ) -> Optional[Template]:
        """
        Get a template by ID.

        Args:
            template_id: Template ID
            db: Database session

        Returns:
            Template object or None
        """
        db = db or SessionLocal()
        return db.query(Template).filter(Template.id == template_id).first()

    def list_templates(
        self,
        channel_id: UUID,
        active_only: bool = False,
        db: Optional[Session] = None,
    ) -> List[Template]:
        """
        List templates for a channel.

        Args:
            channel_id: Channel ID
            active_only: Only return active templates
            db: Database session

        Returns:
            List of templates
        """
        db = db or SessionLocal()
        query = db.query(Template).filter(Template.channel_id == channel_id)
        
        if active_only:
            query = query.filter(Template.is_active == True)
        
        return query.order_by(Template.created_at.desc()).all()

    def delete_template(
        self,
        template_id: UUID,
        db: Optional[Session] = None,
    ) -> bool:
        """
        Delete a template (soft delete by deactivating).

        Args:
            template_id: Template to delete
            db: Database session

        Returns:
            True if successful

        Raises:
            TemplateError: If deletion fails
        """
        db = db or SessionLocal()
        
        try:
            template = db.query(Template).filter(Template.id == template_id).first()
            
            if not template:
                raise TemplateError(f"Template {template_id} not found")
            
            template.is_active = False
            template.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Template deleted (deactivated): {template_id}")
            return True
        except TemplateError:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete template: {e}")
            raise TemplateError(f"Failed to delete template: {str(e)}")

    def update_extraction_stats(
        self,
        template_id: UUID,
        was_successful: bool,
        extracted_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        original_message: Optional[str] = None,
        signal_id: Optional[UUID] = None,
        db: Optional[Session] = None,
    ) -> float:
        """
        Update template extraction statistics.

        Args:
            template_id: Template ID
            was_successful: Whether extraction was successful
            extracted_data: Extracted data (if successful)
            error_message: Error message (if failed)
            original_message: Original message
            signal_id: Associated signal ID (optional)
            db: Database session

        Returns:
            Updated success rate (0-100)
        """
        db = db or SessionLocal()
        
        try:
            template = db.query(Template).filter(Template.id == template_id).first()
            if not template:
                return 0.0
            
            # Create history record
            history = ExtractionHistory(
                template_id=template_id,
                signal_id=signal_id,
                was_successful=was_successful,
                extracted_data=extracted_data,
                error_message=error_message,
                original_message=original_message or "",
            )
            db.add(history)
            
            # Calculate new success rate
            total_count = db.query(ExtractionHistory).filter(
                ExtractionHistory.template_id == template_id
            ).count()
            
            success_count = db.query(ExtractionHistory).filter(
                ExtractionHistory.template_id == template_id,
                ExtractionHistory.was_successful == True,
            ).count()
            
            if total_count > 0:
                success_rate = int((success_count / total_count) * 100)
                template.extraction_success_rate = success_rate
                template.last_used_at = datetime.now(timezone.utc)
            
            db.commit()
            
            return float(template.extraction_success_rate)
        except Exception as e:
            logger.error(f"Failed to update extraction stats: {e}")
            db.rollback()
            return 0.0


__all__ = ["TemplateManager"]