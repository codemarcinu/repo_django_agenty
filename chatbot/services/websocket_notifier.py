"""
WebSocket notification service for real-time receipt processing updates.
Integrates with the receipt processing pipeline to send live status updates.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebSocketNotifier:
    """
    Service for sending WebSocket notifications about receipt processing status.
    Implements the real-time notification system from FAZA 3 of the plan.
    """

    def __init__(self):
        self.channel_layer = get_channel_layer()

    def send_receipt_status_update(
        self,
        receipt_id: int,
        status: str,
        status_display: str,
        progress: Optional[int] = None,
        message: Optional[str] = None
    ):
        """
        Send status update to all clients connected to this receipt's WebSocket.
        
        Args:
            receipt_id: ID of the receipt being processed
            status: New status code
            status_display: Human-readable status message
            progress: Progress percentage (0-100)
            message: Additional message or details
        """
        if not self.channel_layer:
            logger.warning("Channel layer not configured, skipping WebSocket notification")
            return

        group_name = f'receipt_status_{receipt_id}'
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    'type': 'receipt_status_update',
                    'receipt_id': receipt_id,
                    'status': status,
                    'status_display': status_display,
                    'progress': progress,
                    'message': message or '',
                    'timestamp': timezone.now().isoformat()
                }
            )
            logger.debug(f"Sent status update for receipt {receipt_id}: {status}")
        except Exception as e:
            logger.error(f"Failed to send WebSocket status update for receipt {receipt_id}: {e}")

    def send_receipt_error(
        self,
        receipt_id: int,
        error_message: str
    ):
        """
        Send error notification to clients connected to this receipt's WebSocket.
        
        Args:
            receipt_id: ID of the receipt that encountered an error
            error_message: Description of the error
        """
        if not self.channel_layer:
            logger.warning("Channel layer not configured, skipping WebSocket error notification")
            return

        group_name = f'receipt_status_{receipt_id}'
        
        try:
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    'type': 'receipt_error',
                    'receipt_id': receipt_id,
                    'message': error_message,
                    'timestamp': timezone.now().isoformat()
                }
            )
            logger.debug(f"Sent error notification for receipt {receipt_id}: {error_message}")
        except Exception as e:
            logger.error(f"Failed to send WebSocket error notification for receipt {receipt_id}: {e}")

    def send_receipt_list_update(
        self,
        event_type: str,  # 'created', 'updated', 'deleted'
        receipt_id: int,
        status: str,
        old_status: Optional[str] = None
    ):
        """
        Send update to receipt list WebSocket (for dashboard views).
        
        Args:
            event_type: Type of event ('created', 'updated', 'deleted')
            receipt_id: ID of the receipt
            status: Current status
            old_status: Previous status (for updates)
        """
        if not self.channel_layer:
            logger.warning("Channel layer not configured, skipping WebSocket list notification")
            return

        group_name = 'receipt_list_updates'
        
        try:
            message = {
                'type': f'receipt_{event_type}',
                'receipt_id': receipt_id,
                'status': status,
                'timestamp': timezone.now().isoformat()
            }
            
            if old_status:
                message['old_status'] = old_status

            async_to_sync(self.channel_layer.group_send)(group_name, message)
            logger.debug(f"Sent list update for receipt {receipt_id}: {event_type}")
        except Exception as e:
            logger.error(f"Failed to send WebSocket list update for receipt {receipt_id}: {e}")


# Global instance
_websocket_notifier = None


def get_websocket_notifier() -> WebSocketNotifier:
    """Get global WebSocketNotifier instance."""
    global _websocket_notifier
    if _websocket_notifier is None:
        _websocket_notifier = WebSocketNotifier()
    return _websocket_notifier


class ReceiptStatusNotificationMixin:
    """
    Mixin to add WebSocket notification capabilities to receipt processing services.
    Use this to easily add real-time notifications to existing services.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.websocket_notifier = get_websocket_notifier()

    def _notify_status_update(
        self,
        receipt_id: int,
        status: str,
        progress: Optional[int] = None,
        message: Optional[str] = None
    ):
        """Internal method to send status update notification."""
        try:
            from inventory.models import Receipt
            receipt = Receipt.objects.get(id=receipt_id)
            status_display = receipt.get_status_display_with_message()
            
            self.websocket_notifier.send_receipt_status_update(
                receipt_id=receipt_id,
                status=status,
                status_display=status_display,
                progress=progress,
                message=message
            )
        except Exception as e:
            logger.error(f"Error sending status notification for receipt {receipt_id}: {e}")

    def _notify_error(self, receipt_id: int, error_message: str):
        """Internal method to send error notification."""
        self.websocket_notifier.send_receipt_error(receipt_id, error_message)

    def _notify_list_update(self, event_type: str, receipt_id: int, status: str, old_status: str = None):
        """Internal method to send list update notification."""
        self.websocket_notifier.send_receipt_list_update(event_type, receipt_id, status, old_status)


# Convenience functions for direct use
def notify_receipt_status_update(receipt_id: int, status: str, progress: int = None, message: str = None):
    """Convenience function to send receipt status update."""
    notifier = get_websocket_notifier()
    
    try:
        from inventory.models import Receipt
        receipt = Receipt.objects.get(id=receipt_id)
        status_display = receipt.get_status_display_with_message()
        
        notifier.send_receipt_status_update(
            receipt_id=receipt_id,
            status=status,
            status_display=status_display,
            progress=progress,
            message=message
        )
    except Exception as e:
        logger.error(f"Error in notify_receipt_status_update for receipt {receipt_id}: {e}")


def notify_receipt_error(receipt_id: int, error_message: str):
    """Convenience function to send receipt error notification."""
    notifier = get_websocket_notifier()
    notifier.send_receipt_error(receipt_id, error_message)


def notify_receipt_created(receipt_id: int, status: str):
    """Convenience function to notify about new receipt creation."""
    notifier = get_websocket_notifier()
    notifier.send_receipt_list_update('created', receipt_id, status)


def notify_receipt_updated(receipt_id: int, status: str, old_status: str = None):
    """Convenience function to notify about receipt status change."""
    notifier = get_websocket_notifier()
    notifier.send_receipt_list_update('updated', receipt_id, status, old_status)