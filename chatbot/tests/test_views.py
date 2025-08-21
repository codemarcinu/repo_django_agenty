import pytest
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone # Added for purchase_date

from chatbot.models import Agent # Explicitly imported
from inventory.models import InventoryItem, Product, Receipt # Explicitly imported

@pytest.mark.unit
class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Agent is imported at module level, no need to re-import here
        # Create test data
        Agent.objects.create(
            name="Test Agent",
            agent_type="general",
            persona_prompt="Test",
            is_active=True,
        )

    def test_dashboard_view_loads(self):
        """Test dashboard view loads successfully"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_dashboard_shows_statistics(self):
        """Test dashboard shows correct statistics"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aktywni Agenci")
        self.assertContains(response, "0")


@pytest.mark.unit
class ChatViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Agent is imported at module level, no need to re-import here
        self.agent = Agent.objects.create(
            name="Test Agent",
            agent_type="general",
            persona_prompt="You are a helpful test agent",
            is_active=True,
        )

    def test_chat_view_loads(self):
        """Test chat view loads successfully"""
        response = self.client.get(reverse("chatbot:chat"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chat z Asystentem AI")

    def test_chat_view_shows_agents(self):
        """Test chat view displays available agents"""
        response = self.client.get(reverse("chatbot:chat"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.agent.name)


@pytest.mark.integration
class APIViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Agent is imported at module level, no need to re-import here
        self.agent = Agent.objects.create(
            name="Test Agent",
            agent_type="general",
            persona_prompt="You are a helpful test agent",
            is_active=True,
        )

    def test_agent_list_api(self):
        """Test agent list API endpoint"""
        response = self.client.get("/api/agents/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("agents", data) # Changed from "results" to "agents"
        self.assertTrue(len(data["agents"]) > 0) # Changed from "results" to "agents"
        self.assertEqual(data["agents"][0]["name"], self.agent.name) # Changed from "results" to "agents"

    def test_agent_list_api_only_active_agents(self):
        """Test agent list API only returns active agents"""
        # Create inactive agent
        Agent.objects.create(
            name="Inactive Agent",
            agent_type="general",
            persona_prompt="Test",
            is_active=False,
        )

        response = self.client.get("/api/agents/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        agent_names = [agent["name"] for agent in data["agents"]] # Changed from "results" to "agents"
        self.assertIn(self.agent.name, agent_names)
        self.assertNotIn("Inactive Agent", agent_names)


@pytest.mark.unit
class DocumentViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_document_list_view(self):
        """Test document list view loads"""
        response = self.client.get(reverse("chatbot:document_list"))
        self.assertEqual(response.status_code, 200)

    def test_document_upload_view_get(self):
        """Test document upload view GET request"""
        response = self.client.get(reverse("chatbot:document_upload"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")


@pytest.mark.unit
class PantryViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # InventoryItem and Product are imported at module level, no need to re-import here
        self.pantry_item = InventoryItem.objects.create(
            product=Product.objects.create(name="Test Item"),
            quantity_remaining=1.0,
            unit="szt",
            purchase_date=timezone.now().date() # Added purchase_date
        )

    def test_pantry_list_view(self):
        """Test pantry list view loads"""
        response = self.client.get(reverse("inventory:inventory_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.pantry_item.product.name)


@pytest.mark.integration
class ReceiptViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_receipt_upload_view_get(self):
        """Test receipt upload view GET request"""
        response = self.client.get(reverse("chatbot:receipt_upload"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")

    def test_receipt_processing_status_view(self):
        """Test receipt processing status view"""
        receipt = Receipt.objects.create(status="uploaded")

        response = self.client.get(
            reverse(
                "chatbot:receipt_status", kwargs={"receipt_id": receipt.id}
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, receipt.status)