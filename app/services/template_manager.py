"""Template management service for CRUD operations and validation."""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.exceptions import TemplateError, ValidationError
from app.logging_config import logger
from app.models import Template, ExtractionHistory, Channel, Signal
from app.services.extraction_engine import ExtractionEngine

class TemplateManager:
    """Manages template creation, validation, testing, and CRUD operations."""


    def __init__(self, db: Optional[Session] = None):
        """
        Initialize template manager.

        Args:
            db: Database session (optional, will create if not provided)
        """
        self.db = db or SessionLocal()
        self.extraction_engine = ExtractionEngine()


    @staticmethod
    def validate_template_config(
        template_config: Dict[str, Any]
        ) -> bool:
        """
        Validate template extraction configuration structure.

        Args:
            template_config: Extraction configuration dict

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
    ) -> Template:
        """
        Create a new template.

        Args:
            channel_id: Associated channel ID
            name: Template name
            extraction_config: Extraction configuration
            created_by: User ID creating template
            description: Optional template description
            test_message: Optional sample message for testing

        Returns:
            Created template object

        Raises:
            TemplateError: If validation fails
        """
        try:
            # Validate configuration
            self.validate_template_config(extraction_config)

            # Check channel exists
            channel = self.db.query(Channel).filter(
                Channel.id == channel_id
            ).first()
            if not channel:
                raise TemplateError(f"Channel {channel_id} not found")

            # Create template
            template = Template(
                channel_id=channel_id,
                name=name,
                description=description,
                extraction_config=extraction_config,
                test_message=test_message,
                created_by=created_by,
                is_active=True,
                extraction_success_rate=0,
            )

            self.db.add(template)
            self.db.commit()
            self.db.refresh(template)

            logger.info(f"Template created: id={template.id}, name={name}")
            return template

        except TemplateError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create template: {e}")
            raise TemplateError(f"Failed to create template: {str(e)}")

    def get_template(self, template_id: UUID) -> Optional[Template]:
        """
        Retrieve a template by ID.

        Args:
            template_id: Template ID

        Returns:
            Template object or None if not found
        """
        return self.db.query(Template).filter(
            Template.id == template_id
        ).first()

    def get_channel_templates(
        self,
        channel_id: UUID,
        active_only: bool = True
    ) -> List[Template]:
        """
        Get all templates for a channel.

        Args:
            channel_id: Channel ID
            active_only: Only return active templates

        Returns:
            List of templates
        """
        query = self.db.query(Template).filter(Template.channel_id == channel_id)

        if active_only:
            query = query.filter(Template.is_active == True)

        return query.all()
    
    def update_template(
        self,
        template_id: UUID,
        **kwargs
    ) -> Template:
        """
        Update template properties.

        Args:
            template_id: Template ID
            **kwargs: Fields to update (name, description, extraction_config, etc.)

        Returns:
            Updated template

        Raises:
            TemplateError: If template not found or update fails
        """
        try:
            template = self.get_template(template_id)
            if not template:
                raise TemplateError(f"Template {template_id} not found")

            # Validate extraction config if being updated
            if "extraction_config" in kwargs:
                self.validate_template_config(kwargs["extraction_config"])
                # Increment version when config changes
                template.version += 1

            # Update fields
            for key, value in kwargs.items():
                if hasattr(template, key):
                    setattr(template, key, value)

            template.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(template)

            logger.info(f"Template updated: id={template_id}")
            return template

        except TemplateError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update template: {e}")
            raise TemplateError(f"Failed to update template: {str(e)}")

    def delete_template(self, template_id: UUID) -> bool:
        """
        Delete a template.

        Args:
            template_id: Template ID

        Returns:
            True if deleted, False if not found
        """
        try:
            template = self.get_template(template_id)
            if not template:
                return False

            self.db.delete(template)
            self.db.commit()

            logger.info(f"Template deleted: id={template_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete template: {e}")
            raise TemplateError(f"Failed to delete template: {str(e)}")

    def test_template(
        self,
        template_id: UUID,
        test_message: str
    ) -> Dict[str, Any]:
        """
        Test a template against a sample message.

        Args:
            template_id: Template ID
            test_message: Sample message to test extraction

        Returns:
            Dictionary with test results including extracted data and errors
        """
        try:
            template = self.get_template(template_id)
            if not template:
                return {
                    "success": False,
                    "error": f"Template {template_id} not found",
                    "extracted_data": {},
                    "errors": []
                }

            # Run extraction
            result = self.extraction_engine.test_extraction(
                test_message,
                template.extraction_config
            )

            return {
                "success": result["success"],
                "extracted_data": result.get("extracted_data", {}),
                "errors": result.get("errors", []),
                "template_id": str(template_id),
                "template_name": template.name,
            }

        except Exception as e:
            logger.error(f"Template test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "extracted_data": {},
                "errors": []
            }

    def update_extraction_stats(
        self,
        template_id: UUID,
        was_successful: bool,
        extracted_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        original_message: Optional[str] = None,
        signal_id: Optional[UUID] = None,
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

        Returns:
            Updated success rate (0-100)
        """
        try:
            template = self.get_template(template_id)
            if not template:
                return 0.0

            # Create history record
            history = ExtractionHistory(
                template_id=template_id,
                signal_id=signal_id or UUID("00000000-0000-0000-0000-000000000000"),
                was_successful=was_successful,
                extracted_data=extracted_data,
                error_message=error_message,
                original_message=original_message or "",
            )
            self.db.add(history)

            # Calculate new success rate
            total_count = self.db.query(ExtractionHistory).filter(
                ExtractionHistory.template_id == template_id
            ).count()

            success_count = self.db.query(ExtractionHistory).filter(
                ExtractionHistory.template_id == template_id,
                ExtractionHistory.was_successful == True,
            ).count()

            if total_count > 0:
                success_rate = int((success_count / total_count) * 100)
                template.extraction_success_rate = success_rate
                template.last_used_at = datetime.now(timezone.utc)

            self.db.commit()

            logger.debug(
                f"Extraction stats updated: template={template_id}, "
                f"success_rate={template.extraction_success_rate}%"
            )

            return float(template.extraction_success_rate)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update extraction stats: {e}")
            return 0.0

    def activate_template(self, template_id: UUID) -> Optional[Template]:
        """
        Activate a template.

        Args:
            template_id: Template ID

        Returns:
            Updated template or None if not found
        """
        return self.update_template(template_id, is_active=True)

    def deactivate_template(self, template_id: UUID) -> Optional[Template]:
        """
        Deactivate a template.

        Args:
            template_id: Template ID

        Returns:
            Updated template or None if not found
        """
        return self.update_template(template_id, is_active=False)

    def get_template_stats(self, template_id: UUID) -> Dict[str, Any]:
        """
        Get template statistics.

        Args:
            template_id: Template ID

        Returns:
            Dictionary with template statistics
        """
        try:
            template = self.get_template(template_id)
            if not template:
                return {}

            total_history = self.db.query(ExtractionHistory).filter(
                ExtractionHistory.template_id == template_id
            ).count()

            success_history = self.db.query(ExtractionHistory).filter(
                ExtractionHistory.template_id == template_id,
                ExtractionHistory.was_successful == True,
            ).count()

            return {
                "template_id": str(template_id),
                "name": template.name,
                "version": template.version,
                "is_active": template.is_active,
                "extraction_success_rate": template.extraction_success_rate,
                "total_extractions": total_history,
                "successful_extractions": success_history,
                "failed_extractions": total_history - success_history,
                "created_at": template.created_at.isoformat(),
                "updated_at": template.updated_at.isoformat(),
                "last_used_at": template.last_used_at.isoformat() if template.last_used_at else None,
            }

        except Exception as e:
            logger.error(f"Failed to get template stats: {e}")
            return {}

    def close(self):
        """Close database session."""
        if self.db:
            self.db.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

__all__ = ["TemplateManager"]        