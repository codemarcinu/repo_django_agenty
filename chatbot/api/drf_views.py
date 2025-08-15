import json
import logging
from typing import Dict, Any

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, CreateAPIView

from ..models import Agent, ReceiptProcessing, Document, PantryItem
from ..serializers import (
    AgentSerializer, ConversationCreateSerializer, ChatMessageSerializer,
    ReceiptProcessingStatusSerializer, DocumentSerializer, PantryItemSerializer
)
from ..services.agent_factory import agent_factory
from ..conversation_manager import conversation_manager
from ..services.async_services import AsyncReceiptService

logger = logging.getLogger(__name__)


class AgentListAPIView(ListAPIView):
    """API view for listing available agents with proper authentication"""
    queryset = Agent.objects.filter(is_active=True).order_by('name')
    serializer_class = AgentSerializer
    permission_classes = [AllowAny]  # Allow anonymous access for agent listing


class ConversationCreateAPIView(APIView):
    """API view for creating new conversations with proper CSRF protection"""
    permission_classes = [AllowAny]  # Allow anonymous conversations
    
    async def post(self, request):
        serializer = ConversationCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                validated_data = serializer.validated_data
                session_id = await conversation_manager.create_conversation(
                    agent_name=validated_data['agent_name'],
                    user_id=validated_data['user_id'],
                    title=validated_data.get('title')
                )
                return Response({
                    'success': True, 
                    'session_id': session_id
                }, status=status.HTTP_201_CREATED)
            except ValueError as e:
                return Response({
                    'success': False, 
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(f"Error creating conversation: {str(e)}")
                return Response({
                    'success': False, 
                    'error': 'Internal server error'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False, 
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ChatMessageAPIView(APIView):
    """API view for sending messages to agents with proper CSRF protection"""
    permission_classes = [AllowAny]  # Allow anonymous chat
    
    async def post(self, request):
        serializer = ChatMessageSerializer(data=request.data)
        if serializer.is_valid():
            try:
                validated_data = serializer.validated_data
                session_id = validated_data['session_id']
                message = validated_data['message']
                
                # Add user message to conversation
                await conversation_manager.add_message(
                    session_id=session_id,
                    role='user',
                    content=message,
                    metadata={'timestamp': 'auto'}
                )
                
                # Get conversation context
                context = await conversation_manager.get_conversation_context(session_id)
                if not context:
                    return Response({
                        'success': False, 
                        'error': 'Conversation not found'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # Process message through agent
                agent_name = context['conversation']['agent_name']
                agent = await agent_factory.create_agent_from_db(agent_name)
                
                now = timezone.now()
                current_datetime_str = now.strftime("%A, %Y-%m-%d %H:%M:%S")
                
                agent_input = {
                    'message': message,
                    'history': context['recent_messages'],
                    'session_id': session_id,
                    'user_id': context['conversation']['user_id'],
                    'current_datetime': current_datetime_str
                }
                
                response = await agent.safe_process(agent_input)
                
                if response.success:
                    agent_message = response.data.get('response', 'No response generated')
                    
                    # Add agent response to conversation
                    await conversation_manager.add_message(
                        session_id=session_id,
                        role='assistant',
                        content=agent_message,
                        metadata=response.metadata or {}
                    )
                    
                    return Response({
                        'success': True, 
                        'response': agent_message, 
                        'agent': agent_name, 
                        'metadata': response.metadata
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': False, 
                        'error': response.error, 
                        'agent': agent_name
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                logger.error(f"Error processing chat message: {str(e)}")
                return Response({
                    'success': False, 
                    'error': 'Internal server error'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False, 
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ConversationHistoryAPIView(APIView):
    """API view for getting conversation history"""
    permission_classes = [AllowAny]
    
    async def get(self, request, session_id):
        try:
            limit = int(request.GET.get('limit', 50))
            history = await conversation_manager.get_conversation_history(
                session_id=session_id,
                limit=limit
            )
            return Response({
                'success': True, 
                'history': history
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return Response({
                'success': False, 
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConversationInfoAPIView(APIView):
    """API view for getting conversation information"""
    permission_classes = [AllowAny]
    
    async def get(self, request, session_id):
        try:
            info = await conversation_manager.get_conversation_info(session_id)
            if info:
                return Response({
                    'success': True, 
                    'conversation': info
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False, 
                    'error': 'Conversation not found'
                }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error getting conversation info: {str(e)}")
            return Response({
                'success': False, 
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReceiptProcessingStatusAPIView(APIView):
    """API view for checking receipt processing status"""
    permission_classes = [AllowAny]
    
    def get(self, request, receipt_id):
        try:
            receipt_record = ReceiptProcessing.objects.get(id=receipt_id)
            serializer = ReceiptProcessingStatusSerializer(receipt_record)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ReceiptProcessing.DoesNotExist:
            return Response({
                'error': 'Receipt not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error getting receipt status: {str(e)}")
            return Response({
                'error': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentListAPIView(ListAPIView):
    """API view for listing documents"""
    queryset = Document.objects.all().order_by('-uploaded_at')
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]


class PantryItemListAPIView(ListAPIView):
    """API view for listing pantry items"""
    queryset = PantryItem.objects.all().order_by('-added_date')
    serializer_class = PantryItemSerializer
    permission_classes = [IsAuthenticated]