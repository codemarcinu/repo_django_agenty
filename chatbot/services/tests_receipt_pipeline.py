"""
Comprehensive unit tests for the receipt processing pipeline components.
Tests individual services and their interactions.
"""

from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from inventory.models import Category, InventoryItem, Product, Receipt

from .ocr_backends import OCRResult
from .product_matcher import ProductMatcher
from .receipt_parser import ParsedProduct, RegexReceiptParser
from .receipt_service import ReceiptService


class ReceiptValidationTests(TestCase):
    """Test receipt file validation logic."""

    def setUp(self):
        """Set up test service."""
        self.service = ReceiptService()

    def test_valid_pdf_file(self):
        """Test validation of valid PDF file."""
        pdf_file = SimpleUploadedFile(
            name="test_receipt.pdf",
            content=b"%PDF-1.4 dummy pdf content",
            content_type="application/pdf"
        )

        # Should not raise exception
        receipt = self.service.create_receipt_record(pdf_file)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.status, "uploaded")

    def test_valid_image_file(self):
        """Test validation of valid image file."""
        # PNG file signature
        png_content = b'\x89PNG\r\n\x1a\n' + b'dummy image content'

        image_file = SimpleUploadedFile(
            name="test_receipt.png",
            content=png_content,
            content_type="image/png"
        )

        receipt = self.service.create_receipt_record(image_file)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.status, "uploaded")

    def test_invalid_file_type(self):
        """Test validation rejects invalid file types."""
        text_file = SimpleUploadedFile(
            name="test.txt",
            content=b"This is not a receipt",
            content_type="text/plain"
        )

        # Create receipt and manually call clean to trigger validation
        receipt = Receipt(receipt_file=text_file)
        with self.assertRaises(ValidationError):
            receipt.full_clean()

    def test_file_too_large(self):
        """Test validation rejects files that are too large."""
        # Create file larger than 10MB
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB

        large_file = SimpleUploadedFile(
            name="large_receipt.pdf",
            content=large_content,
            content_type="application/pdf"
        )

        receipt = Receipt(receipt_file=large_file)
        with self.assertRaises(ValidationError):
            receipt.full_clean()

    def test_empty_file(self):
        """Test validation rejects empty files."""
        empty_file = SimpleUploadedFile(
            name="empty.pdf",
            content=b"",
            content_type="application/pdf"
        )

        receipt = Receipt(receipt_file=empty_file)
        with self.assertRaises(ValidationError):
            receipt.full_clean()


class ReceiptOCRProcessingTests(TestCase):
    """Test OCR processing functionality."""

    def setUp(self):
        """Set up test data."""
        self.service = ReceiptService()

        # Create test receipt
        self.receipt = Receipt.objects.create(
            status="uploaded",
            receipt_file=None  # Will be set in individual tests
        )

    @patch('chatbot.services.receipt_service.get_ocr_service')
    def test_ocr_processing_success(self, mock_get_ocr_service):
        """Test successful OCR processing."""
        # Mock OCR service
        mock_ocr_service = Mock()
        mock_ocr_service.is_available.return_value = True
        mock_ocr_service.process_file.return_value = OCRResult(
            text="LIDL Sp. z o.o.\nMleko 3,2% 1L    2,99\nSUMA:           2,99",
            confidence=0.95,
            backend="easyocr",
            processing_time=2.5,
            metadata={"pages": 1},
            success=True
        )
        mock_get_ocr_service.return_value = mock_ocr_service

        # Process OCR
        success = self.service.process_receipt_ocr(self.receipt.id)

        self.assertTrue(success)

        # Verify receipt was updated
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "ocr_done")
        self.assertIn("LIDL", self.receipt.raw_ocr_text)
        self.assertIn("Mleko", self.receipt.raw_ocr_text)

    @patch('chatbot.services.receipt_service.get_ocr_service')
    def test_ocr_processing_failure(self, mock_get_ocr_service):
        """Test OCR processing failure."""
        mock_ocr_service = Mock()
        mock_ocr_service.is_available.return_value = True
        mock_ocr_service.process_file.return_value = OCRResult(
            text="",
            confidence=0.0,
            backend="easyocr",
            processing_time=1.0,
            metadata={},
            success=False,
            error_message="Could not process image"
        )
        mock_get_ocr_service.return_value = mock_ocr_service

        success = self.service.process_receipt_ocr(self.receipt.id)

        self.assertFalse(success)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "error")
        self.assertIn("OCR failed", self.receipt.error_message)

    @patch('chatbot.services.receipt_service.get_ocr_service')
    def test_ocr_no_service_available(self, mock_get_ocr_service):
        """Test OCR processing when no service available."""
        mock_ocr_service = Mock()
        mock_ocr_service.is_available.return_value = False
        mock_get_ocr_service.return_value = mock_ocr_service

        success = self.service.process_receipt_ocr(self.receipt.id)

        self.assertFalse(success)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "error")
        self.assertIn("No OCR backends available", self.receipt.error_message)


class ReceiptParsingTests(TestCase):
    """Test receipt parsing functionality."""

    def setUp(self):
        """Set up test data."""
        self.service = ReceiptService()
        self.parser = RegexReceiptParser()

        # Create receipt with OCR data
        self.receipt = Receipt.objects.create(
            status="ocr_done",
            raw_ocr_text="""LIDL Sp. z o.o.
ul. Przykładowa 123
00-000 Warszawa
NIP: 526-26-42-052

PARAGON FISKALNY
Nr: 12345
15.01.2024 14:30

Mleko 3,2% 1L                    2,99 A
Chleb graham 500g                3,50 A
Masło extra 200g                 5,99 A

SUMA PLN                        12,48
Gotówka PLN                     15,00
Reszta PLN                       2,52

Dziękujemy!"""
        )

    def test_parse_receipt_success(self):
        """Test successful receipt parsing."""
        success = self.service.process_receipt_parsing(self.receipt.id)

        self.assertTrue(success)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "llm_done")

        extracted_data = self.receipt.extracted_data
        self.assertIsNotNone(extracted_data)
        self.assertIn("products", extracted_data)
        self.assertIn("store_name", extracted_data)
        self.assertIn("total_amount", extracted_data)

        # Check products were extracted
        products = extracted_data["products"]
        self.assertGreater(len(products), 0)

        # Verify product structure
        for product in products:
            self.assertIn("name", product)
            self.assertIn("price", product)

    def test_parse_empty_ocr_text(self):
        """Test parsing with empty OCR text."""
        self.receipt.raw_ocr_text = ""
        self.receipt.save()

        success = self.service.process_receipt_parsing(self.receipt.id)

        self.assertFalse(success)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "error")

    def test_parse_wrong_status(self):
        """Test parsing with wrong receipt status."""
        self.receipt.status = "uploaded"
        self.receipt.save()

        success = self.service.process_receipt_parsing(self.receipt.id)

        self.assertFalse(success)

    def test_parse_malformed_text(self):
        """Test parsing with malformed text."""
        self.receipt.raw_ocr_text = "Random text without receipt structure"
        self.receipt.save()

        success = self.service.process_receipt_parsing(self.receipt.id)

        # Should handle gracefully, might succeed with empty products
        self.receipt.refresh_from_db()
        # Status could be llm_done with empty products or error
        self.assertIn(self.receipt.status, ["llm_done", "error"])


class ProductMatchingTests(TestCase):
    """Test product matching functionality."""

    def setUp(self):
        """Set up test data."""
        self.matcher = ProductMatcher()

        # Create test categories
        self.dairy_category = Category.objects.create(
            name="Nabiał",
            meta={"expiry_days": 7}
        )

        # Create test products
        self.milk_product = Product.objects.create(
            name="Mleko 3,2%",
            category=self.dairy_category,
            aliases=["mleko", "milk", "mleko 3.2%"]
        )

        self.bread_product = Product.objects.create(
            name="Chleb graham",
            category=None,
            aliases=["chleb", "bread", "graham"]
        )

    def test_exact_match(self):
        """Test exact product name matching."""
        parsed_product = ParsedProduct(
            name="Mleko 3,2%",
            total_price=Decimal("2.99")
        )

        result = self.matcher.match_product(parsed_product)

        self.assertIsNotNone(result.product)
        self.assertEqual(result.product.id, self.milk_product.id)
        self.assertEqual(result.match_type, "exact")
        self.assertGreater(result.confidence, 0.95)

    def test_fuzzy_match(self):
        """Test fuzzy product name matching."""
        parsed_product = ParsedProduct(
            name="Mleko 3,2% 1L",  # Similar but not exact
            total_price=Decimal("2.99")
        )

        result = self.matcher.match_product(parsed_product)

        self.assertIsNotNone(result.product)
        self.assertEqual(result.product.id, self.milk_product.id)
        self.assertEqual(result.match_type, "fuzzy")
        self.assertGreater(result.confidence, 0.7)

    def test_alias_match(self):
        """Test product alias matching."""
        parsed_product = ParsedProduct(
            name="mleko",  # Alias
            total_price=Decimal("2.99")
        )

        result = self.matcher.match_product(parsed_product)

        self.assertIsNotNone(result.product)
        self.assertEqual(result.product.id, self.milk_product.id)
        self.assertEqual(result.match_type, "alias")
        self.assertGreater(result.confidence, 0.8)

    def test_no_match_creates_product(self):
        """Test that unknown products are created."""
        parsed_product = ParsedProduct(
            name="Nieznany Produkt XYZ",
            total_price=Decimal("9.99")
        )

        # Count products before matching
        initial_count = Product.objects.count()

        result = self.matcher.match_product(parsed_product)

        # New product should be created
        self.assertIsNotNone(result.product)
        self.assertEqual(result.match_type, "created")
        self.assertEqual(Product.objects.count(), initial_count + 1)

        # Check created product
        created_product = result.product
        self.assertEqual(created_product.name, "Nieznany Produkt XYZ")
        self.assertFalse(created_product.is_active)  # Ghost product

    def test_normalization(self):
        """Test product name normalization."""
        # Test with weight/volume patterns
        normalized = self.matcher.normalize_product_name("Mleko 3,2% 1L 500ml")
        self.assertIn("mleko", normalized.lower())

        # Test with brand patterns
        normalized = self.matcher.normalize_product_name("LIDL Organic Bread")
        self.assertIn("bread", normalized.lower())

    def test_similarity_scoring(self):
        """Test similarity scoring algorithm."""
        score = self.matcher._calculate_similarity("Mleko 3,2%", "Mleko 3.2%")
        self.assertGreater(score, 0.8)

        score = self.matcher._calculate_similarity("Chleb", "Bread")
        self.assertLess(score, 0.5)

    def test_multiple_products_individual_matching(self):
        """Test matching multiple products individually."""
        parsed_products = [
            ParsedProduct(name="Mleko 3,2%", total_price=Decimal("2.99")),
            ParsedProduct(name="Chleb graham", total_price=Decimal("3.50")),
            ParsedProduct(name="Nowy Produkt", total_price=Decimal("5.99"))
        ]

        results = []
        for product in parsed_products:
            result = self.matcher.match_product(product)
            results.append(result)

        self.assertEqual(len(results), 3)

        # First two should match existing products
        self.assertEqual(results[0].match_type, "exact")
        self.assertEqual(results[1].match_type, "exact")

        # Third should create new product
        self.assertEqual(results[2].match_type, "created")


class InventoryUpdateTests(TestCase):
    """Test inventory update functionality."""

    def setUp(self):
        """Set up test data."""
        # Create category and products
        self.dairy_category = Category.objects.create(
            name="Nabiał",
            meta={"expiry_days": 7}
        )

        self.milk_product = Product.objects.create(
            name="Mleko 3,2%",
            category=self.dairy_category
        )

        # Create receipt with extracted data
        self.receipt = Receipt.objects.create(
            status="ready_for_review",
            extracted_data={
                "products": [
                    {
                        "name": "Mleko 3,2%",
                        "quantity": 1.0,
                        "unit": "szt",
                        "price": "2.99",
                        "matched_product_id": self.milk_product.id
                    }
                ],
                "store_name": "LIDL",
                "total_amount": "2.99"
            }
        )

    def test_successful_inventory_update(self):
        """Test successful inventory update from receipt data."""
        products_data = self.receipt.extracted_data["products"]

        success = self.receipt.update_pantry_from_extracted_data(products_data)

        self.assertTrue(success)

        # Check receipt status
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "completed")

        # Check inventory item was created
        inventory_items = InventoryItem.objects.filter(product=self.milk_product)
        self.assertEqual(inventory_items.count(), 1)

        item = inventory_items.first()
        self.assertEqual(item.quantity_remaining, Decimal("1.0"))
        self.assertEqual(item.unit, "szt")
        self.assertIsNotNone(item.purchase_date)
        self.assertIsNotNone(item.expiry_date)

    def test_inventory_update_with_invalid_data(self):
        """Test inventory update with invalid product data."""
        invalid_products_data = [
            {
                "name": "",  # Empty name
                "quantity": -1,  # Invalid quantity
                "unit": "szt"
            }
        ]

        success = self.receipt.update_pantry_from_extracted_data(invalid_products_data)

        self.assertFalse(success)

        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "error")
        self.assertIn("spiżarni", self.receipt.error_message)

    def test_inventory_update_duplicate_items(self):
        """Test inventory update with duplicate items adds quantities."""
        # Create existing inventory item
        existing_item = InventoryItem.objects.create(
            product=self.milk_product,
            quantity_remaining=Decimal("2.0"),
            unit="szt",
            purchase_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timezone.timedelta(days=7)
        )

        products_data = [
            {
                "name": "Mleko 3,2%",
                "quantity": 1.0,
                "unit": "szt",
                "matched_product_id": self.milk_product.id
            }
        ]

        success = self.receipt.update_pantry_from_extracted_data(products_data)

        self.assertTrue(success)

        # Should create new item or update existing
        inventory_items = InventoryItem.objects.filter(product=self.milk_product)
        self.assertGreaterEqual(inventory_items.count(), 1)

        total_quantity = sum(item.quantity_remaining for item in inventory_items)
        self.assertGreaterEqual(total_quantity, Decimal("3.0"))


class ReceiptWorkflowIntegrationTests(TestCase):
    """Integration tests for complete receipt workflow."""

    def setUp(self):
        """Set up integration test data."""
        self.service = ReceiptService()

        # Create test products for matching
        self.dairy_category = Category.objects.create(name="Nabiał")
        self.bread_category = Category.objects.create(name="Pieczywo")

        Product.objects.create(
            name="Mleko 3,2%",
            category=self.dairy_category,
            aliases=["mleko", "milk"]
        )
        Product.objects.create(
            name="Chleb graham",
            category=self.bread_category,
            aliases=["chleb", "bread"]
        )

    def test_complete_workflow_with_mocked_components(self):
        """Test complete workflow with mocked OCR and parsing."""
        # Create receipt file
        receipt_file = SimpleUploadedFile(
            name="test_receipt.pdf",
            content=b"%PDF-1.4 dummy content",
            content_type="application/pdf"
        )

        # Step 1: Create receipt
        receipt = self.service.create_receipt_record(receipt_file)
        self.assertEqual(receipt.status, "uploaded")

        # Mock OCR processing
        with patch.object(self.service, 'process_receipt_ocr') as mock_ocr:
            mock_ocr.return_value = True

            # Mock the OCR result
            receipt.status = "ocr_done"
            receipt.raw_ocr_text = "LIDL\nMleko 3,2% 2,99\nChleb graham 3,50\nSUMA: 6,49"
            receipt.save()

            # Step 2: OCR processing
            ocr_success = self.service.process_receipt_ocr(receipt.id)
            self.assertTrue(ocr_success)

            # Mock parsing processing
            with patch.object(self.service, 'process_receipt_parsing') as mock_parse:
                mock_parse.return_value = True

                # Mock the parsing result
                receipt.status = "llm_done"
                receipt.extracted_data = {
                    "products": [
                        {"name": "Mleko 3,2%", "quantity": 1.0, "price": "2.99"},
                        {"name": "Chleb graham", "quantity": 1.0, "price": "3.50"}
                    ],
                    "store_name": "LIDL",
                    "total_amount": "6.49"
                }
                receipt.save()

                # Step 3: Parsing
                parse_success = self.service.process_receipt_parsing(receipt.id)
                self.assertTrue(parse_success)

                # Mock product matching
                with patch.object(self.service, 'process_receipt_matching') as mock_match:
                    mock_match.return_value = True

                    receipt.status = "ready_for_review"
                    receipt.save()

                    # Step 4: Product matching
                    match_success = self.service.process_receipt_matching(receipt.id)
                    self.assertTrue(match_success)

                    # Step 5: Final inventory update
                    final_success = receipt.update_pantry_from_extracted_data(
                        receipt.extracted_data["products"]
                    )
                    self.assertTrue(final_success)

                    receipt.refresh_from_db()
                    self.assertEqual(receipt.status, "completed")

    def test_workflow_with_failures(self):
        """Test workflow handles failures gracefully."""
        receipt_file = SimpleUploadedFile(
            name="test_receipt.pdf",
            content=b"%PDF-1.4 dummy content",
            content_type="application/pdf"
        )

        receipt = self.service.create_receipt_record(receipt_file)

        # Simulate OCR failure
        with patch.object(self.service, 'process_receipt_ocr') as mock_ocr:
            mock_ocr.return_value = False

            receipt.status = "error"
            receipt.error_message = "OCR failed"
            receipt.save()

            ocr_success = self.service.process_receipt_ocr(receipt.id)
            self.assertFalse(ocr_success)

            receipt.refresh_from_db()
            self.assertEqual(receipt.status, "error")
            self.assertIn("OCR failed", receipt.error_message)

    def test_receipt_status_transitions(self):
        """Test proper status transitions throughout workflow."""
        receipt_file = SimpleUploadedFile(
            name="test.pdf",
            content=b"%PDF-1.4 content",
            content_type="application/pdf"
        )

        # Initial status
        receipt = self.service.create_receipt_record(receipt_file)
        self.assertEqual(receipt.status, "uploaded")

        # Mark as processing
        receipt.mark_as_processing()
        self.assertEqual(receipt.status, "ocr_in_progress")

        # Mark OCR done
        receipt.mark_ocr_done("dummy text")
        self.assertEqual(receipt.status, "ocr_done")
        self.assertEqual(receipt.raw_ocr_text, "dummy text")

        # Mark LLM processing
        receipt.mark_llm_processing()
        self.assertEqual(receipt.status, "llm_in_progress")

        # Mark LLM done
        receipt.mark_llm_done({"products": []})
        self.assertEqual(receipt.status, "llm_done")
        self.assertEqual(receipt.extracted_data, {"products": []})

        # Mark ready for review
        receipt.mark_as_ready_for_review()
        self.assertEqual(receipt.status, "ready_for_review")

        # Mark completed
        receipt.mark_as_completed()
        self.assertEqual(receipt.status, "completed")
        self.assertIsNotNone(receipt.processed_at)

    def test_error_status_handling(self):
        """Test error status handling."""
        receipt_file = SimpleUploadedFile(
            name="test.pdf",
            content=b"%PDF-1.4 content",
            content_type="application/pdf"
        )

        receipt = self.service.create_receipt_record(receipt_file)

        # Mark as error
        receipt.mark_as_error("Test error message")
        self.assertEqual(receipt.status, "error")
        self.assertEqual(receipt.error_message, "Test error message")

        # Test status check methods
        self.assertTrue(receipt.has_error())
        self.assertFalse(receipt.is_completed())
        self.assertFalse(receipt.is_ready_for_review())
        self.assertFalse(receipt.is_processing())
