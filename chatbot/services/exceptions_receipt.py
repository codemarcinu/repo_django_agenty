"""
Custom exceptions for receipt processing module.
"""

from typing import Any

from .exceptions import ProcessingError, ResourceNotFoundError, ValidationError


class ReceiptError(Exception):
    """Base exception for receipt errors."""

    def __init__(self, message: str, error_code: str | None = None, details: dict[str, Any] | None = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.message,
            "error_code": self.error_code,
            "details": self.details
        }


class OCRError(ReceiptError):
    """Exception raised during OCR text extraction."""

    def __init__(self, message: str, file_path: str | None = None, **kwargs):
        details = kwargs.get("details", {})
        if file_path:
            details["file_path"] = file_path
        super().__init__(message, error_code="OCR_ERROR", details=details)


class LLMError(ReceiptError):
    """Exception raised during LLM product extraction."""

    def __init__(self, message: str, model_name: str | None = None, **kwargs):
        details = kwargs.get("details", {})
        if model_name:
            details["model_name"] = model_name
        super().__init__(message, error_code="LLM_ERROR", details=details)


class FileValidationError(ReceiptError):
    """Exception raised during file validation."""

    def __init__(self, message: str, file_path: str | None = None, **kwargs):
        details = kwargs.get("details", {})
        if file_path:
            details["file_path"] = file_path
        super().__init__(message, error_code="FILE_VALIDATION_ERROR", details=details)


class CacheError(ReceiptError):
    """Exception raised during cache operations."""

    def __init__(self, message: str, cache_key: str | None = None, **kwargs):
        details = kwargs.get("details", {})
        if cache_key:
            details["cache_key"] = cache_key
        super().__init__(message, error_code="CACHE_ERROR", details=details)


class DatabaseError(ReceiptError):
    """Exception raised during database operations."""

    def __init__(self, message: str, model_name: str | None = None, **kwargs):
        details = kwargs.get("details", {})
        if model_name:
            details["model_name"] = model_name
        super().__init__(message, error_code="DATABASE_ERROR", details=details)


class ReceiptNotFoundError(ReceiptError, ResourceNotFoundError):
    """Raised when receipt is not found"""
    pass


class ReceiptValidationError(ReceiptError, ValidationError):
    """Raised when receipt validation fails"""
    pass


class ParsingError(ReceiptError, ProcessingError):
    """Raised when receipt parsing fails"""
    pass


class MatchingError(ReceiptError, ProcessingError):
    """Raised when product matching fails"""
    pass
