import json
import logging

from django.http import JsonResponse, HttpRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone

from ..models import Agent, Conversation, ReceiptProcessing
from ..services.agent_factory import agent_factory
from ..conversation_manager import conversation_manager

logger = logging.getLogger(__name__)

class ReceiptProcessingStatusAPIView(View):
    def get(self, request, receipt_id):
        receipt_record = get_object_or_404(ReceiptProcessing, id=receipt_id)
        if receipt_record.status == 'ready_for_review':
            return JsonResponse({'status': receipt_record.status, 'redirect_url': reverse_lazy('chatbot:receipt_review', kwargs={'receipt_id': receipt_record.id})})
        elif receipt_record.status == 'error':
            return JsonResponse({'status': receipt_record.status, 'error_message': receipt_record.error_message})
        return JsonResponse({'status': receipt_record.status})

class AgentListView(View):
    """API view for listing available agents"""
    def get(self, request: HttpRequest):
        try:
            agents = []
            for agent in Agent.objects.filter(is_active=True).order_by('name'):
                agents.append({
                    'name': agent.name,
                    'type': agent.agent_type,
                    'capabilities': agent.capabilities,
                    'description': agent.persona_prompt[:200] + "..." if len(agent.persona_prompt) > 200 else agent.persona_prompt
                })
            return JsonResponse({'success': True, 'agents': agents})
        except Exception as e:
            logger.error(f"Error listing agents: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class ConversationCreateView(View):
    """API view for creating new conversations"""
    async def post(self, request: HttpRequest):
        try:
            data = json.loads(request.body.decode('utf-8'))
            agent_name = data.get('agent_name')
            user_id = data.get('user_id', 'anonymous')
            title = data.get('title')
            if not agent_name:
                return JsonResponse({'success': False, 'error': 'Agent name is required'}, status=400)
            session_id = await conversation_manager.create_conversation(
                agent_name=agent_name,
                user_id=user_id,
                title=title
            )
            return JsonResponse({'success': True, 'session_id': session_id})
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class ChatMessageView(View):
    """API view for sending messages to agents"""
    async def post(self, request: HttpRequest):
        try:
            data = json.loads(request.body.decode('utf-8'))
            session_id = data.get('session_id')
            message = data.get('message')
            if not session_id or not message:
                return JsonResponse({'success': False, 'error': 'Session ID and message are required'}, status=400)
            await conversation_manager.add_message(
                session_id=session_id,
                role='user',
                content=message,
                metadata={'timestamp': 'auto'}
            )
            context = await conversation_manager.get_conversation_context(session_id)
            if not context:
                return JsonResponse({'success': False, 'error': 'Conversation not found'}, status=404)
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
                await conversation_manager.add_message(
                    session_id=session_id,
                    role='assistant',
                    content=agent_message,
                    metadata=response.metadata or {}
                )
                return JsonResponse({'success': True, 'response': agent_message, 'agent': agent_name, 'metadata': response.metadata})
            else:
                return JsonResponse({'success': False, 'error': response.error, 'agent': agent_name})
        except Exception as e:
            logger.error(f"Error processing chat message: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

class ConversationHistoryView(View):
    """API view for getting conversation history"""
    async def get(self, request: HttpRequest, session_id: str):
        try:
            history = await conversation_manager.get_conversation_history(
                session_id=session_id,
                limit=int(request.GET.get('limit', 50))
            )
            return JsonResponse({'success': True, 'history': history})
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

class ConversationInfoView(View):
    """API view for getting conversation information"""
    async def get(self, request: HttpRequest, session_id: str):
        try:
            info = await conversation_manager.get_conversation_info(session_id)
            if info:
                return JsonResponse({'success': True, 'conversation': info})
            else:
                return JsonResponse({'success': False, 'error': 'Conversation not found'}, status=404)
        except Exception as e:
            logger.error(f"Error getting conversation info: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)
