"""
File validators for receipt upload functionality.
"""
import os
from django.core.exceptions import ValidationError
from django.conf import settings


def validate_receipt_file(file):
    """
    Validate uploaded receipt file - supports images and PDF.
    """
    # File size validation (10MB max)
    max_size = 10 * 1024 * 1024  # 10MB in bytes
    if file.size > max_size:
        raise ValidationError(
            f'Plik jest za duży. Maksymalny rozmiar to {max_size // (1024*1024)}MB.'
        )
    
    # File extension validation
    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.pdf']
    file_extension = os.path.splitext(file.name)[1].lower()
    
    if file_extension not in valid_extensions:
        raise ValidationError(
            f'Nieprawidłowy format pliku. Obsługiwane formaty: {", ".join(valid_extensions)}'
        )
    
    # MIME type validation
    valid_mime_types = [
        'image/jpeg',
        'image/jpg', 
        'image/png',
        'image/webp',
        'application/pdf'
    ]
    
    if hasattr(file, 'content_type') and file.content_type:
        if file.content_type not in valid_mime_types:
            raise ValidationError(
                f'Nieprawidłowy typ pliku: {file.content_type}. '
                f'Obsługiwane typy: {", ".join(valid_mime_types)}'
            )
    
    return file


def get_file_type(file):
    """
    Determine if uploaded file is image or PDF.
    Accepts both file objects (with .name attribute) and file paths (strings).
    Returns: 'image' or 'pdf'
    """
    # Handle both file objects and string paths
    if hasattr(file, 'name'):
        # File object with .name attribute
        filename = file.name
    elif isinstance(file, str):
        # String path
        filename = file
    else:
        # Fallback - convert to string
        filename = str(file)
    
    file_extension = os.path.splitext(filename)[1].lower()
    
    if file_extension == '.pdf':
        return 'pdf'
    else:
        return 'image'