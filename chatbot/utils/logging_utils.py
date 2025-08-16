"""
Logging utilities with security enhancements.
Prevents sensitive information leakage in logs.
"""

import logging
import re
from typing import Any

# Patterns to detect and sanitize sensitive information
SENSITIVE_PATTERNS = [
    # API keys and tokens
    (re.compile(r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', re.IGNORECASE), '[API_KEY_REDACTED]'),
    (re.compile(r'["\']?token["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', re.IGNORECASE), '[TOKEN_REDACTED]'),
    (re.compile(r'["\']?secret["\']?\s*[:=]\s*["\']?([^"\'\\s]+)', re.IGNORECASE), '[SECRET_REDACTED]'),

    # Database URLs
    (re.compile(r'(postgresql|mysql|sqlite)://[^\\s]+', re.IGNORECASE), '[DATABASE_URL_REDACTED]'),

    # Email addresses (partially redact)
    (re.compile(r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', re.IGNORECASE), r'\1@[DOMAIN_REDACTED]'),

    # Credit card patterns (basic)
    (re.compile(r'\b(?:\d{4}[-\s]?){3,4}\d{1,4}\b'), '[CARD_NUMBER_REDACTED]'),

    # IP addresses (partially redact)
    (re.compile(r'\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b'), r'\1.\2.XXX.XXX'),
]


def sanitize_log_message(message: str) -> str:
    """
    Sanitize log message by removing or redacting sensitive information.
    
    Args:
        message: Original log message
        
    Returns:
        Sanitized log message
    """
    if not isinstance(message, str):
        message = str(message)

    sanitized = message

    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized


def safe_log_error(logger: logging.Logger, message: str, exception: Exception = None, **kwargs) -> None:
    """
    Safely log an error with automatic sanitization.
    
    Args:
        logger: Logger instance
        message: Base error message
        exception: Optional exception to include
        **kwargs: Additional keyword arguments for logger
    """
    full_message = message

    if exception:
        # Convert exception to string safely
        exc_str = str(exception)
        # Sanitize the exception message
        exc_str = sanitize_log_message(exc_str)
        full_message = f"{message}: {exc_str}"

    # Sanitize the full message
    sanitized_message = sanitize_log_message(full_message)

    logger.error(sanitized_message, **kwargs)


def safe_log_warning(logger: logging.Logger, message: str, **kwargs) -> None:
    """
    Safely log a warning with automatic sanitization.
    """
    sanitized_message = sanitize_log_message(message)
    logger.warning(sanitized_message, **kwargs)


def safe_log_info(logger: logging.Logger, message: str, **kwargs) -> None:
    """
    Safely log info with automatic sanitization.
    """
    sanitized_message = sanitize_log_message(message)
    logger.info(sanitized_message, **kwargs)


def safe_repr(obj: Any, max_length: int = 200) -> str:
    """
    Safely represent an object for logging, with length limit and sanitization.
    
    Args:
        obj: Object to represent
        max_length: Maximum length of representation
        
    Returns:
        Safe string representation
    """
    try:
        # Convert to string representation
        if hasattr(obj, '__dict__'):
            # For objects with attributes, show type and some safe attributes
            obj_type = type(obj).__name__
            safe_attrs = []

            for key, value in obj.__dict__.items():
                if not key.startswith('_') and len(safe_attrs) < 5:
                    # Limit attribute values and sanitize
                    str_value = str(value)[:50]
                    if key.lower() in ['password', 'secret', 'token', 'key']:
                        str_value = '[REDACTED]'
                    else:
                        str_value = sanitize_log_message(str_value)
                    safe_attrs.append(f"{key}={str_value}")

            obj_repr = f"{obj_type}({', '.join(safe_attrs)})"
        else:
            obj_repr = str(obj)

        # Sanitize and truncate
        sanitized = sanitize_log_message(obj_repr)
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length-3] + "..."

        return sanitized

    except Exception:
        # Fallback for objects that can't be safely represented
        return f"<{type(obj).__name__} object>"


class SanitizingFormatter(logging.Formatter):
    """
    Custom log formatter that automatically sanitizes sensitive information.
    """

    def format(self, record):
        # First format the record normally
        formatted = super().format(record)

        # Then sanitize the result
        return sanitize_log_message(formatted)


# Convenience function to get a sanitizing logger
def get_sanitizing_logger(name: str) -> logging.Logger:
    """
    Get a logger configured with sanitizing formatter.
    
    Args:
        name: Logger name
        
    Returns:
        Logger with sanitizing formatter
    """
    logger = logging.getLogger(name)

    # Add sanitizing handler if not already present
    has_sanitizing_handler = any(
        isinstance(handler.formatter, SanitizingFormatter)
        for handler in logger.handlers
    )

    if not has_sanitizing_handler:
        handler = logging.StreamHandler()
        handler.setFormatter(SanitizingFormatter(
            '[{asctime}] {levelname} in {name}: {message}',
            style='{',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(handler)

    return logger
