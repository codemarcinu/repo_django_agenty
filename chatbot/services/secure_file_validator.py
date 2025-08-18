"""
Secure File Validator implementing Phase 4.1 of the receipt pipeline improvement plan.
Provides enhanced security validation for uploaded receipt files.
"""

import os
import magic
import hashlib
import tempfile
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
from PIL import Image
import PyPDF2
from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class SecurityScanResult:
    """Result of security scan."""
    is_safe: bool
    issues: List[str]
    file_type: str
    file_size: int
    hash_sha256: str
    metadata: Dict[str, Any]


class SecureReceiptValidator:
    """
    Enhanced security validator for receipt file uploads.
    Implements comprehensive security checks beyond basic Django validation.
    """
    
    # Allowed MIME types for receipt files
    ALLOWED_MIME_TYPES = {
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/webp': ['.webp'],
        'image/tiff': ['.tiff', '.tif'],
        'application/pdf': ['.pdf']
    }
    
    # Maximum file sizes (in bytes)
    MAX_FILE_SIZES = {
        'image/jpeg': 10 * 1024 * 1024,  # 10MB
        'image/png': 15 * 1024 * 1024,   # 15MB
        'image/webp': 10 * 1024 * 1024,  # 10MB
        'image/tiff': 20 * 1024 * 1024,  # 20MB
        'application/pdf': 25 * 1024 * 1024  # 25MB
    }
    
    # Image dimension limits
    MAX_IMAGE_DIMENSIONS = (8000, 8000)  # 8K x 8K max
    MIN_IMAGE_DIMENSIONS = (50, 50)      # Minimum readable size
    
    # PDF limits
    MAX_PDF_PAGES = 10
    
    def __init__(self):
        """Initialize the secure validator."""
        self.magic_mime = magic.Magic(mime=True)
        
        # Initialize malware scanner if available
        self.malware_scanner = self._init_malware_scanner()
        
    def validate_upload(self, file) -> SecurityScanResult:
        """
        Comprehensive security validation of uploaded file.
        
        Args:
            file: Django UploadedFile object
            
        Returns:
            SecurityScanResult with validation results
        """
        issues = []
        metadata = {}
        
        try:
            # Basic file properties
            file_size = file.size
            file_name = file.name
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(file)
            
            # Reset file pointer
            file.seek(0)
            
            # 1. MIME type validation
            detected_mime = self._detect_mime_type(file)
            mime_issues = self._validate_mime_type(detected_mime, file_name)
            issues.extend(mime_issues)
            
            # 2. File size validation
            size_issues = self._validate_file_size(file_size, detected_mime)
            issues.extend(size_issues)
            
            # 3. File name validation
            name_issues = self._validate_file_name(file_name)
            issues.extend(name_issues)
            
            # 4. Content validation based on file type
            if detected_mime.startswith('image/'):
                content_issues, img_metadata = self._validate_image_content(file)
                issues.extend(content_issues)
                metadata.update(img_metadata)
            elif detected_mime == 'application/pdf':
                content_issues, pdf_metadata = self._validate_pdf_content(file)
                issues.extend(content_issues)
                metadata.update(pdf_metadata)
            
            # 5. Malware scanning
            if self.malware_scanner:
                malware_issues = self._scan_for_malware(file)
                issues.extend(malware_issues)
            
            # 6. Suspicious pattern detection
            pattern_issues = self._detect_suspicious_patterns(file, detected_mime)
            issues.extend(pattern_issues)
            
            # Reset file pointer
            file.seek(0)
            
            is_safe = len(issues) == 0
            
            logger.info(f"File validation completed for {file_name}: {len(issues)} issues found")
            
            return SecurityScanResult(
                is_safe=is_safe,
                issues=issues,
                file_type=detected_mime,
                file_size=file_size,
                hash_sha256=file_hash,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error during file validation: {e}", exc_info=True)
            return SecurityScanResult(
                is_safe=False,
                issues=[f"Validation error: {str(e)}"],
                file_type="unknown",
                file_size=0,
                hash_sha256="",
                metadata={}
            )
    
    def _detect_mime_type(self, file) -> str:
        """Detect actual MIME type of file."""
        try:
            # Read first chunk for MIME detection
            chunk = file.read(1024)
            file.seek(0)
            
            # Use python-magic for reliable detection
            detected_mime = magic.from_buffer(chunk, mime=True)
            
            return detected_mime
            
        except Exception as e:
            logger.warning(f"MIME type detection failed: {e}")
            return "application/octet-stream"
    
    def _validate_mime_type(self, detected_mime: str, file_name: str) -> List[str]:
        """Validate MIME type against allowed types."""
        issues = []
        
        if detected_mime not in self.ALLOWED_MIME_TYPES:
            issues.append(f"File type not allowed: {detected_mime}")
            return issues
        
        # Check file extension matches MIME type
        file_ext = Path(file_name).suffix.lower()
        allowed_extensions = self.ALLOWED_MIME_TYPES[detected_mime]
        
        if file_ext not in allowed_extensions:
            issues.append(f"File extension {file_ext} doesn't match detected type {detected_mime}")
        
        return issues
    
    def _validate_file_size(self, file_size: int, mime_type: str) -> List[str]:
        """Validate file size against limits."""
        issues = []
        
        if file_size == 0:
            issues.append("File is empty")
            return issues
        
        max_size = self.MAX_FILE_SIZES.get(mime_type, 5 * 1024 * 1024)  # Default 5MB
        
        if file_size > max_size:
            issues.append(f"File too large: {file_size} bytes (max: {max_size} bytes)")
        
        return issues
    
    def _validate_file_name(self, file_name: str) -> List[str]:
        """Validate file name for security issues."""
        issues = []
        
        if not file_name:
            issues.append("Missing file name")
            return issues
        
        # Check for path traversal attempts
        if '..' in file_name or '/' in file_name or '\\' in file_name:
            issues.append("Invalid characters in file name")
        
        # Check for excessively long names
        if len(file_name) > 255:
            issues.append("File name too long")
        
        # Check for suspicious extensions
        suspicious_extensions = ['.exe', '.bat', '.cmd', '.scr', '.com', '.pif', '.vbs', '.js']
        file_ext = Path(file_name).suffix.lower()
        
        if file_ext in suspicious_extensions:
            issues.append(f"Suspicious file extension: {file_ext}")
        
        return issues
    
    def _validate_image_content(self, file) -> tuple[List[str], Dict[str, Any]]:
        """Validate image file content."""
        issues = []
        metadata = {}
        
        try:
            with Image.open(file) as img:
                width, height = img.size
                format_name = img.format
                mode = img.mode
                
                metadata.update({
                    'width': width,
                    'height': height,
                    'format': format_name,
                    'mode': mode
                })
                
                # Check dimensions
                if width > self.MAX_IMAGE_DIMENSIONS[0] or height > self.MAX_IMAGE_DIMENSIONS[1]:
                    issues.append(f"Image too large: {width}x{height} (max: {self.MAX_IMAGE_DIMENSIONS[0]}x{self.MAX_IMAGE_DIMENSIONS[1]})")
                
                if width < self.MIN_IMAGE_DIMENSIONS[0] or height < self.MIN_IMAGE_DIMENSIONS[1]:
                    issues.append(f"Image too small: {width}x{height} (min: {self.MIN_IMAGE_DIMENSIONS[0]}x{self.MIN_IMAGE_DIMENSIONS[1]})")
                
                # Check for suspicious metadata
                if hasattr(img, '_getexif') and img._getexif():
                    exif_data = img._getexif()
                    if exif_data:
                        # Remove GPS data for privacy
                        gps_tags = [34853]  # GPS IFD tag
                        if any(tag in exif_data for tag in gps_tags):
                            issues.append("Image contains GPS data (will be stripped)")
                
                # Verify image can be processed
                try:
                    img.verify()
                except Exception as e:
                    issues.append(f"Image verification failed: {str(e)}")
                
        except Exception as e:
            issues.append(f"Invalid image file: {str(e)}")
        
        finally:
            file.seek(0)
        
        return issues, metadata
    
    def _validate_pdf_content(self, file) -> tuple[List[str], Dict[str, Any]]:
        """Validate PDF file content."""
        issues = []
        metadata = {}
        
        try:
            # Create a temporary file for PDF reading
            with tempfile.NamedTemporaryFile() as temp_file:
                file.seek(0)
                temp_file.write(file.read())
                temp_file.flush()
                
                with open(temp_file.name, 'rb') as pdf_file:
                    reader = PyPDF2.PdfReader(pdf_file)
                    
                    num_pages = len(reader.pages)
                    metadata['num_pages'] = num_pages
                    
                    # Check page count
                    if num_pages > self.MAX_PDF_PAGES:
                        issues.append(f"PDF has too many pages: {num_pages} (max: {self.MAX_PDF_PAGES})")
                    
                    # Check for encryption
                    if reader.is_encrypted:
                        issues.append("Encrypted PDFs are not allowed")
                    
                    # Check for JavaScript or forms
                    for page_num, page in enumerate(reader.pages):
                        if '/JS' in str(page) or '/JavaScript' in str(page):
                            issues.append(f"PDF contains JavaScript on page {page_num + 1}")
                        
                        if '/AcroForm' in str(page):
                            issues.append(f"PDF contains interactive forms on page {page_num + 1}")
                    
                    # Extract metadata
                    if reader.metadata:
                        pdf_metadata = reader.metadata
                        metadata.update({
                            'title': pdf_metadata.get('/Title', ''),
                            'author': pdf_metadata.get('/Author', ''),
                            'creator': pdf_metadata.get('/Creator', ''),
                            'producer': pdf_metadata.get('/Producer', '')
                        })
                        
                        # Check for suspicious metadata
                        for key, value in pdf_metadata.items():
                            if isinstance(value, str) and len(value) > 1000:
                                issues.append(f"Suspicious metadata field {key} is too long")
                
        except Exception as e:
            issues.append(f"Invalid PDF file: {str(e)}")
        
        finally:
            file.seek(0)
        
        return issues, metadata
    
    def _scan_for_malware(self, file) -> List[str]:
        """Scan file for malware using available scanner."""
        issues = []
        
        if not self.malware_scanner:
            return issues
        
        try:
            # This would integrate with ClamAV or similar
            # For now, it's a placeholder
            logger.info("Malware scanning not implemented yet")
        except Exception as e:
            logger.warning(f"Malware scan failed: {e}")
            issues.append("Could not perform malware scan")
        
        return issues
    
    def _detect_suspicious_patterns(self, file, mime_type: str) -> List[str]:
        """Detect suspicious patterns in file content."""
        issues = []
        
        try:
            # Read first 1KB for pattern analysis
            file.seek(0)
            content_sample = file.read(1024)
            file.seek(0)
            
            # Check for embedded executables
            if b'MZ' in content_sample or b'PK' in content_sample:
                if mime_type not in ['application/pdf', 'application/zip']:
                    issues.append("File may contain embedded executable content")
            
            # Check for script patterns
            script_patterns = [b'<script', b'javascript:', b'vbscript:', b'<?php']
            for pattern in script_patterns:
                if pattern in content_sample.lower():
                    issues.append(f"File contains suspicious script pattern")
                    break
            
            # Check for polyglot file signatures
            if content_sample.startswith(b'%PDF') and b'JFIF' in content_sample:
                issues.append("File appears to be a PDF/JPEG polyglot")
            
        except Exception as e:
            logger.warning(f"Pattern detection failed: {e}")
        
        return issues
    
    def _calculate_file_hash(self, file) -> str:
        """Calculate SHA-256 hash of file."""
        try:
            hasher = hashlib.sha256()
            file.seek(0)
            
            for chunk in iter(lambda: file.read(4096), b""):
                hasher.update(chunk)
            
            file.seek(0)
            return hasher.hexdigest()
            
        except Exception as e:
            logger.warning(f"Hash calculation failed: {e}")
            return ""
    
    def _init_malware_scanner(self):
        """Initialize malware scanner if available."""
        try:
            # Try to initialize ClamAV scanner
            # This would need pyclamd or similar library
            return None  # Placeholder
        except Exception:
            return None
    
    def strip_metadata(self, file, file_type: str):
        """Strip potentially sensitive metadata from file."""
        try:
            if file_type.startswith('image/'):
                return self._strip_image_metadata(file)
            elif file_type == 'application/pdf':
                return self._strip_pdf_metadata(file)
        except Exception as e:
            logger.warning(f"Metadata stripping failed: {e}")
        
        return file
    
    def _strip_image_metadata(self, file):
        """Strip EXIF and other metadata from image."""
        try:
            with Image.open(file) as img:
                # Create new image without metadata
                clean_img = Image.new(img.mode, img.size)
                clean_img.putdata(list(img.getdata()))
                
                # Save to temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                clean_img.save(temp_file.name, 'JPEG', quality=95)
                
                return temp_file.name
                
        except Exception as e:
            logger.warning(f"Image metadata stripping failed: {e}")
            return None
    
    def _strip_pdf_metadata(self, file):
        """Strip metadata from PDF."""
        try:
            # This would require more sophisticated PDF processing
            # For now, return original file
            return None
        except Exception as e:
            logger.warning(f"PDF metadata stripping failed: {e}")
            return None


def get_secure_validator() -> SecureReceiptValidator:
    """Factory function to get secure validator instance."""
    return SecureReceiptValidator()