"""
Integration tests for OCR backends and service.
"""

import pytest
from django.test import TestCase, override_settings

from inventory.models import Receipt

from .ocr_backends import (
    EasyOCRBackend,
    FallbackOCRBackend,
    OCRResult,
    TesseractBackend,
)
from .ocr_service import OCRService


class OCRResultTest(TestCase):
    """Test OCRResult dataclass."""

    def test_ocr_result_creation(self):
        """Test OCR result creation and conversion."""
        result = OCRResult(
            text="Test text",
            confidence=0.85,
            backend="test_backend",
            processing_time=1.5,
            metadata={"key": "value"},
        )

        self.assertEqual(result.text, "Test text")
        self.assertEqual(result.confidence, 0.85)
        self.assertEqual(result.backend, "test_backend")
        self.assertTrue(result.success)

        # Test to_dict conversion
        result_dict = result.to_dict()
        self.assertIn("text", result_dict)
        self.assertIn("confidence", result_dict)
        self.assertIn("backend", result_dict)
        self.assertEqual(result_dict["success"], True)

    def test_ocr_result_failure(self):
        """Test OCR result with failure."""
        result = OCRResult(
            text="",
            confidence=0.0,
            backend="test_backend",
            processing_time=0.5,
            metadata={},
            success=False,
            error_message="Test error",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Test error")


class EasyOCRBackendTest(TestCase):
    """Test EasyOCR backend."""

    def setUp(self):
        """Set up test backend."""
        self.backend = EasyOCRBackend(["en"])

    def test_backend_initialization(self):
        """Test backend initialization."""
        self.assertEqual(self.backend.name, "easyocr")
        self.assertEqual(self.backend.languages, ["en"])

    @pytest.mark.skipif(True, reason="Requires EasyOCR installation and real image processing")
    def test_extract_text_from_image_integration(self):
        """Test integration with real EasyOCR (requires installation)."""
        # Skip this test as it requires real EasyOCR installation
        # In a real implementation, you would test with actual image files
        self.skipTest("Integration test requires EasyOCR installation and real image files")

    def test_extract_text_unavailable_backend(self):
        """Test extraction with unavailable backend."""
        self.backend.is_available = False

        result = self.backend.extract_text_from_image("/fake/path.jpg")

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "EasyOCR not available")


class TesseractBackendTest(TestCase):
    """Test Tesseract backend."""

    def setUp(self):
        """Set up test backend."""
        self.backend = TesseractBackend("eng")

    def test_backend_initialization(self):
        """Test backend initialization."""
        self.assertEqual(self.backend.name, "tesseract")
        self.assertEqual(self.backend.language, "eng")

    @pytest.mark.skipif(True, reason="Requires Tesseract installation and real image processing")
    def test_extract_text_from_image_integration(self):
        """Test integration with real Tesseract (requires installation)."""
        # Skip this test as it requires real Tesseract installation
        # In a real implementation, you would test with actual image files
        self.skipTest("Integration test requires Tesseract installation and real image files")

    def test_extract_text_unavailable_backend(self):
        """Test extraction with unavailable backend."""
        self.backend.is_available = False

        result = self.backend.extract_text_from_image("/fake/path.jpg")

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Tesseract not available")


class FallbackOCRBackendTest(TestCase):
    """Test fallback OCR backend."""

    def test_fallback_backend_initialization(self):
        """Test fallback backend initialization."""
        backend1 = EasyOCRBackend(["en"])
        backend2 = TesseractBackend("eng")
        
        fallback = FallbackOCRBackend([backend1, backend2])
        
        self.assertEqual(fallback.name, "fallback")
        self.assertEqual(len(fallback.backends), 2)

    @pytest.mark.skipif(True, reason="Requires real OCR backends for integration testing")
    def test_fallback_integration(self):
        """Test fallback behavior with real backends."""
        # Skip this test as it requires real OCR backend installations
        self.skipTest("Integration test requires real OCR backends")


@override_settings(
    OCR_CONFIG={
        "enable_easyocr": True,
        "enable_tesseract": False,
        "easyocr_languages": ["en"],
        "tesseract_language": "eng",
        "fallback_enabled": True,
    }
)
class OCRServiceTest(TestCase):
    """Test OCR service."""

    def setUp(self):
        """Set up fresh OCR service for each test."""
        # Create new service instance for testing
        self.service = OCRService()

    @pytest.mark.skipif(True, reason="Requires real OCR backends for service initialization")
    def test_service_initialization_integration(self):
        """Test service initialization with real backends."""
        # Skip this test as it requires real OCR installations
        self.skipTest("Integration test requires real OCR backend installations")

    def test_service_no_backends_available(self):
        """Test service when no backends are available."""
        # Override settings to disable all backends
        with self.settings(
            OCR_CONFIG={
                "enable_easyocr": False,
                "enable_tesseract": False,
            }
        ):
            self.service.initialize()

            self.assertFalse(self.service.is_available())
            self.assertEqual(len(self.service.get_available_backends()), 0)

    @pytest.mark.skipif(True, reason="Requires real OCR backends for file processing")
    def test_process_file_integration(self):
        """Test file processing with real backends."""
        # Skip this test as it requires real OCR backends and files
        self.skipTest("Integration test requires real OCR backends and files")

    def test_get_service_stats(self):
        """Test getting service statistics."""
        stats = self.service.get_service_stats()

        self.assertIn("initialized", stats)
        self.assertIn("backends_available", stats)
        self.assertIn("backend_names", stats)
        self.assertIn("service_available", stats)


class ReceiptOCRIntegrationTest(TestCase):
    """Integration tests for receipt OCR processing."""

    def setUp(self):
        """Set up test receipt."""
        from django.utils import timezone

        self.receipt = Receipt.objects.create(
            purchased_at=timezone.now(),
            total=0.00,
            source_file_path="/fake/receipt.pdf",
            status="pending_ocr",
        )

    @pytest.mark.skipif(True, reason="Requires real OCR service for receipt processing integration")
    def test_process_receipt_ocr_integration(self):
        """Test receipt OCR processing integration with real services."""
        # Skip this test as it requires real OCR services
        # In a real implementation, you would test with actual receipt files and OCR services
        self.skipTest("Integration test requires real OCR service and receipt files")

    def test_receipt_ocr_error_handling(self):
        """Test error handling for receipt OCR processing."""
        from .receipt_service import ReceiptService

        service = ReceiptService()

        # Test with receipt that has invalid file path
        self.receipt.source_file_path = "/nonexistent/file.pdf"
        self.receipt.save()

        # Should handle gracefully without crashing
        success = service.process_receipt_ocr(self.receipt.id)
        
        # Verify it handled the error appropriately
        self.assertFalse(success)
        self.receipt.refresh_from_db()
        self.assertTrue(self.receipt.status in ["error", "ocr_failed", "pending_ocr"])
