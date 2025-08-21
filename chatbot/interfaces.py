"""
Agent interfaces and base classes for Django Agent system.
Inspired by FoodSave AI architecture.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class AgentResponse:
    """Standardized response from agents"""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    severity: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class IntentData:
    """Intent detection data"""

    intent: str
    confidence: float
    entities: dict[str, Any]
    raw_query: str


class BaseAgentInterface(ABC):
    """Base interface for all agents"""

    @abstractmethod
    async def process(self, input_data: dict[str, Any]) -> AgentResponse:
        """Process input data and return response"""
        pass

    @abstractmethod
    def get_metadata(self) -> dict[str, Any]:
        """Return agent metadata including capabilities"""
        pass

    def get_dependencies(self) -> list[str]:
        """List of agent types this agent depends on"""
        return []

    def is_healthy(self) -> bool:
        """Check if agent is functioning properly"""
        return True


class ConversationManagerInterface(ABC):
    """Interface for conversation management"""

    @abstractmethod
    async def create_conversation(
        self, agent_name: str, user_id: str | None = None
    ) -> str:
        """Create new conversation and return session_id"""
        pass

    @abstractmethod
    async def add_message(
        self, session_id: str, role: str, content: str, metadata: dict | None = None
    ):
        """Add message to conversation"""
        pass

    @abstractmethod
    async def get_conversation_history(
        self, session_id: str, limit: int = 50
    ) -> list[dict]:
        """Get conversation history"""
        pass

    @abstractmethod
    async def update_conversation_summary(self, session_id: str, summary: str):
        """Update conversation summary"""
        pass


class AgentFactoryInterface(ABC):
    """Interface for agent factory"""

    @abstractmethod
    def create_agent(self, agent_type: str, **kwargs) -> BaseAgentInterface:
        """Create agent instance"""
        pass

    @abstractmethod
    def register_agent(self, agent_type: str, agent_class: type):
        """Register new agent type"""
        pass

    @abstractmethod
    def list_available_agents(self) -> list[str]:
        """List all available agent types"""
        pass


class ReceiptParser(ABC):
    """Base receipt parser interface."""

    @abstractmethod
    def parse(self, raw_text: str) -> Dict:
        """Parse raw text into structured receipt data."""
        pass
