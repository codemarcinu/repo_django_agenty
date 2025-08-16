"""
File validators for receipt upload functionality.
"""

import os

from django.conf import settings
from django.core.exceptions import ValidationError


def validate_receipt_file(file):
    """
    Validate uploaded receipt file with enhanced security checks.
    """
    if not file:
        raise ValidationError("Plik jest wymagany")

    # Check file size
    max_size = getattr(settings, 'MAX_RECEIPT_FILE_SIZE', 10 * 1024 * 1024)  # 10MB default
    if file.size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        current_size_mb = file.size / (1024 * 1024)
        raise ValidationError(
            f'Plik jest za duży ({current_size_mb:.1f}MB). Maksymalny rozmiar: {max_size_mb:.0f}MB'
        )

    # Check minimum file size (prevent empty files)
    min_size = 100  # 100 bytes minimum
    if file.size < min_size:
        raise ValidationError("Plik jest za mały lub pusty")

    # File extension validation
    valid_extensions = getattr(settings, 'ALLOWED_RECEIPT_EXTENSIONS', ['.jpg', '.jpeg', '.png', '.webp', '.pdf'])
    file_extension = os.path.splitext(file.name)[1].lower()

    if file_extension not in valid_extensions:
        raise ValidationError(
            f'Nieprawidłowy format pliku "{file_extension}". Obsługiwane formaty: {", ".join(valid_extensions)}'
        )

    # Enhanced MIME type validation
    allowed_content_types = {
        '.jpg': ['image/jpeg'],
        '.jpeg': ['image/jpeg'],
        '.png': ['image/png'],
        '.webp': ['image/webp'],
        '.pdf': ['application/pdf']
    }

    if hasattr(file, "content_type") and file.content_type:
        expected_types = allowed_content_types.get(file_extension, [])
        if expected_types and file.content_type not in expected_types:
            raise ValidationError(
                f'Nieprawidłowy typ MIME "{file.content_type}" dla rozszerzenia "{file_extension}"'
            )

    # Validate filename characters (prevent path traversal)
    if '..' in file.name or '/' in file.name or '\\' in file.name:
        raise ValidationError("Nazwa pliku zawiera niedozwolone znaki")

    # Check filename length
    if len(file.name) > 255:
        raise ValidationError("Nazwa pliku jest za długa (maksymalnie 255 znaków)")

    # Check for null bytes and other dangerous characters
    dangerous_chars = ['\x00', '\r', '\n']
    for char in dangerous_chars:
        if char in file.name:
            raise ValidationError("Nazwa pliku zawiera niedozwolone znaki kontrolne")

    return file


def get_file_type(file):
    """
    Determine if uploaded file is image or PDF.
    Accepts both file objects (with .name attribute) and file paths (strings).
    Returns: 'image' or 'pdf'
    """
    # Handle both file objects and string paths
    if hasattr(file, "name"):
        # File object with .name attribute
        filename = file.name
    elif isinstance(file, str):
        # String path
        filename = file
    else:
        # Fallback - convert to string
        filename = str(file)

    file_extension = os.path.splitext(filename)[1].lower()

    if file_extension == ".pdf":
        return "pdf"
    else:
        return "image"
