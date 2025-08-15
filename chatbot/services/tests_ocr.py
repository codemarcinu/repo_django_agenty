"""
Tests for OCR backends and service.
"""

import os
import tempfile
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile

from .ocr_backends import OCRResult, EasyOCRBackend, TesseractBackend, FallbackOCRBackend
from .ocr_service import OCRService, get_ocr_service
from inventory.models import Receipt


class OCRResultTest(TestCase):
    """Test OCRResult dataclass."""
    
    def test_ocr_result_creation(self):
        """Test OCR result creation and conversion."""
        result = OCRResult(
            text="Test text",
            confidence=0.85,
            backend="test_backend",
            processing_time=1.5,
            metadata={"key": "value"}
        )
        
        self.assertEqual(result.text, "Test text")
        self.assertEqual(result.confidence, 0.85)
        self.assertEqual(result.backend, "test_backend")
        self.assertTrue(result.success)
        
        # Test to_dict conversion
        result_dict = result.to_dict()
        self.assertIn('text', result_dict)
        self.assertIn('confidence', result_dict)
        self.assertIn('backend', result_dict)
        self.assertEqual(result_dict['success'], True)
    
    def test_ocr_result_failure(self):
        """Test OCR result with failure."""
        result = OCRResult(
            text="",
            confidence=0.0,
            backend="test_backend",
            processing_time=0.5,
            metadata={},
            success=False,
            error_message="Test error"
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Test error")


class EasyOCRBackendTest(TestCase):
    """Test EasyOCR backend."""
    
    def setUp(self):
        """Set up test backend."""
        self.backend = EasyOCRBackend(['en'])
    
    def test_backend_initialization(self):
        """Test backend initialization."""
        self.assertEqual(self.backend.name, 'easyocr')
        self.assertEqual(self.backend.languages, ['en'])
    
    @patch('easyocr.Reader')
    def test_extract_text_from_image_success(self, mock_reader_class):
        """Test successful text extraction from image."""
        # Mock EasyOCR reader
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [
            ([[0, 0], [100, 0], [100, 30], [0, 30]], 'Hello', 0.9),
            ([[0, 35], [100, 35], [100, 65], [0, 65]], 'World', 0.8)
        ]
        mock_reader_class.return_value = mock_reader
        
        # Force backend to be available for testing
        self.backend.is_available = True
        self.backend._reader = mock_reader
        
        result = self.backend.extract_text_from_image('/fake/path.jpg')
        
        self.assertTrue(result.success)
        self.assertEqual(result.text, 'Hello\nWorld')
        self.assertAlmostEqual(result.confidence, 0.85, places=2)  # Average of 0.9 and 0.8
        self.assertEqual(result.backend, 'easyocr')
    
    def test_extract_text_unavailable_backend(self):
        """Test extraction with unavailable backend."""
        self.backend.is_available = False
        
        result = self.backend.extract_text_from_image('/fake/path.jpg')
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, 'EasyOCR not available')


class TesseractBackendTest(TestCase):
    """Test Tesseract backend."""
    
    def setUp(self):
        """Set up test backend."""
        self.backend = TesseractBackend('eng')
    
    def test_backend_initialization(self):
        """Test backend initialization."""
        self.assertEqual(self.backend.name, 'tesseract')
        self.assertEqual(self.backend.language, 'eng')
    
    @patch('pytesseract.image_to_data')
    @patch('PIL.Image.open')
    @patch('pytesseract.get_tesseract_version')
    def test_extract_text_from_image_success(self, mock_tesseract_version, mock_image_open, mock_image_to_data):
        """Test successful text extraction with Tesseract."""
        # Mock PIL Image
        mock_image = MagicMock()
        mock_image_open.return_value = mock_image
        
        # Mock Tesseract data output
        mock_image_to_data.return_value = {
            'conf': [90, 85, 0, 80],
            'text': ['Hello', 'World', '', 'Test']
        }
        
        # Mock tesseract version check to make backend available
        mock_tesseract_version.return_value = "4.1.1"
        
        # Force backend to be available for testing
        self.backend.is_available = True
        
        result = self.backend.extract_text_from_image('/fake/path.jpg')
        
        self.assertTrue(result.success)
        self.assertEqual(result.text, 'Hello World Test')
        self.assertGreater(result.confidence, 0)
        self.assertEqual(result.backend, 'tesseract')
    
    def test_extract_text_unavailable_backend(self):
        """Test extraction with unavailable backend."""
        self.backend.is_available = False
        
        result = self.backend.extract_text_from_image('/fake/path.jpg')
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, 'Tesseract not available')


class FallbackOCRBackendTest(TestCase):
    """Test fallback OCR backend."""
    
    def test_fallback_with_successful_backend(self):
        """Test fallback that succeeds with first backend."""
        # Create mock backends
        successful_backend = MagicMock()
        successful_backend.name = 'backend1'
        successful_backend.is_available = True
        successful_backend.extract_text_from_image.return_value = OCRResult(
            text="Success",
            confidence=0.9,
            backend="backend1",
            processing_time=1.0,
            metadata={},
            success=True
        )
        
        failing_backend = MagicMock()
        failing_backend.name = 'backend2'
        failing_backend.is_available = True
        
        fallback = FallbackOCRBackend([successful_backend, failing_backend])
        
        result = fallback.extract_text_from_image('/fake/path.jpg')
        
        self.assertTrue(result.success)
        self.assertEqual(result.text, "Success")
        self.assertIn('fallback_used', result.metadata)
        self.assertEqual(result.metadata['successful_backend'], 'backend1')
    
    def test_fallback_with_all_failing_backends(self):
        """Test fallback when all backends fail."""
        # Create mock failing backends
        failing_backend1 = MagicMock()
        failing_backend1.name = 'backend1'
        failing_backend1.is_available = True
        failing_backend1.extract_text_from_image.return_value = OCRResult(
            text="",
            confidence=0.0,
            backend="backend1",
            processing_time=1.0,
            metadata={},
            success=False,
            error_message="Backend 1 failed"
        )
        
        failing_backend2 = MagicMock()
        failing_backend2.name = 'backend2'
        failing_backend2.is_available = True
        failing_backend2.extract_text_from_image.return_value = OCRResult(
            text="",
            confidence=0.0,
            backend="backend2",
            processing_time=1.0,
            metadata={},
            success=False,
            error_message="Backend 2 failed"
        )
        
        fallback = FallbackOCRBackend([failing_backend1, failing_backend2])
        
        result = fallback.extract_text_from_image('/fake/path.jpg')
        
        self.assertFalse(result.success)
        self.assertIn('all_failed', result.metadata)
        self.assertEqual(len(result.metadata['attempted_backends']), 2)


@override_settings(OCR_CONFIG={
    'enable_easyocr': True,
    'enable_tesseract': False,
    'easyocr_languages': ['en'],
    'tesseract_language': 'eng',
    'fallback_enabled': True,
})
class OCRServiceTest(TestCase):
    """Test OCR service."""
    
    def setUp(self):
        """Set up fresh OCR service for each test."""
        # Create new service instance for testing
        self.service = OCRService()
    
    @patch('chatbot.services.ocr_backends.EasyOCRBackend')
    def test_service_initialization(self, mock_easyocr):
        """Test service initialization with mocked backends."""
        # Mock EasyOCR backend
        mock_backend = MagicMock()
        mock_backend.is_available = True
        mock_backend.name = 'easyocr'
        mock_easyocr.return_value = mock_backend
        
        self.service.initialize()
        
        self.assertTrue(self.service._initialized)
        self.assertTrue(self.service.is_available())
        self.assertIn('easyocr', self.service.get_available_backends())
    
    def test_service_no_backends_available(self):
        """Test service when no backends are available."""
        # Override settings to disable all backends
        with self.settings(OCR_CONFIG={
            'enable_easyocr': False,
            'enable_tesseract': False,
        }):
            self.service.initialize()
            
            self.assertFalse(self.service.is_available())
            self.assertEqual(len(self.service.get_available_backends()), 0)
    
    @patch('chatbot.services.ocr_backends.EasyOCRBackend')
    def test_process_file_success(self, mock_easyocr):
        """Test successful file processing."""
        # Mock successful backend
        mock_backend = MagicMock()
        mock_backend.is_available = True
        mock_backend.name = 'easyocr'
        
        # Create a successful OCR result
        success_result = OCRResult(
            text="Extracted text",
            confidence=0.85,
            backend="easyocr",
            processing_time=2.0,
            metadata={},
            success=True
        )
        mock_backend.process_file.return_value = success_result
        mock_easyocr.return_value = mock_backend
        
        # Initialize service with mocked backend
        self.service.initialize()
        
        # Manually set the backend since mocking doesn't work perfectly
        self.service._backends = [mock_backend]
        self.service._primary_backend = mock_backend
        
        # Verify backend was set up correctly
        self.assertTrue(self.service.is_available())
        
        result = self.service.process_file('/fake/receipt.pdf')
        
        self.assertTrue(result.success)
        self.assertEqual(result.text, "Extracted text")
        self.assertEqual(result.confidence, 0.85)
    
    def test_get_service_stats(self):
        """Test getting service statistics."""
        stats = self.service.get_service_stats()
        
        self.assertIn('initialized', stats)
        self.assertIn('backends_available', stats)
        self.assertIn('backend_names', stats)
        self.assertIn('service_available', stats)


class ReceiptOCRIntegrationTest(TestCase):
    """Integration tests for receipt OCR processing."""
    
    def setUp(self):
        """Set up test receipt."""
        from django.utils import timezone
        self.receipt = Receipt.objects.create(
            purchased_at=timezone.now(),
            total=0.00,
            source_file_path='/fake/receipt.pdf',
            status='pending_ocr'
        )
    
    @patch('chatbot.services.receipt_service.get_ocr_service')
    def test_process_receipt_ocr_success(self, mock_get_ocr_service):
        """Test successful OCR processing of receipt."""
        # Mock OCR service
        mock_service = MagicMock()
        mock_service.is_available.return_value = True
        mock_service.process_file.return_value = OCRResult(
            text="TESCO\\nMleko 2.99\\nChleb 3.50\\nRazem: 6.49",
            confidence=0.9,
            backend="easyocr",
            processing_time=3.0,
            metadata={'pages_processed': 1},
            success=True
        )
        mock_get_ocr_service.return_value = mock_service
        
        from .receipt_service import ReceiptService
        service = ReceiptService()
        
        success = service.process_receipt_ocr(self.receipt.id)
        
        self.assertTrue(success)
        
        # Check receipt was updated
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, 'ocr_completed')
        self.assertIsNotNone(self.receipt.raw_text)
        self.assertIn('OCR completed', self.receipt.processing_notes)
    
    @patch('chatbot.services.receipt_service.get_ocr_service')
    def test_process_receipt_ocr_failure(self, mock_get_ocr_service):
        """Test OCR processing failure."""
        # Mock OCR service failure
        mock_service = MagicMock()
        mock_service.is_available.return_value = True
        mock_service.process_file.return_value = OCRResult(
            text="",
            confidence=0.0,
            backend="easyocr",
            processing_time=1.0,
            metadata={},
            success=False,
            error_message="Could not extract text"
        )
        mock_get_ocr_service.return_value = mock_service
        
        from .receipt_service import ReceiptService
        service = ReceiptService()
        
        success = service.process_receipt_ocr(self.receipt.id)
        
        self.assertFalse(success)
        
        # Check receipt was marked as error
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, 'error')
        self.assertIn('OCR failed', self.receipt.processing_notes)
    
    @patch('chatbot.services.receipt_service.get_ocr_service')
    def test_process_receipt_ocr_no_service(self, mock_get_ocr_service):
        """Test OCR processing when no service available."""
        # Mock unavailable OCR service
        mock_service = MagicMock()
        mock_service.is_available.return_value = False
        mock_get_ocr_service.return_value = mock_service
        
        from .receipt_service import ReceiptService
        service = ReceiptService()
        
        success = service.process_receipt_ocr(self.receipt.id)
        
        self.assertFalse(success)
        
        # Check receipt was marked as error
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, 'error')
        self.assertIn('No OCR backends available', self.receipt.processing_notes)