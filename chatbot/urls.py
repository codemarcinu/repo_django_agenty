"""
URL configuration for chatbot app.
"""

from django.urls import path

from . import views

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
        views.ReceiptProcessingStatusView.as_view(),
        name="receipt_processing_status",
    ),
    path(
        "api/receipts/<int:receipt_id>/status/",
        views.ReceiptProcessingStatusAPIView.as_view(),
        name="receipt_processing_status_api",
    ),
    path(
        "receipts/<int:receipt_id>/review/",
        views.ReceiptReviewView.as_view(),
        name="receipt_review",
    ),
    
]
