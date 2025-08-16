import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase


@pytest.mark.unit
class AgentModelTest(TestCase):
    def test_agent_creation(self):
        """Test Agent model creation and string representation"""
        agent = Agent.objects.create(
            name="Test Agent",
            agent_type="general",
            persona_prompt="You are a helpful test agent",
            capabilities=["chat", "help"],
            is_active=True,
        )

        self.assertEqual(str(agent), "Test Agent")
        self.assertEqual(agent.agent_type, "general")
        self.assertTrue(agent.is_active)
        self.assertIn("chat", agent.capabilities)

    def test_agent_deactivation(self):
        """Test agent can be deactivated"""
        agent = Agent.objects.create(
            name="Test Agent",
            agent_type="general",
            persona_prompt="Test prompt",
            is_active=True,
        )

        agent.is_active = False
        agent.save()

        self.assertFalse(agent.is_active)


@pytest.mark.unit
class DocumentModelTest(TestCase):
    def test_document_creation(self):
        """Test Document model creation"""
        file_content = b"Test document content"
        uploaded_file = SimpleUploadedFile(
            "test.txt", file_content, content_type="text/plain"
        )

        document = Document.objects.create(title="Test Document", file=uploaded_file)

        self.assertEqual(str(document), "Test Document")
        self.assertTrue(document.file.name.endswith("test.txt"))
        self.assertIsNotNone(document.uploaded_at)





@pytest.mark.unit
class ReceiptProcessingModelTest(TestCase):
    def test_receipt_processing_creation(self):
        """Test ReceiptProcessing model creation"""
        file_content = b"Test receipt content"
        uploaded_file = SimpleUploadedFile(
            "receipt.pdf", file_content, content_type="application/pdf"
        )

        receipt = ReceiptProcessing.objects.create(
            receipt_file=uploaded_file, status="uploaded"
        )

        self.assertEqual(receipt.status, "uploaded")
        self.assertTrue(receipt.receipt_file.name.endswith("receipt.pdf"))
        self.assertIsNotNone(receipt.uploaded_at)

    def test_receipt_status_transitions(self):
        """Test receipt status can be changed"""
        receipt = ReceiptProcessing.objects.create(status="uploaded")

        receipt.status = "processing"
        receipt.save()
        self.assertEqual(receipt.status, "processing")

        receipt.status = "completed"
        receipt.save()
        self.assertEqual(receipt.status, "completed")
