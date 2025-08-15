from django.urls import path
from . import views
from . import receipt_views

app_name = 'chatbot_api'

urlpatterns = [
    # Agent endpoints
    path('agents/', views.AgentListView.as_view(), name='agent-list'),
    
    # Conversation endpoints
    path('conversations/create/', views.ConversationCreateView.as_view(), name='conversation-create'),
    path('conversations/<str:session_id>/history/', views.ConversationHistoryView.as_view(), name='conversation-history'),
    path('conversations/<str:session_id>/info/', views.ConversationInfoView.as_view(), name='conversation-info'),
    
    # Chat endpoints
    path('chat/message/', views.ChatMessageView.as_view(), name='chat-message'),
    
    # Receipt upload endpoints (new)
    path('receipts/upload/', receipt_views.upload_receipt, name='receipt-upload'),
    path('receipts/<int:receipt_id>/status/', receipt_views.receipt_status, name='receipt-status'),
    
    # Receipt processing endpoints (legacy) - using different URL pattern
    path('receipt-processing/<int:receipt_id>/status/', views.ReceiptProcessingStatusAPIView.as_view(), name='receipt-status-legacy'),
]