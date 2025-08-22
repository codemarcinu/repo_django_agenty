"""
Unit tests for MistralOcrService.
Tests the integration with Mistral OCR API and parsing functionality.
"""

import json
from unittest.mock import Mock, patch, AsyncMock
from django.test import TestCase
from django.conf import settings

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

    @patch('builtins.open', create=True)
    @patch('httpx.AsyncClient')
    async def test_extract_data_from_file_success(self, mock_async_client, mock_open):
        """Test successful data extraction from file."""
        # Mock file operations
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = b"fake image data"

        # Mock HTTP client
        mock_client = Mock()
        mock_async_client.return_value.__aenter__.return_value = mock_client

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "extracted_items": [
                {
                    "description": "Mleko 3,2%",
                    "price": 2.99,
                    "quantity": 1.0,
                    "unit": "szt."
                },
                {
                    "description": "Chleb graham",
                    "price": 3.50,
                    "quantity": 1.0,
                    "unit": "szt."
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response

        # Test the method
        result = await self.service.extract_data_from_file("/path/to/test_receipt.png")

        # Verify result
        self.assertIsInstance(result, ParsedReceipt)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].product_name, "Mleko 3,2%")
        self.assertEqual(result.items[0].price, 2.99)
        self.assertEqual(result.items[1].product_name, "Chleb graham")
        self.assertEqual(result.items[1].price, 3.50)

    @patch('builtins.open', create=True)
    @patch('httpx.AsyncClient')
    async def test_extract_data_from_file_api_error(self, mock_async_client, mock_open):
        """Test handling of API errors."""
        # Mock file operations
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = b"fake image data"

        # Mock HTTP client with error
        mock_client = Mock()
        mock_async_client.return_value.__aenter__.return_value = mock_client

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_client.post.return_value = mock_response
        mock_client.post.return_value.raise_for_status.side_effect = Exception("API Error")

        # Test that exception is raised
        with self.assertRaises(Exception):
            await self.service.extract_data_from_file("/path/to/test_receipt.png")

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

    @patch('chatbot.services.mistral_ocr_service.fitz.open')
    def test_convert_pdf_to_images_malformed_pdf(self, mock_fitz_open):
        """Test PDF conversion with malformed PDF."""
        # Mock PyMuPDF to raise an exception
        mock_fitz_open.side_effect = Exception("Invalid PDF")

        result = self.service._convert_pdf_to_images("/path/to/malformed.pdf")
        self.assertEqual(result, [])

    @patch('chatbot.services.mistral_ocr_service.fitz.open')
    def test_convert_pdf_to_images_empty_pdf(self, mock_fitz_open):
        """Test PDF conversion with empty PDF."""
        # Mock empty PDF document
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=0)
        mock_fitz_open.return_value = mock_doc

        result = self.service._convert_pdf_to_images("/path/to/empty.pdf")
        self.assertEqual(result, [])

    @patch('chatbot.services.mistral_ocr_service.fitz.open')
    def test_convert_pdf_to_images_success(self, mock_fitz_open):
        """Test successful PDF conversion to images."""
        # Mock PDF document with one page
        mock_page = Mock()
        mock_pix = Mock()
        mock_pix.tobytes.return_value = b"fake_png_data"
        mock_page.get_pixmap.return_value = mock_pix

        mock_doc = Mock()
        # Mock __len__ method properly
        mock_doc.__len__ = Mock(return_value=1)
        mock_doc.load_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc

        # Mock PIL Image
        with patch('chatbot.services.mistral_ocr_service.Image') as mock_image:
            mock_img = Mock()
            mock_img.mode = 'RGB'
            mock_image.open.return_value = mock_img

            result = self.service._convert_pdf_to_images("/path/to/test.pdf")

            self.assertEqual(len(result), 1)
            self.assertTrue(result[0].startswith("data:image/jpeg;base64,"))

    @patch('builtins.open', create=True)
    @patch('httpx.AsyncClient')
    @patch('chatbot.services.mistral_ocr_service.Path')
    async def test_extract_data_from_file_pdf_success(self, mock_path, mock_async_client, mock_open):
        """Test successful PDF processing."""
        # Mock Path.exists() to return True
        mock_path.return_value.exists.return_value = True
        mock_path.return_value.suffix.lower.return_value = '.pdf'

        # Mock file operations for PDF
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = b"fake pdf data"

        # Mock PDF conversion to return one image
        with patch.object(self.service, '_convert_pdf_to_images') as mock_convert:
            mock_convert.return_value = ["data:image/jpeg;base64,fake_image_data"]

            # Mock HTTP client with AsyncMock
            mock_client = AsyncMock()
            mock_async_client.return_value.__aenter__.return_value = mock_client

            # Mock successful API response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "store_name": "Test Store",
                                "total_amount": 10.99,
                                "items": [
                                    {
                                        "product_name": "Test Product",
                                        "quantity": 1.0,
                                        "unit": "szt.",
                                        "price": 10.99
                                    }
                                ]
                            })
                        }
                    }
                ]
            }
            mock_response.raise_for_status.return_value = None
            mock_client.post.return_value = mock_response

            # Test the method with PDF file
            result = await self.service.extract_data_from_file("/path/to/test_receipt.pdf")

            # Verify result
            self.assertIsInstance(result, ParsedReceipt)
            self.assertEqual(result.store_name, "Test Store")
            self.assertEqual(result.total_amount, 10.99)
            self.assertEqual(len(result.items), 1)
            self.assertEqual(result.items[0].product_name, "Test Product")

    @patch('builtins.open', create=True)
    @patch('httpx.AsyncClient')
    async def test_extract_data_from_file_pdf_conversion_failure(self, mock_async_client, mock_open):
        """Test PDF processing when conversion fails."""
        # Mock file operations for PDF
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = b"fake pdf data"

        # Mock PDF conversion to fail
        with patch.object(self.service, '_convert_pdf_to_images') as mock_convert:
            mock_convert.return_value = []

            # Test the method with PDF file
            result = await self.service.extract_data_from_file("/path/to/test_receipt.pdf")

            # Should return None when PDF conversion fails
            self.assertIsNone(result)
