"""
Service for sending real-time notifications via WebSockets.
"""

import logging
from datetime import datetime

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


class WebSocketNotifier:
    """Handles sending notifications to WebSocket consumers."""

    def __init__(self):
        self.channel_layer = get_channel_layer()

    def _send_to_group(self, group_name: str, message_type: str, payload: dict):
        """Helper to send a message to a WebSocket group."""
        if not self.channel_layer:
            logger.warning("Channel layer not available. Cannot send WebSocket message.")
            return

        try:
            async_to_sync(self.channel_layer.group_send)(
                group_name,
                {
                    "type": message_type,
                    **payload,
                },
            )
        except Exception as e:
            logger.error(f"Failed to send WebSocket message to group {group_name}: {e}")

    def send_status_update(
        self, receipt_id: int, status: str, message: str, progress: int
    ):
        """
        Send a status update for a specific receipt.
        """
        group_name = f"receipt_status_{receipt_id}"
        payload = {
            "receipt_id": receipt_id,
            "status": status,
            "message": message,
            "progress": progress,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send_to_group(group_name, "receipt.status.update", payload)

    def send_error(self, receipt_id: int, message: str):
        """
        Send an error message for a specific receipt.
        """
        group_name = f"receipt_status_{receipt_id}"
        payload = {
            "receipt_id": receipt_id,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send_to_group(group_name, "receipt.error", payload)

    def notify_receipt_created(self, receipt_id: int, status: str):
        """
        Notify the general list that a new receipt was created.
        """
        self._send_to_group(
            "receipt_list_updates",
            "receipt.created",
            {"receipt_id": receipt_id, "status": status, "timestamp": datetime.utcnow().isoformat()},
        )


# Singleton instance
_notifier_instance = None


def get_websocket_notifier() -> WebSocketNotifier:
    """Get the singleton instance of the WebSocketNotifier."""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = WebSocketNotifier()
    return _notifier_instance
