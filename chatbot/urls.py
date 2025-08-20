"""
URL configuration for chatbot app.
"""

from django.urls import path

from . import views
from . import views_logs
from . import views_monitoring
from .api import views as api_views

app_name = "chatbot"

urlpatterns = [
    # Dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),
    # Main chat interface
    path("chat/", views.ChatView.as_view(), name="chat"),
    # API endpoints
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
    # RAG Document Upload
    path("documents/", views.DocumentListView.as_view(), name="document_list"),
    path(
        "documents/upload/", views.DocumentUploadView.as_view(), name="document_upload"
    ),
    # Receipt and Pantry Management
    path("receipts/upload/", views.ReceiptUploadView.as_view(), name="receipt_upload"),
    path(
        "receipts/<int:receipt_id>/status/",
        views.ReceiptStatusView.as_view(),
        name="receipt_status",
    ),
    path(
        "api/receipts/<int:receipt_id>/status/",
        api_views.ReceiptStatusAPIView.as_view(),
        name="receipt_status_api",
    ),
    path(
        "receipts/<int:receipt_id>/review/",
        views.ReceiptReviewView.as_view(),
        name="receipt_review",
    ),
    
    # Log Viewer
    path("logs/", views_logs.LogViewerView.as_view(), name="logs_viewer"),
    path("logs/stream/", views_logs.LogStreamView.as_view(), name="logs_stream"),
    path("logs/search/", views_logs.LogSearchView.as_view(), name="logs_search"),
    
    # Monitoring Dashboard
    path("monitoring/", views_monitoring.monitoring_dashboard, name="monitoring_dashboard"),
    path("monitoring/api/health/", views_monitoring.api_health_status, name="monitoring_api_health"),
    path("monitoring/api/metrics/", views_monitoring.api_metrics, name="monitoring_api_metrics"),
    path("monitoring/api/alerts/", views_monitoring.api_alerts, name="monitoring_api_alerts"),
    path("monitoring/api/timeline/", views_monitoring.api_processing_timeline, name="monitoring_api_timeline"),
    path("api/monitoring/stats/", views_monitoring.monitoring_stats_api, name="monitoring_stats_api"),
]
