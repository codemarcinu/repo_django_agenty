"""
Serializers for receipt upload API.
"""

from rest_framework import serializers
from django.core.files.uploadedfile import UploadedFile
import magic
import os


class ReceiptUploadSerializer(serializers.Serializer):
    """Serializer for receipt file upload."""
    
    file = serializers.FileField()
    
    # Supported file types
    SUPPORTED_MIME_TYPES = {
        'application/pdf': ['.pdf'],
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
    }
    
    # Maximum file size: 50MB
    MAX_FILE_SIZE = 50 * 1024 * 1024
    
    def validate_file(self, file: UploadedFile) -> UploadedFile:
        """
        Validate uploaded receipt file.
        
        Args:
            file: Uploaded file instance
            
        Returns:
            Validated file
            
        Raises:
            ValidationError: If file is invalid
        """
        # Check file size
        if file.size > self.MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f"File size too large. Maximum size is {self.MAX_FILE_SIZE // (1024*1024)}MB."
            )
        
        # Check file extension
        file_extension = os.path.splitext(file.name)[1].lower()
        valid_extensions = []
        for extensions in self.SUPPORTED_MIME_TYPES.values():
            valid_extensions.extend(extensions)
        
        if file_extension not in valid_extensions:
            raise serializers.ValidationError(
                f"Unsupported file type '{file_extension}'. "
                f"Supported types: {', '.join(valid_extensions)}"
            )
        
        # Validate MIME type using python-magic
        try:
            # Read first 2048 bytes to determine MIME type
            file.seek(0)
            file_header = file.read(2048)
            file.seek(0)  # Reset file pointer
            
            mime_type = magic.from_buffer(file_header, mime=True)
            
            if mime_type not in self.SUPPORTED_MIME_TYPES:
                raise serializers.ValidationError(
                    f"Invalid file content. File appears to be '{mime_type}' "
                    f"but only {list(self.SUPPORTED_MIME_TYPES.keys())} are supported."
                )
            
            # Verify file extension matches MIME type
            expected_extensions = self.SUPPORTED_MIME_TYPES[mime_type]
            if file_extension not in expected_extensions:
                raise serializers.ValidationError(
                    f"File extension '{file_extension}' doesn't match content type '{mime_type}'. "
                    f"Expected extensions for this type: {', '.join(expected_extensions)}"
                )
                
        except Exception as e:
            raise serializers.ValidationError(
                f"Unable to validate file content: {str(e)}"
            )
        
        return file


class ReceiptUploadResponseSerializer(serializers.Serializer):
    """Serializer for receipt upload response."""
    
    receipt_id = serializers.IntegerField()
    status = serializers.CharField()
    message = serializers.CharField()
    file_path = serializers.CharField()
    file_size = serializers.IntegerField()
    uploaded_at = serializers.DateTimeField()