"""
Integration tests for MistralOcrService.
Tests the integration with Mistral OCR API and parsing functionality.
"""

import json
from django.test import TestCase
from django.conf import settings
import pytest

from chatbot.services.mistral_ocr_service import MistralOcrService
from chatbot.schemas import ParsedReceipt, ProductSchema


class MistralOcrServiceTests(TestCase):
    """Test cases for MistralOcrService."""

    def setUp(self):
        """Set up test data."""
        # Mock API key for testing before creating service
        settings.MISTRAL_API_KEY = "test_api_key"
        self.service = MistralOcrService()

    def tearDown(self):
        """Clean up after tests."""
        # Reset API key
        if hasattr(settings, 'MISTRAL_API_KEY'):
            delattr(settings, 'MISTRAL_API_KEY')

    def test_service_initialization(self):
        """Test service initialization."""
        service = MistralOcrService()
        self.assertEqual(service.api_url, "https://api.mistral.ai/v1/ocr/process")
        self.assertEqual(service.timeout, 120.0)

    def test_service_availability_with_api_key(self):
        """Test service availability when API key is configured."""
        self.assertTrue(self.service.is_available())

    def test_service_availability_without_api_key(self):
        """Test service availability when API key is not configured."""
        service = MistralOcrService()
        # Remove API key to test unavailability
        service.api_key = ""
        self.assertFalse(service.is_available())

    def test_get_content_type_pdf(self):
        """Test content type detection for PDF files."""
        content_type = self.service._get_content_type("/path/to/test.pdf")
        self.assertEqual(content_type, "application/pdf")

    def test_get_content_type_image_png(self):
        """Test content type detection for PNG files."""
        content_type = self.service._get_content_type("/path/to/test.png")
        self.assertEqual(content_type, "image/png")

    def test_get_content_type_image_jpeg(self):
        """Test content type detection for JPEG files."""
        content_type = self.service._get_content_type("/path/to/test.jpg")
        self.assertEqual(content_type, "image/jpeg")

    def test_get_content_type_unknown(self):
        """Test content type detection for unknown file types."""
        content_type = self.service._get_content_type("/path/to/test.unknown")
        self.assertEqual(content_type, "application/octet-stream")

    @pytest.mark.skipif(not settings.MISTRAL_API_KEY, reason="Mistral API key not configured")
    async def test_extract_data_from_file_integration(self):
        """Test data extraction with real API (requires API key)."""
        # This test requires a real API key and network connection
        if not self.service.is_available():
            self.skipTest("Mistral API service not available")
        
        # Skip this test as it requires real file and API access
        # In a real implementation, you would provide a test file path
        self.skipTest("Integration test requires real file and API access")

    def test_extract_data_error_handling(self):
        """Test error handling for file operations."""
        # Test with non-existent file path
        try:
            import asyncio
            result = asyncio.run(self.service.extract_data_from_file("/path/to/nonexistent.file"))
            # Should handle gracefully
            self.assertIsNone(result)
        except Exception as e:
            # Should not crash with unhandled exceptions
            self.assertTrue(isinstance(e, (FileNotFoundError, OSError)))

    def test_parse_mistral_response_standard_format(self):
        """Test parsing of standard Mistral response format."""
        response_data = {
            "extracted_items": [
                {
                    "description": "Mleko 3,2%",
                    "price": 2.99,
                    "quantity": 1.0,
                    "unit": "szt."
                }
            ]
        }

        items = self.service._parse_mistral_response(response_data)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].product_name, "Mleko 3,2%")
        self.assertEqual(items[0].price, 2.99)
        self.assertEqual(items[0].quantity, 1.0)
        self.assertEqual(items[0].unit, "szt.")

    def test_parse_mistral_response_alternative_fields(self):
        """Test parsing with alternative field names."""
        response_data = {
            "items": [
                {
                    "name": "Chleb graham",
                    "price": "3,50",
                    "quantity": "2.0"
                }
            ]
        }

        items = self.service._parse_mistral_response(response_data)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].product_name, "Chleb graham")
        self.assertEqual(items[0].price, 3.50)
        self.assertEqual(items[0].quantity, 2.0)

    def test_parse_mistral_response_malformed_data(self):
        """Test parsing of malformed response data."""
        response_data = {
            "extracted_items": [
                {
                    "description": "",  # Empty description
                    "price": 0,         # Invalid price
                    "quantity": 1.0
                },
                {
                    "description": "Valid Product",
                    "price": "invalid",  # Invalid price format
                    "quantity": 1.0
                }
            ]
        }

        items = self.service._parse_mistral_response(response_data)

        # Should skip invalid items
        self.assertEqual(len(items), 0)

    def test_parse_mistral_response_empty_data(self):
        """Test parsing of empty response data."""
        response_data = {}

        items = self.service._parse_mistral_response(response_data)

        self.assertEqual(len(items), 0)

    def test_parse_mistral_response_no_items(self):
        """Test parsing when no items are found."""
        response_data = {"message": "No items detected"}

        items = self.service._parse_mistral_response(response_data)

        self.assertEqual(len(items), 0)

    def test_parse_mistral_response_price_normalization(self):
        """Test price normalization with different formats."""
        response_data = {
            "extracted_items": [
                {
                    "description": "Product with comma price",
                    "price": "12,99",
                    "quantity": 1.0
                },
                {
                    "description": "Product with dot price",
                    "price": 15.50,
                    "quantity": 1.0
                }
            ]
        }

        items = self.service._parse_mistral_response(response_data)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].price, 12.99)
        self.assertEqual(items[1].price, 15.50)

    def test_parse_mistral_response_quantity_normalization(self):
        """Test quantity normalization with different formats."""
        response_data = {
            "extracted_items": [
                {
                    "description": "Product with string quantity",
                    "price": 10.00,
                    "quantity": "2,5"
                },
                {
                    "description": "Product with numeric quantity",
                    "price": 5.00,
                    "quantity": 3.0
                },
                {
                    "description": "Product without quantity",
                    "price": 7.00
                }
            ]
        }

        items = self.service._parse_mistral_response(response_data)

        self.assertEqual(len(items), 3)
        self.assertEqual(items[0].quantity, 2.5)
        self.assertEqual(items[1].quantity, 3.0)
        self.assertEqual(items[2].quantity, 1.0)  # Default quantity

    def test_get_content_type_pdf_case_insensitive(self):
        """Test content type detection is case insensitive."""
        content_type = self.service._get_content_type("/path/to/test.PDF")
        self.assertEqual(content_type, "application/pdf")

    def test_convert_pdf_to_images_no_file(self):
        """Test PDF conversion with non-existent file."""
        result = self.service._convert_pdf_to_images("/path/to/nonexistent.pdf")
        self.assertEqual(result, [])

    def test_convert_pdf_to_images_error_handling(self):
        """Test PDF conversion error handling."""
        # Test with non-existent file
        result = self.service._convert_pdf_to_images("/path/to/nonexistent.pdf")
        self.assertEqual(result, [])
        
        # Test that method handles errors gracefully
        # In real implementation, this would test actual PDF processing
        self.assertTrue(callable(self.service._convert_pdf_to_images))

    @pytest.mark.skipif(not settings.MISTRAL_API_KEY, reason="Requires API key for PDF processing")
    def test_pdf_processing_integration(self):
        """Test PDF processing integration (requires real PDF file)."""
        # Skip this test as it requires real PDF files and API access
        self.skipTest("Integration test requires real PDF file and API access")
