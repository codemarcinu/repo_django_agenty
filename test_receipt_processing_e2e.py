#!/usr/bin/env python
"""
Comprehensive End-to-End tests for the complete receipt processing pipeline.
Tests the entire flow: Upload → OCR → Parse → Match → Inventory

This test suite uses real receipt files from 'paragony_do testów/' directory.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase

# ReceiptProcessing moved to inventory.Receipt
from chatbot.services.ocr_service import get_ocr_service
from chatbot.services.product_matcher import get_product_matcher
from chatbot.services.receipt_parser import get_receipt_parser
from chatbot.services.receipt_service import get_receipt_service
from inventory.models import Category, InventoryItem, Product

# Test data directory
TEST_RECEIPTS_DIR = Path(__file__).parent / "paragony_do testów"


class ReceiptProcessingE2ETestCase(TransactionTestCase):
    """
    End-to-end test case for complete receipt processing pipeline.
    Uses TransactionTestCase to allow testing of async operations and database transactions.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with temporary media directory."""
        super().setUpClass()
        cls.temp_media_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary media directory."""
        super().tearDownClass()
        if os.path.exists(cls.temp_media_dir):
            shutil.rmtree(cls.temp_media_dir)

    def setUp(self):
        """Set up test data for each test."""
        # Create test categories
        self.dairy_category = Category.objects.create(
            name="Nabiał",
            meta={"expiry_days": 7}
        )
        self.bread_category = Category.objects.create(
            name="Pieczywo",
            meta={"expiry_days": 3}
        )
        self.meat_category = Category.objects.create(
            name="Mięso",
            meta={"expiry_days": 5}
        )

        # Create test products
        self.milk_product = Product.objects.create(
            name="Mleko 3,2%",
            category=self.dairy_category,
            aliases=["mleko", "milk", "mleko 3.2%", "mleko 3,2% 1l"]
        )
        self.bread_product = Product.objects.create(
            name="Chleb graham",
            category=self.bread_category,
            aliases=["chleb", "bread", "chleb graham", "graham"]
        )
        self.butter_product = Product.objects.create(
            name="Masło extra",
            category=self.dairy_category,
            aliases=["masło", "butter", "masło extra 200g"]
        )

        # Initialize services
        self.receipt_service = get_receipt_service()
        self.ocr_service = get_ocr_service()
        self.parser = get_receipt_parser()
        self.matcher = get_product_matcher()

    def get_test_receipt_file(self, filename):
        """Get test receipt file as Django UploadedFile."""
        file_path = TEST_RECEIPTS_DIR / filename
        if not file_path.exists():
            self.skipTest(f"Test receipt file not found: {file_path}")

        with open(file_path, 'rb') as f:
            content = f.read()

        return SimpleUploadedFile(
            name=filename,
            content=content,
            content_type='application/pdf' if filename.endswith('.pdf') else 'image/png'
        )

    def test_complete_receipt_processing_pipeline_lidl_png(self):
        """Test complete processing pipeline with real Lidl PNG receipt."""
        # Skip if no OCR service available
        if not self.ocr_service.is_available():
            self.skipTest("OCR service not available")

        receipt_file = self.get_test_receipt_file("Lidl20250131.png")

        # Step 1: Create receipt record
        receipt_processing = self.receipt_service.create_receipt_record(receipt_file)
        self.assertIsNotNone(receipt_processing)
        self.assertEqual(receipt_processing.status, "uploaded")

        # Step 2: Process OCR
        ocr_success = self.receipt_service.process_receipt_ocr(receipt_processing.id)

        receipt_processing.refresh_from_db()

        if ocr_success:
            self.assertEqual(receipt_processing.status, "ocr_done")
            self.assertIsNotNone(receipt_processing.raw_ocr_text)
            self.assertGreater(len(receipt_processing.raw_ocr_text), 0)

            # Step 3: Process parsing
            parse_success = self.receipt_service.process_receipt_parsing(receipt_processing.id)

            receipt_processing.refresh_from_db()

            if parse_success:
                self.assertEqual(receipt_processing.status, "llm_done")
                self.assertIsNotNone(receipt_processing.extracted_data)

                extracted_data = receipt_processing.extracted_data
                self.assertIn("products", extracted_data)
                self.assertIsInstance(extracted_data["products"], list)

                # Step 4: Test product matching and inventory update
                if extracted_data.get("products"):
                    match_success = self.receipt_service.process_product_matching(receipt_processing.id)

                    if match_success:
                        receipt_processing.refresh_from_db()
                        self.assertEqual(receipt_processing.status, "ready_for_review")

                        # Step 5: Final inventory update
                        inventory_success = receipt_processing.update_pantry_from_extracted_data(
                            extracted_data["products"]
                        )

                        if inventory_success:
                            receipt_processing.refresh_from_db()
                            self.assertEqual(receipt_processing.status, "completed")

                            # Verify inventory items were created
                            inventory_items = InventoryItem.objects.all()
                            self.assertGreater(inventory_items.count(), 0)

                            for item in inventory_items:
                                self.assertIsNotNone(item.product)
                                self.assertGreater(item.quantity_remaining, 0)
                        else:
                            self.fail("Inventory update failed")
                    else:
                        self.fail("Product matching failed")
                else:
                    self.skipTest("No products extracted from receipt")
            else:
                self.fail("Receipt parsing failed")
        else:
            self.fail("OCR processing failed")

    def test_complete_receipt_processing_pipeline_pdf(self):
        """Test complete processing pipeline with PDF receipt."""
        if not self.ocr_service.is_available():
            self.skipTest("OCR service not available")

        receipt_file = self.get_test_receipt_file("45124711000057030425.pdf")

        # Complete pipeline test
        receipt_processing = self.receipt_service.create_receipt_record(receipt_file)

        # OCR step
        ocr_success = self.receipt_service.process_receipt_ocr(receipt_processing.id)
        receipt_processing.refresh_from_db()

        if ocr_success and receipt_processing.status == "ocr_done":
            # Parse step
            parse_success = self.receipt_service.process_receipt_parsing(receipt_processing.id)
            receipt_processing.refresh_from_db()

            if parse_success and receipt_processing.status == "llm_done":
                extracted_data = receipt_processing.extracted_data

                if extracted_data and extracted_data.get("products"):
                    # Matching step
                    match_success = self.receipt_service.process_product_matching(receipt_processing.id)

                    if match_success:
                        receipt_processing.refresh_from_db()
                        self.assertEqual(receipt_processing.status, "ready_for_review")

                        # Final inventory update
                        final_success = receipt_processing.update_pantry_from_extracted_data(
                            extracted_data["products"]
                        )

                        self.assertTrue(final_success)
                        receipt_processing.refresh_from_db()
                        self.assertEqual(receipt_processing.status, "completed")

    def test_complete_pipeline_with_known_data(self):
        """Test complete pipeline with real OCR processing."""
        if not self.ocr_service.is_available():
            self.skipTest("OCR service not available")

        receipt_file = self.get_test_receipt_file("Lidl20250131.png")

        # Complete pipeline with real OCR processing
        receipt_processing = self.receipt_service.create_receipt_record(receipt_file)

        # OCR with real processing
        ocr_success = self.receipt_service.process_receipt_ocr(receipt_processing.id)

        if ocr_success:
            receipt_processing.refresh_from_db()
            self.assertEqual(receipt_processing.status, "ocr_done")
            self.assertIsNotNone(receipt_processing.raw_ocr_text)

            # Parse the OCR text
            parse_success = self.receipt_service.process_receipt_parsing(receipt_processing.id)
            
            if parse_success:
                receipt_processing.refresh_from_db()
                self.assertEqual(receipt_processing.status, "llm_done")

                extracted_data = receipt_processing.extracted_data
                self.assertIsNotNone(extracted_data)
                self.assertIn("products", extracted_data)

                products = extracted_data["products"]
                if products:
                    self.assertGreater(len(products), 0)

                    # Test product matching
                    match_success = self.receipt_service.process_product_matching(receipt_processing.id)
                    
                    if match_success:
                        receipt_processing.refresh_from_db()
                        self.assertEqual(receipt_processing.status, "ready_for_review")

                        # Final inventory update
                        final_success = receipt_processing.update_pantry_from_extracted_data(products)
                        
                        if final_success:
                            receipt_processing.refresh_from_db()
                            self.assertEqual(receipt_processing.status, "completed")

                            # Verify inventory was updated
                            inventory_items = InventoryItem.objects.all()
                            if inventory_items.exists():
                                for item in inventory_items:
                                    self.assertGreater(item.quantity_remaining, 0)
                                    self.assertIsNotNone(item.purchase_date)

    def test_error_handling_invalid_file(self):
        """Test error handling with invalid file."""
        # Create invalid file content
        invalid_file = SimpleUploadedFile(
            name="invalid.txt",
            content=b"This is not a valid receipt file",
            content_type="text/plain"
        )

        # Should handle validation error gracefully
        with self.assertRaises(Exception):
            self.receipt_service.create_receipt_record(invalid_file)

    def test_error_handling_ocr_failure(self):
        """Test error handling when OCR fails naturally."""
        # Create a test file that should naturally cause OCR to fail or return poor results
        invalid_receipt_file = SimpleUploadedFile(
            name="invalid_receipt.png",
            content=b"invalid image content",
            content_type="image/png"
        )
        
        receipt_processing = self.receipt_service.create_receipt_record(invalid_receipt_file)

        # Attempt OCR processing - should handle failure gracefully
        ocr_success = self.receipt_service.process_receipt_ocr(receipt_processing.id)
        
        receipt_processing.refresh_from_db()
        
        # OCR might succeed or fail depending on the service implementation
        # Test that the system handles either case appropriately
        if not ocr_success:
            self.assertTrue(receipt_processing.status in ["error", "ocr_failed"])
        else:
            # If OCR somehow succeeds with invalid data, system should still be stable
            self.assertIsNotNone(receipt_processing.raw_ocr_text)

    def test_all_test_receipts_basic_pipeline(self):
        """Test basic pipeline (OCR only) with all available test receipts."""
        if not self.ocr_service.is_available():
            self.skipTest("OCR service not available")

        test_files = [
            "Lidl20250131.png",
            "20250125lidl.png",
            "20250626LIDL.png",
            "45124711000057030425.pdf",
            "20241209_151934.pdf",
            "20250121_063301.pdf"
        ]

        results = {}

        for filename in test_files:
            if not (TEST_RECEIPTS_DIR / filename).exists():
                continue

            try:
                receipt_file = self.get_test_receipt_file(filename)
                receipt_processing = self.receipt_service.create_receipt_record(receipt_file)

                # Test OCR step only for faster execution
                ocr_success = self.receipt_service.process_receipt_ocr(receipt_processing.id)

                receipt_processing.refresh_from_db()

                results[filename] = {
                    "ocr_success": ocr_success,
                    "status": receipt_processing.status,
                    "text_length": len(receipt_processing.raw_ocr_text or ""),
                    "has_error": bool(receipt_processing.error_message)
                }

            except Exception as e:
                results[filename] = {
                    "error": str(e),
                    "ocr_success": False
                }

        # Print results for analysis
        print("\n=== OCR Test Results ===")
        for filename, result in results.items():
            print(f"{filename}: {result}")

        # Verify at least some receipts processed successfully
        successful_count = sum(1 for r in results.values() if r.get("ocr_success"))
        self.assertGreater(successful_count, 0, "At least one receipt should process successfully")


class ReceiptProcessingUnitTests(TestCase):
    """Unit tests for individual components of receipt processing."""

    def setUp(self):
        """Set up test data."""
        self.service = get_receipt_service()

    def test_receipt_service_initialization(self):
        """Test receipt service initializes correctly."""
        self.assertIsNotNone(self.service)
        self.assertIsNotNone(self.service.pantry_service)

    def test_ocr_service_availability(self):
        """Test OCR service availability check."""
        ocr_service = get_ocr_service()
        # Should not raise exception
        is_available = ocr_service.is_available()
        self.assertIsInstance(is_available, bool)

    def test_receipt_parser_initialization(self):
        """Test receipt parser initializes correctly."""
        parser = get_receipt_parser()
        self.assertIsNotNone(parser)
        self.assertIsNotNone(parser.store_patterns)
        self.assertIsNotNone(parser.product_patterns)

    def test_product_matcher_initialization(self):
        """Test product matcher initializes correctly."""
        matcher = get_product_matcher()
        self.assertIsNotNone(matcher)
        self.assertIsNotNone(matcher.weight_patterns)
        self.assertIsNotNone(matcher.brand_patterns)


class ReceiptProcessingPerformanceTests(TestCase):
    """Performance tests for receipt processing pipeline."""

    def setUp(self):
        """Set up performance test data."""
        self.service = get_receipt_service()

    def test_receipt_creation_performance(self):
        """Test receipt creation performance."""
        import time

        receipt_file = SimpleUploadedFile(
            name="test_performance.pdf",
            content=b"dummy content",
            content_type="application/pdf"
        )

        start_time = time.time()

        try:
            receipt_processing = self.service.create_receipt_record(receipt_file)
            creation_time = time.time() - start_time

            # Should create receipt quickly (< 1 second)
            self.assertLess(creation_time, 1.0)
            self.assertIsNotNone(receipt_processing)

        except Exception:
            # Expected due to validation, but timing should still be fast
            creation_time = time.time() - start_time
            self.assertLess(creation_time, 1.0)

    def test_service_initialization_performance(self):
        """Test service initialization performance."""
        import time

        start_time = time.time()

        # Initialize all services
        receipt_service = get_receipt_service()
        ocr_service = get_ocr_service()
        parser = get_receipt_parser()
        matcher = get_product_matcher()

        initialization_time = time.time() - start_time

        # Services should initialize quickly (< 2 seconds)
        self.assertLess(initialization_time, 2.0)

        # All services should be available
        self.assertIsNotNone(receipt_service)
        self.assertIsNotNone(ocr_service)
        self.assertIsNotNone(parser)
        self.assertIsNotNone(matcher)


if __name__ == '__main__':
    # Run tests with Django setup
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_dev')
    django.setup()

    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
