"""
OCR Service - main interface for OCR operations.
Manages OCR backends and provides unified interface.
"""

import logging
from typing import List, Optional, Dict, Any
from django.conf import settings

from .ocr_backends import (
    OCRBackend, OCRResult, EasyOCRBackend, 
    TesseractBackend, FallbackOCRBackend
)

logger = logging.getLogger(__name__)


class OCRService:
    """
    Main OCR service that manages multiple backends and provides
    a unified interface for OCR operations.
    """
    
    def __init__(self):
        self._backends: List[OCRBackend] = []
        self._primary_backend: Optional[OCRBackend] = None
        self._fallback_backend: Optional[FallbackOCRBackend] = None
        self._initialized = False
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize OCR service with configuration.
        
        Args:
            config: Configuration dict with OCR settings
        """
        if self._initialized:
            return
        
        config = config or getattr(settings, 'OCR_CONFIG', {})
        
        # Create backend instances
        available_backends = []
        
        # EasyOCR
        if config.get('enable_easyocr', True):
            languages = config.get('easyocr_languages', ['pl', 'en'])
            backend = EasyOCRBackend(languages=languages)
            if backend.is_available:
                available_backends.append(backend)
                logger.info(f"EasyOCR backend initialized with languages: {languages}")
            else:
                logger.warning("EasyOCR backend not available")
        
        # Tesseract
        if config.get('enable_tesseract', True):
            language = config.get('tesseract_language', 'pol+eng')
            backend = TesseractBackend(language=language)
            if backend.is_available:
                available_backends.append(backend)
                logger.info(f"Tesseract backend initialized with language: {language}")
            else:
                logger.warning("Tesseract backend not available")
        
        self._backends = available_backends
        
        if not self._backends:
            logger.error("No OCR backends available!")
            return
        
        # Set primary backend (first available)
        self._primary_backend = self._backends[0]
        logger.info(f"Primary OCR backend: {self._primary_backend.name}")
        
        # Create fallback backend if multiple backends available
        if len(self._backends) > 1:
            self._fallback_backend = FallbackOCRBackend(self._backends)
            logger.info(f"Fallback OCR with {len(self._backends)} backends available")
        
        self._initialized = True
    
    def is_available(self) -> bool:
        """Check if any OCR backend is available."""
        if not self._initialized:
            self.initialize()
        return len(self._backends) > 0
    
    def get_available_backends(self) -> List[str]:
        """Get list of available backend names."""
        if not self._initialized:
            self.initialize()
        return [backend.name for backend in self._backends]
    
    def process_file(
        self, 
        file_path: str, 
        use_fallback: bool = True,
        preferred_backend: Optional[str] = None
    ) -> OCRResult:
        """
        Process file with OCR.
        
        Args:
            file_path: Path to file to process
            use_fallback: Whether to use fallback if primary backend fails
            preferred_backend: Specific backend to use
            
        Returns:
            OCRResult with extracted text and metadata
        """
        if not self._initialized:
            self.initialize()
        
        if not self._backends:
            return OCRResult(
                text="",
                confidence=0.0,
                backend="none",
                processing_time=0.0,
                metadata={'error': 'No OCR backends available'},
                success=False,
                error_message='No OCR backends available'
            )
        
        # Select backend to use
        backend = None
        
        if preferred_backend:
            # Find specific backend
            backend = next(
                (b for b in self._backends if b.name == preferred_backend),
                None
            )
            if not backend:
                logger.warning(f"Preferred backend '{preferred_backend}' not available")
        
        if not backend:
            # Use primary backend
            backend = self._primary_backend
        
        logger.info(f"Processing {file_path} with {backend.name}")
        
        # Try primary backend
        result = backend.process_file(file_path)
        
        if result.success and result.text.strip():
            logger.info(f"OCR successful with {backend.name}: {result.confidence:.2f} confidence")
            return result
        
        # Try fallback if enabled and available
        if use_fallback and self._fallback_backend and len(self._backends) > 1:
            logger.info(f"Primary backend failed, trying fallback")
            fallback_result = self._fallback_backend.process_file(file_path)
            
            if fallback_result.success:
                logger.info(f"Fallback OCR successful: {fallback_result.confidence:.2f} confidence")
                return fallback_result
            else:
                logger.warning("All OCR backends failed")
                return fallback_result
        
        logger.warning(f"OCR failed with {backend.name}")
        return result
    
    def extract_text_from_image(
        self, 
        image_path: str, 
        preferred_backend: Optional[str] = None
    ) -> OCRResult:
        """Extract text from image file."""
        return self.process_file(image_path, preferred_backend=preferred_backend)
    
    def extract_text_from_pdf(
        self, 
        pdf_path: str, 
        preferred_backend: Optional[str] = None
    ) -> OCRResult:
        """Extract text from PDF file."""
        return self.process_file(pdf_path, preferred_backend=preferred_backend)
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics and status."""
        if not self._initialized:
            self.initialize()
        
        return {
            'initialized': self._initialized,
            'backends_available': len(self._backends),
            'backend_names': [b.name for b in self._backends],
            'primary_backend': self._primary_backend.name if self._primary_backend else None,
            'fallback_available': self._fallback_backend is not None,
            'service_available': len(self._backends) > 0
        }


# Global OCR service instance
ocr_service = OCRService()


def get_ocr_service() -> OCRService:
    """Get the global OCR service instance."""
    return ocr_service


# Convenience functions
def process_receipt_file(file_path: str, use_fallback: bool = True) -> OCRResult:
    """
    Process receipt file with OCR.
    
    Args:
        file_path: Path to receipt file
        use_fallback: Whether to use fallback backends
        
    Returns:
        OCR result with extracted text
    """
    return get_ocr_service().process_file(file_path, use_fallback=use_fallback)


def is_ocr_available() -> bool:
    """Check if OCR service is available."""
    return get_ocr_service().is_available()


def get_ocr_backends() -> List[str]:
    """Get list of available OCR backends."""
    return get_ocr_service().get_available_backends()