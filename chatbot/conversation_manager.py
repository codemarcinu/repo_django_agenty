"""
Conversation management system for Django Agent.
Handles conversation lifecycle, message storage, and context management.
"""

import logging
from typing import Any

from django.utils import timezone

from .interfaces import ConversationManagerInterface
from .models import Conversation, Message
from .services.async_services import AsyncConversationService

logger = logging.getLogger(__name__)


class ConversationManager(ConversationManagerInterface):
    """
    Manages conversations, messages, and context for Django Agent system.
    """

    async def create_conversation(
        self,
        agent_name: str,
        user_id: str | None = None,
        title: str | None = None,
    ) -> str:
        """Create new conversation and return session_id"""
        return await AsyncConversationService.create_conversation_with_agent(
            agent_name=agent_name, user_id=user_id, title=title
        )

    async def add_message(
        self, session_id: str, role: str, content: str, metadata: dict | None = None
    ):
        """Add message to conversation"""
        return await AsyncConversationService.add_message_to_conversation(
            session_id=session_id, role=role, content=content, metadata=metadata
        )

    async def get_conversation_history(
        self, session_id: str, limit: int = 50
    ) -> list[dict]:
        """Get conversation history"""
        return await AsyncConversationService.get_conversation_messages(
            session_id=session_id, limit=limit, format_for_ai=False
        )

    async def get_conversation_info(self, session_id: str) -> dict | None:
        """Get conversation information"""
        try:
            conversation = await Conversation.objects.select_related("agent").aget(
                session_id=session_id
            )

            message_count = await Message.objects.filter(
                conversation=conversation
            ).acount()

            return {
                "session_id": str(conversation.session_id),
                "agent_name": conversation.agent.name,
                "agent_type": conversation.agent.agent_type,
                "title": conversation.title,
                "user_id": conversation.user_id,
                "summary": conversation.summary,
                "is_active": conversation.is_active,
                "message_count": message_count,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "metadata": conversation.metadata,
            }

        except Conversation.DoesNotExist:
            logger.error(f"Conversation not found: {session_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting conversation info: {str(e)}")
            return None

    async def update_conversation_summary(self, session_id: str, summary: str):
        """Update conversation summary"""
        try:
            conversation = await Conversation.objects.aget(session_id=session_id)
            conversation.summary = summary
            conversation.updated_at = timezone.now()
            await conversation.asave()

            logger.info(f"Updated summary for conversation {session_id}")

        except Conversation.DoesNotExist:
            logger.error(f"Conversation not found: {session_id}")
            raise ValueError(f"Conversation not found: {session_id}")
        except Exception as e:
            logger.error(f"Error updating conversation summary: {str(e)}")
            raise

    async def update_conversation_title(self, session_id: str, title: str):
        """Update conversation title"""
        try:
            conversation = await Conversation.objects.aget(session_id=session_id)
            conversation.title = title
            conversation.updated_at = timezone.now()
            await conversation.asave()

            logger.info(f"Updated title for conversation {session_id}")

        except Conversation.DoesNotExist:
            logger.error(f"Conversation not found: {session_id}")
            raise ValueError(f"Conversation not found: {session_id}")
        except Exception as e:
            logger.error(f"Error updating conversation title: {str(e)}")
            raise

    async def deactivate_conversation(self, session_id: str):
        """Deactivate conversation"""
        try:
            conversation = await Conversation.objects.aget(session_id=session_id)
            conversation.is_active = False
            conversation.updated_at = timezone.now()
            await conversation.asave()

            logger.info(f"Deactivated conversation {session_id}")

        except Conversation.DoesNotExist:
            logger.error(f"Conversation not found: {session_id}")
            raise ValueError(f"Conversation not found: {session_id}")
        except Exception as e:
            logger.error(f"Error deactivating conversation: {str(e)}")
            raise

    async def list_user_conversations(
        self, user_id: str, limit: int = 20
    ) -> list[dict]:
        """List conversations for a user"""
        try:
            conversations = []
            async for conv in (
                Conversation.objects.select_related("agent")
                .filter(user_id=user_id, is_active=True)
                .order_by("-updated_at")[:limit]
            ):

                message_count = await Message.objects.filter(conversation=conv).acount()

                conversations.append(
                    {
                        "session_id": str(conv.session_id),
                        "agent_name": conv.agent.name,
                        "title": conv.title,
                        "summary": conv.summary,
                        "message_count": message_count,
                        "created_at": conv.created_at.isoformat(),
                        "updated_at": conv.updated_at.isoformat(),
                    }
                )

            return conversations

        except Exception as e:
            logger.error(f"Error listing user conversations: {str(e)}")
            return []

    async def get_conversation_context(
        self, session_id: str, context_window: int = 10
    ) -> dict[str, Any]:
        """Get conversation context for AI processing"""
        try:
            conversation_info = await self.get_conversation_info(session_id)
            if not conversation_info:
                return {}

            # Get recent messages formatted for AI
            recent_messages = await AsyncConversationService.get_conversation_messages(
                session_id=session_id, limit=context_window, format_for_ai=True
            )

            return {
                "conversation": conversation_info,
                "recent_messages": recent_messages,
                "message_count": len(recent_messages),
                "context_window": context_window,
            }

        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}")
            return {}


# Global conversation manager instance
conversation_manager = ConversationManager()
