"""
WebSocket consumers for real-time receipt processing updates.
Implements the real-time WebSocket feedback from the plan.
"""

import json
import logging
from typing import Dict, Any

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)


class ReceiptStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time receipt processing status updates.
    
    Implements the real-time feedback system from FAZA 3 of the plan.
    Clients connect to ws://localhost:8000/ws/receipt-status/{receipt_id}/
    """

    async def connect(self):
        """Accept WebSocket connection and join receipt status group."""
        self.receipt_id = self.scope['url_route']['kwargs']['receipt_id']
        self.group_name = f'receipt_status_{self.receipt_id}'

        # Join receipt status group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()
        
        # Send initial status when client connects
        try:
            initial_status = await self.get_receipt_status(self.receipt_id)
            await self.send(text_data=json.dumps({
                'type': 'status_update',
                'receipt_id': self.receipt_id,
                **initial_status
            }))
        except Exception as e:
            logger.error(f"Error sending initial status for receipt {self.receipt_id}: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to get receipt status'
            }))

    async def disconnect(self, close_code):
        """Leave receipt status group when disconnecting."""
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle messages from WebSocket (currently not implemented)."""
        try:
            data = json.loads(text_data)
            # Could implement commands like 'get_status', 'cancel_processing', etc.
            if data.get('command') == 'get_status':
                status = await self.get_receipt_status(self.receipt_id)
                await self.send(text_data=json.dumps({
                    'type': 'status_update',
                    'receipt_id': self.receipt_id,
                    **status
                }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Internal error'
            }))

    async def receipt_status_update(self, event):
        """
        Handle status update messages sent to the group.
        Called when receipt_status_update message is sent to the group.
        """
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'receipt_id': event['receipt_id'],
            'status': event['status'],
            'status_display': event['status_display'],
            'progress': event.get('progress', 0),
            'message': event.get('message', ''),
            'timestamp': event.get('timestamp')
        }))

    async def receipt_error(self, event):
        """Handle error messages sent to the group."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'receipt_id': event['receipt_id'],
            'message': event['message'],
            'timestamp': event.get('timestamp')
        }))

    @database_sync_to_async
    def get_receipt_status(self, receipt_id: str) -> Dict[str, Any]:
        """Get current receipt status from database."""
        try:
            from inventory.models import Receipt
            receipt = Receipt.objects.get(id=receipt_id)
            
            # Calculate progress based on status
            progress_map = {
                'uploaded': 10,
                'pending_ocr': 15,
                'processing_ocr': 25,
                'ocr_in_progress': 35,
                'ocr_completed': 50,
                'ocr_done': 55,
                'processing_parsing': 65,
                'llm_in_progress': 75,
                'llm_done': 85,
                'parsing_completed': 90,
                'matching': 95,
                'ready_for_review': 98,
                'completed': 100,
                'error': 0
            }
            
            return {
                'status': receipt.status,
                'status_display': receipt.get_status_display_with_message(),
                'progress': progress_map.get(receipt.status, 0),
                'created_at': receipt.created_at.isoformat() if receipt.created_at else None,
                'updated_at': receipt.updated_at.isoformat() if receipt.updated_at else None,
                'store_name': receipt.store_name or '',
                'total': str(receipt.total) if receipt.total else None,
                'is_processing': receipt.is_processing(),
                'is_completed': receipt.is_completed(),
                'has_error': receipt.has_error(),
                'redirect_url': receipt.get_redirect_url()
            }
        except ObjectDoesNotExist:
            raise Exception(f"Receipt {receipt_id} not found")


class ReceiptListConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time updates to receipt list.
    Useful for dashboard views showing all receipts.
    """

    async def connect(self):
        """Accept connection and join general receipt updates group."""
        self.group_name = 'receipt_list_updates'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """Leave receipt list group."""
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receipt_created(self, event):
        """Handle new receipt creation notifications."""
        await self.send(text_data=json.dumps({
            'type': 'receipt_created',
            'receipt_id': event['receipt_id'],
            'status': event['status'],
            'timestamp': event.get('timestamp')
        }))

    async def receipt_updated(self, event):
        """Handle receipt status change notifications."""
        await self.send(text_data=json.dumps({
            'type': 'receipt_updated',
            'receipt_id': event['receipt_id'],
            'status': event['status'],
            'old_status': event.get('old_status'),
            'timestamp': event.get('timestamp')
        }))