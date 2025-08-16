"""
Tests for receipt upload API endpoints.
"""

from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from inventory.models import Receipt


class ReceiptUploadAPITest(TestCase):
    """Test receipt upload API functionality."""

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.upload_url = "/api/receipts/upload/"

    def create_test_file(self, content: bytes, filename: str, content_type: str):
        """Create test file for upload."""
        return SimpleUploadedFile(
            name=filename, content=content, content_type=content_type
        )

    def test_successful_pdf_upload(self):
        """Test successful PDF file upload."""
        # Create a minimal PDF content (PDF magic number)
        pdf_content = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\ntrailer\n%%EOF"
        )

        test_file = self.create_test_file(
            content=pdf_content,
            filename="test_receipt.pdf",
            content_type="application/pdf",
        )

        response = self.client.post(self.upload_url, {"file": test_file})

        # Debug response if it's not 201
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("receipt_id", response.data)
        self.assertIn("status", response.data)
        self.assertEqual(response.data["status"], "pending_ocr")

        # Verify Receipt object was created
        receipt_id = response.data["receipt_id"]
        receipt = Receipt.objects.get(id=receipt_id)
        self.assertEqual(receipt.status, "pending_ocr")
        self.assertIsNotNone(receipt.source_file_path)

    def test_successful_jpg_upload(self):
        """Test successful JPG file upload."""
        # Create minimal JPEG content (JPEG magic number)
        jpeg_content = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb"
        )

        test_file = self.create_test_file(
            content=jpeg_content, filename="test_receipt.jpg", content_type="image/jpeg"
        )

        response = self.client.post(self.upload_url, {"file": test_file})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending_ocr")

    def test_successful_png_upload(self):
        """Test successful PNG file upload."""
        # Create minimal PNG content (PNG magic number)
        png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"

        test_file = self.create_test_file(
            content=png_content, filename="test_receipt.png", content_type="image/png"
        )

        response = self.client.post(self.upload_url, {"file": test_file})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending_ocr")

    def test_missing_file(self):
        """Test upload without file."""
        response = self.client.post(self.upload_url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_invalid_file_extension(self):
        """Test upload with invalid file extension."""
        test_file = self.create_test_file(
            content=b"test content", filename="test.txt", content_type="text/plain"
        )

        response = self.client.post(self.upload_url, {"file": test_file})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)
        self.assertIn("file", response.data["errors"])

    def test_file_too_large(self):
        """Test upload with file exceeding size limit."""
        # Create content larger than 50MB (mock)
        large_content = b"x" * (51 * 1024 * 1024)  # 51MB

        test_file = self.create_test_file(
            content=large_content,
            filename="large_receipt.pdf",
            content_type="application/pdf",
        )

        response = self.client.post(self.upload_url, {"file": test_file})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_content_type_mismatch(self):
        """Test upload with mismatched content type and extension."""
        # Text content with PDF extension
        test_file = self.create_test_file(
            content=b"This is not a PDF file",
            filename="fake.pdf",
            content_type="application/pdf",
        )

        response = self.client.post(self.upload_url, {"file": test_file})

        # Should fail due to magic number validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_file(self):
        """Test upload with empty file."""
        test_file = self.create_test_file(
            content=b"", filename="empty.pdf", content_type="application/pdf"
        )

        response = self.client.post(self.upload_url, {"file": test_file})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ReceiptStatusAPITest(TestCase):
    """Test receipt status API functionality."""

    def setUp(self):
        """Set up test data."""
        from django.utils import timezone

        self.client = APIClient()
        self.receipt = Receipt.objects.create(
            store_name="Test Store",
            purchased_at=timezone.now(),
            total=Decimal("25.99"),
            currency="PLN",
            status="pending_ocr",
            source_file_path="/test/receipt.pdf",
        )

    def test_get_receipt_status(self):
        """Test retrieving receipt status."""
        url = f"/api/receipts/{self.receipt.id}/status/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["receipt_id"], self.receipt.id)
        self.assertEqual(response.data["status"], "pending_ocr")
        self.assertEqual(response.data["store_name"], "Test Store")
        self.assertEqual(response.data["total"], "25.99")
        self.assertEqual(response.data["currency"], "PLN")

    def test_get_nonexistent_receipt_status(self):
        """Test retrieving status for non-existent receipt."""
        url = "/api/receipts/999999/status/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_receipt_with_line_items(self):
        """Test status response includes line items count."""
        from inventory.models import ReceiptLineItem

        # Add line items
        ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Item 1",
            quantity=Decimal("1.000"),
            unit_price=Decimal("10.00"),
            line_total=Decimal("10.00"),
        )
        ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Item 2",
            quantity=Decimal("2.000"),
            unit_price=Decimal("7.99"),
            line_total=Decimal("15.98"),
        )

        url = f"/api/receipts/{self.receipt.id}/status/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["line_items_count"], 2)


class ReceiptAPIIntegrationTest(TestCase):
    """Integration tests for receipt API workflow."""

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()

    def test_upload_and_check_status_workflow(self):
        """Test complete upload -> check status workflow."""
        # Step 1: Upload file
        pdf_content = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\ntrailer\n%%EOF"
        )
        test_file = SimpleUploadedFile(
            name="integration_test.pdf",
            content=pdf_content,
            content_type="application/pdf",
        )

        upload_response = self.client.post("/api/receipts/upload/", {"file": test_file})

        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)
        receipt_id = upload_response.data["receipt_id"]

        # Step 2: Check status
        status_response = self.client.get(f"/api/receipts/{receipt_id}/status/")

        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertEqual(status_response.data["receipt_id"], receipt_id)
        self.assertEqual(status_response.data["status"], "pending_ocr")

        # Verify database state
        receipt = Receipt.objects.get(id=receipt_id)
        self.assertEqual(receipt.status, "pending_ocr")
        self.assertIsNotNone(receipt.source_file_path)
        self.assertIn("integration_test", receipt.processing_notes)
