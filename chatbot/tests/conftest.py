import pytest
from django.contrib.auth.models import User
from django.test import Client

from chatbot.models import Agent


@pytest.fixture
def client():
    """Provide a Django test client"""
    return Client()


@pytest.fixture
def user():
    """Create a test user"""
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def test_agent():
    """Create a test agent"""
    return Agent.objects.create(
        name="Test Agent",
        agent_type="general",
        persona_prompt="You are a helpful test agent for unit testing",
        capabilities=["chat", "help"],
        is_active=True,
    )


@pytest.fixture
def inactive_agent():
    """Create an inactive test agent"""
    return Agent.objects.create(
        name="Inactive Agent",
        agent_type="general",
        persona_prompt="You are an inactive test agent",
        is_active=False,
    )


@pytest.fixture
def authenticated_client(client, user):
    """Provide an authenticated Django test client"""
    client.login(username="testuser", password="testpass123")
    return client
