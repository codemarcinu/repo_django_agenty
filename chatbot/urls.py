"""
URL configuration for chatbot app.
API-only endpoints - frontend layer has been removed.
"""

from django.urls import path

from . import views, views_logs, views_monitoring

app_name = "chatbot"

urlpatterns = [
    # API endpoints for agent interaction
    path("api/agents/", views.AgentListView.as_view(), name="agent_list"),
    path(
        "api/conversations/",
        views.ConversationCreateView.as_view(),
        name="conversation_create",
    ),
    path("api/chat/", views.ChatMessageView.as_view(), name="chat_message"),
    path(
        "api/conversations/<str:session_id>/history/",
        views.ConversationHistoryView.as_view(),
        name="conversation_history",
    ),
    path(
        "api/conversations/<str:session_id>/info/",
        views.ConversationInfoView.as_view(),
        name="conversation_info",
    ),
    
    # API endpoints for receipt processing
    path("api/receipts/upload/", views.ReceiptUploadAPI.as_view(), name="receipt_upload_api"),
    path(
        "api/receipts/<int:receipt_id>/status/",
        views.ReceiptStatusAPI.as_view(),
        name="receipt_status_api",
    ),
    path(
        "api/receipts/<int:receipt_id>/ocr-review/",
        views.OCRReviewAPI.as_view(),
        name="receipt_ocr_review_api",
    ),
    path(
        "api/receipts/<int:receipt_id>/review/",
        views.ReceiptReviewAPI.as_view(),
        name="receipt_review_api",
    ),

    # Monitoring API endpoints
    path("api/monitoring/health/", views_monitoring.api_health_status, name="monitoring_api_health"),
    path("api/monitoring/metrics/", views_monitoring.api_metrics, name="monitoring_api_metrics"),
    path("api/monitoring/alerts/", views_monitoring.api_alerts, name="monitoring_api_alerts"),
    path("api/monitoring/timeline/", views_monitoring.api_processing_timeline, name="monitoring_api_timeline"),
    path("api/monitoring/stats/", views_monitoring.monitoring_stats_api, name="monitoring_stats_api"),
    path("api/logs/live/", views.LiveLogsView.as_view(), name="live_logs"),
    path("logs/", views.LiveLogsPageView.as_view(), name="live_logs_page"),
]
