"""
Async service layer for better separation of sync/async operations.
Provides async-first database operations and business logic.
"""

import logging
from typing import Any

from ..models import Agent, Conversation, Message, ReceiptProcessing
from .exceptions import (
    AgentNotFoundError,
)

logger = logging.getLogger(__name__)


class AsyncAgentService:
    """Async service for agent-related operations"""

    @staticmethod
    async def get_agent_by_name(agent_name: str) -> Agent:
        """Get agent by name asynchronously
        
        Raises:
            AgentNotFoundError: If agent is not found
        """
        try:
            return await Agent.objects.aget(name=agent_name, is_active=True)
        except Agent.DoesNotExist:
            error_msg = f"Agent not found: {agent_name}"
            logger.error(error_msg)
            raise AgentNotFoundError(error_msg)

    @staticmethod
    async def list_active_agents() -> list[dict[str, Any]]:
        """List all active agents"""
        agents = []
        async for agent in Agent.objects.filter(is_active=True).order_by("name"):
            agents.append(
                {
                    "name": agent.name,
                    "agent_type": agent.agent_type,
                    "capabilities": agent.capabilities,
                    "created_at": agent.created_at.isoformat(),
                }
            )
        return agents

    @staticmethod
    async def update_agent_config(agent_name: str, config: dict[str, Any]) -> bool:
        """Update agent configuration"""
        try:
            agent = await Agent.objects.aget(name=agent_name, is_active=True)
            agent.config = config
            await agent.asave()
            logger.info(f"Updated config for agent {agent_name}")
            return True
        except Agent.DoesNotExist:
            logger.error(f"Agent not found: {agent_name}")
            return False


class AsyncConversationService:
    """Async service for conversation-related operations"""

    @staticmethod
    async def create_conversation_with_agent(
        agent_name: str, user_id: str | None = None, title: str | None = None
    ) -> str:
        """Create conversation with proper agent validation"""
        agent = await AsyncAgentService.get_agent_by_name(agent_name)

        conversation = await Conversation.objects.acreate(
            agent=agent,
            user_id=user_id or "",
            title=title or f"Konwersacja z {agent_name}",
            metadata={"created_by": "system", "agent_name": agent_name},
        )

        logger.info(
            f"Created conversation {conversation.session_id} with agent {agent_name}"
        )
        return str(conversation.session_id)

    @staticmethod
    async def add_message_to_conversation(
        session_id: str, role: str, content: str, metadata: dict | None = None
    ) -> Message:
        """Add message to conversation with proper validation"""
        try:
            conversation = await Conversation.objects.aget(session_id=session_id)

            message = await Message.objects.acreate(
                conversation=conversation,
                role=role,
                content=content,
                metadata=metadata or {},
            )

            # Update conversation timestamp
            from django.utils import timezone

            conversation.updated_at = timezone.now()
            await conversation.asave()

            logger.info(f"Added {role} message to conversation {session_id}")
            return message

        except Conversation.DoesNotExist:
            logger.error(f"Conversation not found: {session_id}")
            raise ValueError(f"Conversation not found: {session_id}")

    @staticmethod
    async def get_conversation_messages(
        session_id: str, limit: int = 50, format_for_ai: bool = False
    ) -> list[dict]:
        """Get conversation messages with optional AI formatting"""
        try:
            conversation = await Conversation.objects.aget(session_id=session_id)

            messages = []
            async for message in Message.objects.filter(
                conversation=conversation
            ).order_by("-created_at")[:limit]:

                if format_for_ai:
                    messages.append({"role": message.role, "content": message.content})
                else:
                    messages.append(
                        {
                            "id": message.id,
                            "role": message.role,
                            "content": message.content,
                            "created_at": message.created_at.isoformat(),
                            "metadata": message.metadata,
                        }
                    )

            # Reverse to get chronological order
            messages.reverse()
            return messages

        except Conversation.DoesNotExist:
            logger.error(f"Conversation not found: {session_id}")
            return []



    """Async service for receipt processing operations"""

    @staticmethod
    async def get_receipt_status(receipt_id: int) -> dict[str, Any] | None:
        """Get receipt processing status"""
        try:
            receipt = await ReceiptProcessing.objects.aget(id=receipt_id)
            return {
                "id": receipt.id,
                "status": receipt.status,
                "error_message": receipt.error_message,
                "created_at": receipt.created_at.isoformat(),
                "updated_at": receipt.updated_at.isoformat(),
            }
        except ReceiptProcessing.DoesNotExist:
            logger.error(f"Receipt not found: {receipt_id}")
            return None

    @staticmethod
    async def update_receipt_status(
        receipt_id: int, status: str, error_message: str | None = None
    ) -> bool:
        """Update receipt processing status"""
        try:
            receipt = await ReceiptProcessing.objects.aget(id=receipt_id)
            receipt.status = status
            if error_message:
                receipt.error_message = error_message
            await receipt.asave()
            logger.info(f"Updated receipt {receipt_id} status to {status}")
            return True
        except ReceiptProcessing.DoesNotExist:
            logger.error(f"Receipt not found: {receipt_id}")
            return False


# Service registry for easy access
async_services = {
    "agent": AsyncAgentService,
    "conversation": AsyncConversationService,
    "pantry": AsyncPantryService,
    "receipt": AsyncReceiptService,
}
