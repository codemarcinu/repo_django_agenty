
import pytest
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from chatbot.models import Agent
from inventory.models import Receipt # Added new import


@pytest.mark.integration
class APIEndpointsTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.agent = Agent.objects.create(
            name="Test Agent",
            agent_type="general",
            persona_prompt="You are a helpful test agent",
            is_active=True,
        )

    def test_agent_list_endpoint(self):
        """Test the DRF agent list endpoint"""
        url = "/api/agents/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], self.agent.name)

    def test_conversation_create_endpoint(self):
        """Test conversation creation endpoint"""
        url = "/api/conversations/create/"
        data = {
            "agent_name": self.agent.name,
            "user_id": "test_user",
            "title": "Test Conversation",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertIn("session_id", response.data)

    def test_conversation_create_missing_agent(self):
        """Test conversation creation with missing agent name"""
        url = "/api/conversations/create/"
        data = {"user_id": "test_user", "title": "Test Conversation"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("errors", response.data)

    def test_conversation_create_invalid_agent(self):
        """Test conversation creation with invalid agent name"""
        url = "/api/conversations/create/"
        data = {"agent_name": "NonexistentAgent", "user_id": "test_user"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_receipt_status_endpoint(self):
        """Test receipt processing status endpoint"""
        receipt = Receipt.objects.create(status="uploaded")

        url = f"/api/receipts/{receipt.id}/status/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "uploaded")

    def test_receipt_status_not_found(self):
        """Test receipt status endpoint with non-existent receipt"""
        url = "/api/receipts/99999/status/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)


@pytest.mark.integration
class AuthenticatedAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.client = APIClient()

    def test_authenticated_endpoint_without_auth(self):
        """Test authenticated endpoint returns 401 without authentication"""
        url = "/api/documents/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_endpoint_with_auth(self):
        """Test authenticated endpoint works with authentication"""
        self.client.force_authenticate(user=self.user)

        url = "/api/documents/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


@pytest.mark.unit
class SerializerTest(TestCase):
    def test_agent_serializer(self):
        """Test AgentSerializer"""
        from chatbot.serializers import AgentSerializer

        agent = Agent.objects.create(
            name="Test Agent",
            agent_type="general",
            persona_prompt="A very long persona prompt that should be truncated when displayed in the API to avoid sending too much data to the client",
            is_active=True,
        )

        serializer = AgentSerializer(agent)
        data = serializer.data

        self.assertEqual(data["name"], agent.name)
        self.assertEqual(data["agent_type"], agent.agent_type)
        self.assertTrue(data["description"].endswith("..."))  # Should be truncated

    def test_conversation_create_serializer(self):
        """Test ConversationCreateSerializer"""
        from chatbot.serializers import ConversationCreateSerializer

        data = {
            "agent_name": "Test Agent",
            "user_id": "test_user",
            "title": "Test Conversation",
        }

        serializer = ConversationCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        validated_data = serializer.validated_data
        self.assertEqual(validated_data["agent_name"], "Test Agent")
        self.assertEqual(validated_data["user_id"], "test_user")
        self.assertEqual(validated_data["title"], "Test Conversation")

    def test_chat_message_serializer(self):
        """Test ChatMessageSerializer"""
        from chatbot.serializers import ChatMessageSerializer

        data = {"session_id": "test_session_123", "message": "Hello, how are you?"}

        serializer = ChatMessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        validated_data = serializer.validated_data
        self.assertEqual(validated_data["session_id"], "test_session_123")
        self.assertEqual(validated_data["message"], "Hello, how are you?")
