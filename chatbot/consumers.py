"""
WebSocket consumers for real-time receipt processing updates.
Implements the real-time WebSocket feedback from the plan.
"""

import json
import logging
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


class ReceiptStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time receipt processing status updates.
    Clients connect to ws://localhost:8000/ws/receipt-status/{receipt_id}/
    """

    async def connect(self):
        """Accept WebSocket connection and join receipt status group."""
        self.receipt_id = self.scope["url_route"]["kwargs"]["receipt_id"]
        self.group_name = f"receipt_status_{self.receipt_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        try:
            initial_status = await self.get_receipt_status(self.receipt_id)
            await self.send(text_data=json.dumps({"type": "status_update", **initial_status}))
        except Exception as e:
            logger.error(f"Error sending initial status for receipt {self.receipt_id}: {e}")
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    async def disconnect(self, close_code):
        """Leave receipt status group when disconnecting."""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receipt_status_update(self, event: dict):
        """
        Handle status update messages sent to the group.
        """
        await self.send(text_data=json.dumps({"type": "status_update", **event}))

    async def receipt_error(self, event: dict):
        """
        Handle error messages sent to the group.
        """
        await self.send(text_data=json.dumps({"type": "error", **event}))

    @database_sync_to_async
    def get_receipt_status(self, receipt_id: str) -> dict[str, Any]:
        """Get current receipt status from database."""
        from inventory.models import Receipt

        try:
            receipt = Receipt.objects.get(id=receipt_id)

            progress_map = {
                "uploaded": 10,
                "processing_started": 30,
                "fallback_to_local": 35,
                "ocr_in_progress": 40,
                "ocr_completed": 60,
                "quality_gate": 75,
                "parsing_in_progress": 80,
                "parsing_completed": 90,
                "matching_in_progress": 95,
                "matching_completed": 98,
                "review_pending": 98,
                "done": 100,
                "failed": 100,
            }

            return {
                "receipt_id": receipt.id,
                "status": receipt.status,
                "processing_step": receipt.processing_step,
                "status_display": receipt.get_status_display_with_message(),
                "progress": progress_map.get(receipt.processing_step, 0),
                "is_completed": receipt.is_completed(),
                "has_error": receipt.has_error(),
                "redirect_url": receipt.get_redirect_url(),
            }
        except ObjectDoesNotExist:
            raise Exception(f"Receipt {receipt_id} not found")


class ReceiptListConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time updates to receipt list.
    """

    async def connect(self):
        """Accept connection and join general receipt updates group."""
        self.group_name = "receipt_list_updates"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        """Leave receipt list group."""
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receipt_created(self, event: dict):
        """Handle new receipt creation notifications."""
        await self.send(text_data=json.dumps({"type": "receipt_created", **event}))

    async def receipt_updated(self, event: dict):
        """Handle receipt status change notifications."""
        await self.send(text_data=json.dumps({"type": "receipt_updated", **event}))
