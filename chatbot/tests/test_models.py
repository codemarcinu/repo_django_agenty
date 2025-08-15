import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from chatbot.models import Agent, Document, PantryItem, ReceiptProcessing


@pytest.mark.unit
class AgentModelTest(TestCase):
    def test_agent_creation(self):
        """Test Agent model creation and string representation"""
        agent = Agent.objects.create(
            name="Test Agent",
            agent_type="general",
            persona_prompt="You are a helpful test agent",
            capabilities=["chat", "help"],
            is_active=True
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
            is_active=True
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
            "test.txt", 
            file_content, 
            content_type="text/plain"
        )
        
        document = Document.objects.create(
            title="Test Document",
            file=uploaded_file
        )
        
        self.assertEqual(str(document), "Test Document")
        self.assertTrue(document.file.name.endswith('test.txt'))
        self.assertIsNotNone(document.uploaded_at)


@pytest.mark.unit
class PantryItemModelTest(TestCase):
    def test_pantry_item_creation(self):
        """Test PantryItem model creation"""
        pantry_item = PantryItem.objects.create(
            name="Test Item",
            quantity=2.5,
            unit="kg"
        )
        
        self.assertEqual(str(pantry_item), "Test Item")
        self.assertEqual(pantry_item.quantity, 2.5)
        self.assertEqual(pantry_item.unit, "kg")
        self.assertIsNotNone(pantry_item.added_at)

    def test_pantry_item_with_expiry(self):
        """Test PantryItem with expiry date"""
        from django.utils import timezone
        from datetime import timedelta
        
        future_date = timezone.now() + timedelta(days=7)
        
        pantry_item = PantryItem.objects.create(
            name="Milk",
            quantity=1.0,
            unit="liter",
            expiry_date=future_date
        )
        
        self.assertEqual(pantry_item.expiry_date, future_date)


@pytest.mark.unit
class ReceiptProcessingModelTest(TestCase):
    def test_receipt_processing_creation(self):
        """Test ReceiptProcessing model creation"""
        file_content = b"Test receipt content"
        uploaded_file = SimpleUploadedFile(
            "receipt.pdf", 
            file_content, 
            content_type="application/pdf"
        )
        
        receipt = ReceiptProcessing.objects.create(
            receipt_file=uploaded_file,
            status='uploaded'
        )
        
        self.assertEqual(receipt.status, 'uploaded')
        self.assertTrue(receipt.receipt_file.name.endswith('receipt.pdf'))
        self.assertIsNotNone(receipt.uploaded_at)

    def test_receipt_status_transitions(self):
        """Test receipt status can be changed"""
        receipt = ReceiptProcessing.objects.create(
            status='uploaded'
        )
        
        receipt.status = 'processing'
        receipt.save()
        self.assertEqual(receipt.status, 'processing')
        
        receipt.status = 'completed'
        receipt.save()
        self.assertEqual(receipt.status, 'completed')