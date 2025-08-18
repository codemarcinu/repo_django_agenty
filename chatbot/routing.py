"""
WebSocket routing configuration for real-time updates.
Part of FAZA 3 implementation from the plan.
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # Individual receipt status updates
    re_path(r'ws/receipt-status/(?P<receipt_id>\w+)/$', consumers.ReceiptStatusConsumer.as_asgi()),
    
    # General receipt list updates (for dashboard)
    re_path(r'ws/receipt-list/$', consumers.ReceiptListConsumer.as_asgi()),
]