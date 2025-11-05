"""Custom exceptions for the flexi trader application"""

class FlexiTraderException(Exception):
    """Base exception for the flexi trader application"""

    def __init__(self, message: str, code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)

class ConfigurationError(FlexiTraderException):
    """Exception raised for configuration errors"""

    def __init__(self, message: str):
        super().__init__(message, "CONFIGURATION_ERROR")

class DatabaseError(FlexiTraderException):
    """Exception raised for database errors"""

    def __init__(self, message: str):
        super().__init__(message, "DATABASE_ERROR")

class ValidationError(FlexiTraderException):
    """Exception raised for validation errors"""

    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, "VALIDATION_ERROR")

class TemplateError(FlexiTraderException):
    """Exception raised for template errors"""

    def __init__(self, message: str):
        super().__init__(message, "TEMPLATE_ERROR")

class ExtractionError(FlexiTraderException):
    """Exception raised for extraction errors"""

    def __init__(self, message: str, reason: str = None):
        self.reason = reason
        super().__init__(message, "EXTRACTION_ERROR")

class ChannelError(FlexiTraderException):
    """Exception raised for channel errors"""

    def __init__(self, message: str):
        super().__init__(message, "CHANNEL_ERROR")

class TelegramError(FlexiTraderException):
    """Exception raised for telegram errors"""

    def __init__(self, message: str):
        super().__init__(message, "TELEGRAM_ERROR")

class DuplicateSignalError(FlexiTraderException):
    """Exception raised when a duplicate signal is detected."""

    def __init__(self, message: str, signal_id: str = None):
        self.signal_id = signal_id
        super().__init__(message, code="DUPLICATE_SIGNAL")


class RateLimitError(FlexiTraderException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(message, code="RATE_LIMIT_EXCEEDED")


__all__ = [
    "FlexiTraderException",
    "ConfigurationError",
    "DatabaseError",
    "ValidationError",
    "TemplateError",
    "ExtractionError",
    "ChannelError",
    "TelegramError",
    "DuplicateSignalError",
    "RateLimitError",
]