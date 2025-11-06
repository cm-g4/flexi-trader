"""Signal extraction engine with multiple extraction methods."""

import re
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple

from app.exceptions import ExtractionError
from app.logging_config import logger


class ExtractionMethod(ABC):
    """Abstract base class for extraction methods."""

    @abstractmethod
    def extract(self, message: str, pattern: Any) -> Optional[str]:
        """
        Extract text from message using the specified pattern.

        Args:
            message: The text message to extract from
            pattern: The pattern/configuration for extraction

        Returns:
            Extracted value or None if not found
        """
        pass

class RegexExtractionMethod(ExtractionMethod):
    """Extract using regex patterns."""

    def extract(self, message: str, pattern: str) -> Optional[str]:
        """
        Extract using regex pattern.

        Args:
            message: Text to search in
            pattern: Regex pattern

        Returns:
            First captured group or None
        """
        try:
            match = re.search(pattern, message, re.MULTILINE | re.IGNORECASE)
            if match:
                # Return first group if exists, otherwise the whole match
                return match.group(1) if match.groups() else match.group(0)
            return None
        except re.error as e:
            logger.error(f"Invalid regex pattern: {pattern}. Error: {e}")
            raise ExtractionError(f"Invalid regex pattern: {pattern}", reason=str(e))

class LineBasedExtractionMethod(ExtractionMethod):
    """Extract from specific line."""

    def extract(self, message: str, config: Dict[str, Any]) -> Optional[str]:
        """
        Extract from specific line.

        Args:
            message: Text to search in
            config: Contains 'line_number' and optional 'marker_after'

        Returns:
            Extracted value or None
        """
        lines = message.split("\n")
        line_number = config.get("line_number", 0)
        marker_after = config.get("marker_after")
        
        if line_number < 0 or line_number >= len(lines):
            return None
        
        line = lines[line_number].strip()
        
        if marker_after:
            parts = line.split(marker_after)
            if len(parts) > 1:
                return parts[1].strip()
        
        return line if line else None

class MarkerBasedExtractionMethod(ExtractionMethod):
    """Extract text between markers."""

    def extract(self, message: str, config: Dict[str, Any]) -> Optional[str]:
        """
        Extract text between start and end markers.

        Args:
            message: Text to search in
            config: Contains 'marker_start' and 'marker_end'

        Returns:
            Extracted value or None
        """
        marker_start = config.get("marker_start")
        marker_end = config.get("marker_end")
        
        if not marker_start or not marker_end:
            return None
        
        start_idx = message.find(marker_start)
        if start_idx == -1:
            return None
        
        start_idx += len(marker_start)
        end_idx = message.find(marker_end, start_idx)
        
        if end_idx == -1:
            end_idx = len(message)
        
        return message[start_idx:end_idx].strip()

class TextPositionExtractionMethod(ExtractionMethod):
    """Extract based on text position."""

    def extract(self, message: str, config: Dict[str, Any]) -> Optional[str]:
        """
        Extract based on character position.

        Args:
            message: Text to search in
            config: Contains 'start_pos' and optional 'end_pos'

        Returns:
            Extracted value or None
        """
        start_pos = config.get("start_pos", 0)
        end_pos = config.get("end_pos")
        
        if end_pos is None:
            # Look for next space or newline if end not specified
            end_pos = len(message)
            for i in range(start_pos, len(message)):
                if message[i] in (" ", "\n"):
                    end_pos = i
                    break
        
        if start_pos < 0 or start_pos >= len(message):
            return None
        
        return message[start_pos:end_pos].strip()

class ExtractionEngine:
    """Engine for extracting signals from messages using multiple methods."""

    def __init__(self):
        """Initialize the extraction engine with default methods."""
        self.methods: Dict[str, ExtractionMethod] = {
            "regex": RegexExtractionMethod(),
            "line": LineBasedExtractionMethod(),
            "marker": MarkerBasedExtractionMethod(),
            "position": TextPositionExtractionMethod(),
        }

    def extract_field(
        self,
        message: str,
        field_config: Dict[str, Any],
        field_name: str,
    ) -> Tuple[Optional[str], bool]:
        """
        Extract a single field from message.

        Args:
            message: Message text
            field_config: Field extraction configuration
            field_name: Name of field for logging

        Returns:
            Tuple of (extracted_value, was_successful)
        """
        method_name = field_config.get("extraction_method", "regex")

        if method_name not in self.methods:
            logger.warning(f"Unknown extraction method: {method_name}. Using regex.")
            return None, False

        method = self.methods[method_name]

        try:
            # Get pattern based on method
            if method_name == "line":
                pattern = field_config
            elif method_name == "marker":
                pattern = field_config
            elif method_name == "position":
                pattern = field_config
            else:  # regex
                pattern = field_config.get("regex_pattern")

            value = method.extract(message, pattern)

            if value is None and field_config.get("required"):
                logger.debug(f"Required field '{field_name}' not found in message")
                return None, False

            return value, True
        except ExtractionError:
            raise
        except Exception as e:
            logger.error(f"Error extracting field '{field_name}': {e}")
            return None, False
    
    def extract_all_fields(
        self,
        message: str,
        extraction_config: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Extract all fields from a message using provided configuration.

        Args:
            message: The raw message text
            extraction_config: Template extraction configuration

        Returns:
            Tuple of (extracted_data, list_of_errors)
        """
        extracted_data = {}
        errors = []
        
        fields_config = extraction_config.get("fields", {})
        
        for field_name, field_config in fields_config.items():
            value, success = self.extract_field(
                message, field_config, field_name
            )
            
            if success:
                extracted_data[field_name] = value
            elif field_config.get("required"):
                errors.append(f"Required field '{field_name}' could not be extracted")
            
        return extracted_data, errors

    def validate_extraction(
        self,
        extracted_data: Dict[str, Any],
        validation_rules: List[str],
    ) -> Tuple[bool, List[str]]:
        """
        Validate extracted data against validation rules.

        Args:
            extracted_data: The extracted data
            validation_rules: List of validation rule descriptions

        Returns:
            Tuple of (is_valid, list_of_validation_errors)
        """
        # Validation rules are stored as descriptions
        # Actual validation happens in the signal validator
        # This method is here for extensibility
        return True, []

    def test_extraction(
        self,
        sample_message: str,
        extraction_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Test extraction on a sample message.

        Args:
            sample_message: Sample message for testing
            extraction_config: Template configuration

        Returns:
            Dictionary with 'success', 'extracted_data', and 'errors'
        """
        try:
            extracted_data, errors = self.extract_all_fields(
                sample_message, extraction_config
            )
            
            return {
                "success": len(errors) == 0,
                "extracted_data": extracted_data,
                "errors": errors,
            }
        except ExtractionError as e:
            return {
                "success": False,
                "extracted_data": {},
                "errors": [str(e)],
            }
        except Exception as e:
            logger.error(f"Test extraction failed: {e}")
            return {
                "success": False,
                "extracted_data": {},
                "errors": [f"Extraction failed: {str(e)}"],
            }

__all__ = [
    "ExtractionEngine",
    "ExtractionMethod",
    "RegexExtractionMethod",
    "LineBasedExtractionMethod",
    "MarkerBasedExtractionMethod",
    "TextPositionExtractionMethod",
]