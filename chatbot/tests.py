import os
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import ReceiptProcessing
from .tasks import process_receipt_task


class ReceiptProcessingTasksTest(TestCase):

    def setUp(self):
        # Create a dummy receipt file
        self.dummy_file_content = b"dummy image content"
        self.dummy_file = SimpleUploadedFile(
            "test_receipt.jpg", self.dummy_file_content, content_type="image/jpeg"
        )
        self.receipt_record = ReceiptProcessing.objects.create(
            receipt_file=self.dummy_file, status="uploaded"
        )

    @patch("chatbot.tasks.receipt_processor")
    @patch(
        "chatbot.tasks.easyocr"
    )  # Mock easyocr if it's used directly in receipt_processor
    def test_process_receipt_task_success(self, mock_easyocr, mock_receipt_processor):
        # Configure mocks
        mock_receipt_processor.process_receipt.return_value = (
            None  # Assuming it doesn't return anything specific
        )
        mock_easyocr.Reader.return_value.readtext.return_value = [
            ("text", (0, 0, 0, 0), 0.9)
        ]  # Example OCR output

        # Call the Celery task directly (without Celery worker setup)
        # In a real test setup with Celery, you'd use task.delay() and inspect results
        process_receipt_task(self.receipt_record.id)

        # Refresh the model instance from the database
        self.receipt_record.refresh_from_db()

        # Assertions
        mock_receipt_processor.process_receipt.assert_called_once_with(
            self.receipt_record.id
        )
        self.assertEqual(
            self.receipt_record.status, "completed"
        )  # Assuming task sets status to completed on success

    @patch("chatbot.tasks.receipt_processor")
    def test_process_receipt_task_failure(self, mock_receipt_processor):
        # Configure mock to raise an exception
        mock_receipt_processor.process_receipt.side_effect = Exception("Test error")

        # Call the Celery task
        process_receipt_task(self.receipt_record.id)

        # Refresh the model instance from the database
        self.receipt_record.refresh_from_db()

        # Assertions
        mock_receipt_processor.process_receipt.assert_called_once_with(
            self.receipt_record.id
        )
        self.assertEqual(self.receipt_record.status, "error")
        self.assertIn("Test error", self.receipt_record.error_message)

    def tearDown(self):
        # Clean up dummy file
        if self.receipt_record.receipt_file:
            if os.path.exists(self.receipt_record.receipt_file.path):
                os.remove(self.receipt_record.receipt_file.path)
        self.receipt_record.delete()
