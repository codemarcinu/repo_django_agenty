# chatbot/views.py
"""
Views for Django Agent chatbot application.
Provides web interface for agent interactions.
"""
import asyncio
import json
import logging
import os 
from typing import Any, Dict

from django.http import JsonResponse, HttpRequest, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView
from django.forms import ModelForm
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.files.storage import FileSystemStorage 
from django.conf import settings 
from django.utils import timezone
import datetime

from .models import Agent, Conversation, Document, PantryItem, ReceiptProcessing
from .agent_factory import agent_factory
from .conversation_manager import conversation_manager
from .rag_processor import rag_processor
from .receipt_processor import receipt_processor 

logger = logging.getLogger(__name__)

class DashboardView(View):
    """Main dashboard view with overview of all features"""
    def get(self, request: HttpRequest):
        # Get statistics
        agents_count = Agent.objects.filter(is_active=True).count()
        documents_count = Document.objects.count()
        pantry_items_count = PantryItem.objects.count()
        recent_receipts = ReceiptProcessing.objects.order_by('-uploaded_at')[:5]
        
        context = {
            'agents_count': agents_count,
            'documents_count': documents_count,
            'pantry_items_count': pantry_items_count,
            'recent_receipts': recent_receipts,
            'title': 'Dashboard - Twój Osobisty Asystent AI'
        }
        return render(request, 'chatbot/dashboard.html', context)

class DocumentForm(ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'file']

class DocumentListView(ListView):
    model = Document
    template_name = 'chatbot/document_list.html'
    context_object_name = 'documents'

class DocumentUploadView(FormView):
    template_name = 'chatbot/document_upload.html'
    form_class = DocumentForm
    success_url = reverse_lazy('chatbot:document_list')

    def form_valid(self, form):
        document = form.save()
        try:
            rag_processor.process_document(document.id)
        except Exception as e:
            logger.error(f"Failed to trigger processing for document {document.id}: {e}")
        return super().form_valid(form)

# New classes for Receipt Processing and Pantry Management
class ReceiptUploadForm(ModelForm):
    class Meta:
        model = ReceiptProcessing # Use ReceiptProcessing model for file upload
        fields = ['receipt_file'] # Support both images and PDFs for receipts

class ReceiptUploadView(FormView):
    template_name = 'chatbot/receipt_upload.html'
    form_class = ReceiptUploadForm
    success_url = reverse_lazy('chatbot:receipt_processing_status') # Redirect to status page

    def form_valid(self, form):
        receipt_record = form.save(commit=False)
        receipt_record.status = 'uploaded'
        receipt_record.save()

        # Process the receipt using the helper function for async in sync context
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_in_executor(None, self._process_receipt_sync, receipt_record.id)
        except Exception as e:
            logger.error(f"Failed to start receipt processing: {e}")
            receipt_record.status = 'error'
            receipt_record.error_message = f"Nie udało się rozpocząć przetwarzania: {e}"
            receipt_record.save()

        self.success_url = reverse_lazy('chatbot:receipt_processing_status', kwargs={'receipt_id': receipt_record.id})
        return super().form_valid(form)
    
    def _process_receipt_sync(self, receipt_id):
        """Helper method to run async receipt processing in sync context"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(receipt_processor.process_receipt(receipt_id))
        except Exception as e:
            logger.error(f"Error processing receipt {receipt_id}: {e}")
        finally:
            loop.close()

class ReceiptProcessingStatusView(View):
    def get(self, request, receipt_id):
        receipt_record = get_object_or_404(ReceiptProcessing, id=receipt_id)
        context = {
            'receipt_id': receipt_id,
            'status': receipt_record.status,
            'error_message': receipt_record.error_message,
        }
        return render(request, 'chatbot/receipt_processing_status.html', context)

@method_decorator(csrf_exempt, name='dispatch')
class ReceiptProcessingStatusAPIView(View):
    def get(self, request, receipt_id):
        receipt_record = get_object_or_404(ReceiptProcessing, id=receipt_id)
        if receipt_record.status == 'ready_for_review':
            return JsonResponse({'status': receipt_record.status, 'redirect_url': reverse_lazy('chatbot:receipt_review', kwargs={'receipt_id': receipt_record.id})})
        elif receipt_record.status == 'error':
            return JsonResponse({'status': receipt_record.status, 'error_message': receipt_record.error_message})
        return JsonResponse({'status': receipt_record.status})

class ReceiptReviewView(View):
    def get(self, request, receipt_id):
        receipt_record = get_object_or_404(ReceiptProcessing, id=receipt_id)
        if receipt_record.status != 'ready_for_review':
            # If not ready for review, redirect to status page
            return HttpResponseRedirect(reverse_lazy('chatbot:receipt_processing_status', kwargs={'receipt_id': receipt_id}))

        context = {
            'receipt_id': receipt_id,
            'raw_ocr_text': receipt_record.raw_ocr_text,
            'extracted_data': json.dumps(receipt_record.extracted_data) if receipt_record.extracted_data else '[]',
        }
        return render(request, 'chatbot/receipt_review.html', context)

    @method_decorator(csrf_exempt, name='dispatch')
    def post(self, request, receipt_id):
        receipt_record = get_object_or_404(ReceiptProcessing, id=receipt_id)
        try:
            # Assuming data comes as JSON from the frontend
            products_data = json.loads(request.body.decode('utf-8'))
            receipt_processor.update_pantry(products_data)
            
            receipt_record.status = 'completed'
            receipt_record.processed_at = timezone.now()
            receipt_record.save()

            return JsonResponse({'success': True, 'redirect_url': reverse_lazy('chatbot:pantry_list')})
        except Exception as e:
            receipt_record.status = 'error'
            receipt_record.error_message = f"Błąd podczas zapisywania danych do spiżarni: {e}"
            receipt_record.save()
            logger.error(f"Error saving reviewed receipt data for {receipt_id}: {e}", exc_info=True)
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

class PantryListView(ListView):
    model = PantryItem
    template_name = 'chatbot/pantry_list.html'
    context_object_name = 'pantry_items'


def run_async(coro):
    """Helper to run async functions in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

class ChatView(View):
    """Main chat interface view"""
    def get(self, request: HttpRequest):
        agents = Agent.objects.filter(is_active=True).order_by('name')
        context = {
            'agents': agents,
            'title': 'Django Agent - Chat Interface'
        }
        return render(request, 'chatbot/chat.html', context)

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
    def post(self, request: HttpRequest):
        try:
            data = json.loads(request.body.decode('utf-8'))
            agent_name = data.get('agent_name')
            user_id = data.get('user_id', 'anonymous')
            title = data.get('title')
            if not agent_name:
                return JsonResponse({'success': False, 'error': 'Agent name is required'}, status=400)
            session_id = run_async(conversation_manager.create_conversation(
                agent_name=agent_name,
                user_id=user_id,
                title=title
            ))
            return JsonResponse({'success': True, 'session_id': session_id})
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class ChatMessageView(View):
    """API view for sending messages to agents"""
    def post(self, request: HttpRequest):
        try:
            data = json.loads(request.body.decode('utf-8'))
            session_id = data.get('session_id')
            message = data.get('message')
            if not session_id or not message:
                return JsonResponse({'success': False, 'error': 'Session ID and message are required'}, status=400)
            run_async(conversation_manager.add_message(
                session_id=session_id,
                role='user',
                content=message,
                metadata={'timestamp': 'auto'}
            ))
            context = run_async(conversation_manager.get_conversation_context(session_id))
            if not context:
                return JsonResponse({'success': False, 'error': 'Conversation not found'}, status=404)
            agent_name = context['conversation']['agent_name']
            agent = run_async(agent_factory.create_agent_from_db(agent_name))
            now = timezone.now()
            current_datetime_str = now.strftime("%A, %Y-%m-%d %H:%M:%S")
            agent_input = {
                'message': message,
                'history': context['recent_messages'],
                'session_id': session_id,
                'user_id': context['conversation']['user_id'],
                'current_datetime': current_datetime_str
            }
            response = run_async(agent.safe_process(agent_input))
            if response.success:
                agent_message = response.data.get('response', 'No response generated')
                run_async(conversation_manager.add_message(
                    session_id=session_id,
                    role='assistant',
                    content=agent_message,
                    metadata=response.metadata or {}
                ))
                return JsonResponse({'success': True, 'response': agent_message, 'agent': agent_name, 'metadata': response.metadata})
            else:
                return JsonResponse({'success': False, 'error': response.error, 'agent': agent_name})
        except Exception as e:
            logger.error(f"Error processing chat message: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

class ConversationHistoryView(View):
    """API view for getting conversation history"""
    def get(self, request: HttpRequest, session_id: str):
        try:
            history = run_async(conversation_manager.get_conversation_history(
                session_id=session_id,
                limit=int(request.GET.get('limit', 50))
            ))
            return JsonResponse({'success': True, 'history': history})
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)

class ConversationInfoView(View):
    """API view for getting conversation information"""
    def get(self, request: HttpRequest, session_id: str):
        try:
            info = run_async(conversation_manager.get_conversation_info(session_id))
            if info:
                return JsonResponse({'success': True, 'conversation': info})
            else:
                return JsonResponse({'success': False, 'error': 'Conversation not found'}, status=404)
        except Exception as e:
            logger.error(f"Error getting conversation info: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)
