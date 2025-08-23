from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token

from . import receipt_views, views

app_name = "chatbot_api"

urlpatterns = [
    # Auth endpoint
    path("token-auth/", obtain_auth_token, name="api-token-auth"),
    # Agent endpoints
    path("agents/", views.AgentListView.as_view(), name="agent-list"),
    # Conversation endpoints
    path(
        "conversations/",
        views.ConversationListView.as_view(),
        name="conversation-list",
    ),
    path(
        "conversations/create/",
        views.ConversationCreateView.as_view(),
        name="conversation-create",
    ),
    path(
        "conversations/<str:session_id>/history/",
        views.ConversationHistoryView.as_view(),
        name="conversation-history",
    ),
    path(
        "conversations/<str:session_id>/info/",
        views.ConversationInfoView.as_view(),
        name="conversation-info",
    ),
    # Chat endpoints
    path("chat/message/", views.ChatMessageView.as_view(), name="chat-message"),
    # Product search API
    path("products/search/", views.ProductSearchAPIView.as_view(), name="product-search"),
    # Receipt upload endpoints (new)
    path("receipts/upload/", receipt_views.upload_receipt, name="receipt-upload"),
    path(
        "receipts/<int:receipt_id>/status/",
        receipt_views.receipt_status,
        name="receipt-status",
    ),
    # Receipt processing endpoints (legacy) - using different URL pattern
    path(
        "receipt-processing/<int:receipt_id>/status/",
        views.ReceiptStatusAPIView.as_view(),
        name="receipt-status-legacy",
    ),
    # Inventory endpoints (Prompt 9)
    path(
        "inventory/items/",
        views.InventoryItemsView.as_view(),
        name="inventory-items",
    ),
    path(
        "inventory/statistics/",
        views.InventoryStatisticsView.as_view(),
        name="inventory-statistics",
    ),
    path(
        "inventory/expiring/",
        views.ExpiringItemsView.as_view(),
        name="inventory-expiring",
    ),
    path(
        "inventory/<int:inventory_id>/consume/",
        views.ConsumeInventoryView.as_view(),
        name="inventory-consume",
    ),
    # Receipt endpoints
    path(
        "receipts/",
        views.RecentReceiptsView.as_view(),
        name="receipts-list",
    ),
    # Analytics endpoints
    path(
        "analytics/",
        views.AnalyticsView.as_view(),
        name="analytics-data",
    ),
    path(
        "analytics/top-products/",
        views.AnalyticsView.as_view(),
        name="analytics-top-products",
    ),
    path(
        "analytics/waste/",
        views.AnalyticsView.as_view(),
        name="analytics-waste",
    ),
    # Document endpoints
    path("documents/", views.DocumentListAPIView.as_view(), name="document-list"),
]
