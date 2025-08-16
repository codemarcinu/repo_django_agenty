# chatbot/views.py
"""
Views for Django Agent chatbot application.
Provides web interface for agent interactions.
"""
import json
import logging

from django.forms import ModelForm
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, ListView

from .conversation_manager import conversation_manager
from .models import Agent, Document, ReceiptProcessing
from .services.agent_factory import agent_factory
from .services.exceptions import (
    ReceiptError,
    ReceiptNotFoundError,
    ReceiptProcessingError,
    ServiceError,
)
from .services.receipt_service import ReceiptService
from .utils.cache_utils import CachedViewMixin

logger = logging.getLogger(__name__)


from inventory.models import InventoryItem

# ... (rest of the imports)

class DashboardView(CachedViewMixin, View):
    """Main dashboard view with overview of all features"""

    cache_timeout = 300  # Cache for 5 minutes

    def get(self, request: HttpRequest):
        # Get cached statistics using fat model methods
        agent_stats = Agent.get_statistics()
        pantry_stats = InventoryItem.get_statistics()
        receipt_service = ReceiptService()
        receipt_stats = receipt_service.get_processing_statistics()
        recent_receipts = receipt_service.get_recent_receipts(5)

        context = {
            "agents_count": agent_stats["active_agents"],
            "documents_count": Document.objects.count(),  # TODO: Add statistics method to Document
            "pantry_items_count": pantry_stats["total_items"],
            "receipt_stats": receipt_stats,
            "recent_receipts": recent_receipts,
            "pantry_alerts": {
                "expired_count": pantry_stats["expired_count"],
                "expiring_soon_count": pantry_stats["expiring_soon_count"],
                "low_stock_count": pantry_stats["low_stock_count"],
            },
            "title": "Dashboard - Twój Osobisty Asystent AI",
        }
        return render(request, "chatbot/dashboard.html", context)


class DocumentForm(ModelForm):
    class Meta:
        model = Document
        fields = ["title", "file"]


class DocumentListView(ListView):
    model = Document
    template_name = "chatbot/document_list.html"
    context_object_name = "documents"


class DocumentUploadView(FormView):
    template_name = "chatbot/document_upload.html"
    form_class = DocumentForm
    success_url = reverse_lazy("chatbot:document_list")

    def form_valid(self, form):
        document = form.save()
        try:
            from .tasks import process_document_task  # Import the task

            process_document_task.delay(document.id)  # Call the task asynchronously
        except Exception as e:
            logger.error(
                f"Failed to trigger processing for document {document.id}: {e}"
            )
        return super().form_valid(form)


# New classes for Receipt Processing and Pantry Management
class ReceiptUploadForm(ModelForm):
    class Meta:
        model = ReceiptProcessing  # Use ReceiptProcessing model for file upload
        fields = ["receipt_file"]  # Support both images and PDFs for receipts


class ReceiptUploadView(FormView):
    template_name = "chatbot/receipt_upload.html"
    form_class = ReceiptUploadForm

    def form_valid(self, form):
        logger.info("=== STARTING RECEIPT UPLOAD PROCESS ===")
        logger.debug(f"Form data: {form.cleaned_data}")

        uploaded_file = form.cleaned_data["receipt_file"]
        logger.info(
            f"Uploaded file: {uploaded_file.name}, size: {uploaded_file.size} bytes, content_type: {uploaded_file.content_type}"
        )

        receipt_service = ReceiptService()

        try:
            # Create receipt record using service
            logger.info("Creating receipt record...")
            receipt_record = receipt_service.create_receipt_record(uploaded_file)
            logger.info(
                f"✅ Receipt record created successfully with ID: {receipt_record.id}"
            )
            logger.debug(
                f"Receipt record details: status={receipt_record.status}, file_path={receipt_record.receipt_file.name if receipt_record.receipt_file else 'None'}"
            )

            # Start processing using service
            logger.info(f"Starting processing for receipt ID: {receipt_record.id}")
            try:
                receipt_service.start_processing(receipt_record.id)
                logger.info(f"✅ Processing started successfully for receipt {receipt_record.id}")
            except ReceiptNotFoundError as e:
                logger.error(f"❌ Receipt not found: {e}")
                raise
            except ReceiptProcessingError as e:
                logger.error(f"❌ Processing failed for receipt {receipt_record.id}: {e}")
                # Continue to show status page even if processing failed
            except ServiceError as e:
                logger.error(f"❌ Service error processing receipt {receipt_record.id}: {e}")
                # Continue to show status page

            # Set success_url with the receipt_id
            success_url = reverse_lazy(
                "chatbot:receipt_processing_status",
                kwargs={"receipt_id": receipt_record.id},
            )
            self.success_url = success_url
            logger.info(f"Success URL set to: {success_url}")

            logger.info("=== RECEIPT UPLOAD PROCESS COMPLETED ===")
            return super().form_valid(form)

        except (ReceiptError, ServiceError) as e:
            logger.error(f"❌ Service error in receipt upload process: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in receipt upload process: {e}", exc_info=True)
            raise


class ReceiptProcessingStatusView(View):
    def get(self, request, receipt_id):
        receipt_service = ReceiptService()
        status_info = receipt_service.get_receipt_status(receipt_id)

        if not status_info:
            from django.http import Http404

            raise Http404("Paragon nie został znaleziony")

        context = {
            "receipt_id": receipt_id,
            "status_info": status_info,
        }
        return render(request, "chatbot/receipt_processing_status.html", context)


class ReceiptProcessingStatusAPIView(View):
    def get(self, request, receipt_id):
        receipt_service = ReceiptService()
        status_info = receipt_service.get_receipt_status(receipt_id)

        if not status_info:
            return JsonResponse({"error": "Paragon nie został znaleziony"}, status=404)

        return JsonResponse(
            {
                "status": status_info["status"],
                "status_display": status_info["status_display"],
                "is_ready_for_review": status_info["is_ready_for_review"],
                "is_completed": status_info["is_completed"],
                "has_error": status_info["has_error"],
                "error_message": status_info["error_message"],
                "redirect_url": status_info["redirect_url"],
            }
        )


class ReceiptReviewView(View):
    def get(self, request, receipt_id):
        receipt_service = ReceiptService()
        status_info = receipt_service.get_receipt_status(receipt_id)

        if not status_info:
            from django.http import Http404

            raise Http404("Paragon nie został znaleziony")

        if not status_info["is_ready_for_review"]:
            # If not ready for review, redirect to status page
            return HttpResponseRedirect(
                reverse_lazy(
                    "chatbot:receipt_processing_status",
                    kwargs={"receipt_id": receipt_id},
                )
            )

        extracted_products = receipt_service.get_extracted_products(receipt_id)

        context = {
            "receipt_id": receipt_id,
            "status_info": status_info,
            "raw_ocr_text": status_info["raw_ocr_text"],
            "extracted_data": json.dumps(extracted_products),
        }
        return render(request, "chatbot/receipt_review.html", context)

    def post(self, request, receipt_id):
        receipt_service = ReceiptService()

        try:
            # Parse reviewed products data from frontend
            products_data = json.loads(request.body.decode("utf-8"))

            # Finalize receipt processing using service
            success, message = receipt_service.finalize_receipt_processing(
                receipt_id, products_data
            )

            if success:
                return JsonResponse(
                    {
                        "success": True,
                        "message": message,
                        "redirect_url": reverse_lazy("inventory:inventory_by_location", kwargs={"location": "pantry"}),
                    }
                )
            else:
                return JsonResponse({"success": False, "error": message}, status=400)

        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "error": "Nieprawidłowe dane JSON"}, status=400
            )
        except Exception as e:
            logger.error(
                f"Error in receipt review for {receipt_id}: {e}", exc_info=True
            )
            return JsonResponse(
                {"success": False, "error": "Wystąpił nieoczekiwany błąd"}, status=500
            )


# TODO: Replace with InventoryItem-based view
# class PantryListView(ListView):
#     model = InventoryItem
#     template_name = "chatbot/pantry_list.html"
#     context_object_name = "pantry_items"


class ChatView(View):
    """Main chat interface view"""

    def get(self, request: HttpRequest):
        # Use fat model method
        agents = Agent.get_active_agents()
        # Get default agent (Asystent Ogólny)
        default_agent = agents.filter(name="Asystent Ogólny").first()
        context = {
            "agents": agents, 
            "default_agent": default_agent,
            "title": "Django Agent - Chat Interface"
        }
        return render(request, "chatbot/chat.html", context)


class AgentListView(View):
    """API view for listing available agents"""

    def get(self, request: HttpRequest):
        try:
            agents = []
            # Use fat model method
            for agent in Agent.get_active_agents():
                agents.append(
                    {
                        "name": agent.name,
                        "type": agent.agent_type,
                        "capabilities": agent.capabilities,
                        "description": agent.get_description(),  # Use model method
                    }
                )
            return JsonResponse({"success": True, "agents": agents})
        except Exception as e:
            logger.error(f"Error listing agents: {str(e)}")
            return JsonResponse({"success": False, "error": str(e)}, status=500)


# WARNING: This API view now requires CSRF token for POST requests.
# If this is an API endpoint, consider migrating to Django Rest Framework
# with token-based authentication instead of session-based authentication.
class ConversationCreateView(View):
    """API view for creating new conversations"""

    async def post(self, request: HttpRequest):
        try:
            data = json.loads(request.body.decode("utf-8"))
            agent_name = data.get("agent_name")
            user_id = data.get("user_id", "anonymous")
            title = data.get("title")
            if not agent_name:
                return JsonResponse(
                    {"success": False, "error": "Agent name is required"}, status=400
                )
            session_id = await conversation_manager.create_conversation(
                agent_name=agent_name, user_id=user_id, title=title
            )
            return JsonResponse({"success": True, "session_id": session_id})
        except ValueError as e:
            logger.warning(f"Validation error creating conversation: {e}")
            return JsonResponse({"success": False, "error": str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error creating conversation: {e}", exc_info=True)
            return JsonResponse(
                {"success": False, "error": "Internal server error"}, status=500
            )


# WARNING: This API view now requires CSRF token for POST requests.
# If this is an API endpoint, consider migrating to Django Rest Framework
# with token-based authentication instead of session-based authentication.
class ChatMessageView(View):
    """API view for sending messages to agents"""

    async def post(self, request: HttpRequest):
        try:
            data = json.loads(request.body.decode("utf-8"))
            session_id = data.get("session_id")
            message = data.get("message")
            if not session_id or not message:
                return JsonResponse(
                    {"success": False, "error": "Session ID and message are required"},
                    status=400,
                )
            await conversation_manager.add_message(
                session_id=session_id,
                role="user",
                content=message,
                metadata={"timestamp": "auto"},
            )
            context = await conversation_manager.get_conversation_context(session_id)
            if not context:
                return JsonResponse(
                    {"success": False, "error": "Conversation not found"}, status=404
                )
            agent_name = context["conversation"]["agent_name"]
            agent = await agent_factory.create_agent_from_db(agent_name)
            now = timezone.now()
            current_datetime_str = now.strftime("%A, %Y-%m-%d %H:%M:%S")
            agent_input = {
                "message": message,
                "history": context["recent_messages"],
                "session_id": session_id,
                "user_id": context["conversation"]["user_id"],
                "current_datetime": current_datetime_str,
            }
            response = await agent.safe_process(agent_input)
            if response.success:
                agent_message = response.data.get("response", "No response generated")
                await conversation_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=agent_message,
                    metadata=response.metadata or {},
                )
                return JsonResponse(
                    {
                        "success": True,
                        "response": agent_message,
                        "agent": agent_name,
                        "metadata": response.metadata,
                    }
                )
            else:
                return JsonResponse(
                    {"success": False, "error": response.error, "agent": agent_name}
                )
        except Exception as e:
            logger.error(f"Error processing chat message: {str(e)}")
            return JsonResponse(
                {"success": False, "error": "Internal server error"}, status=500
            )


class ConversationHistoryView(View):
    """API view for getting conversation history"""

    async def get(self, request: HttpRequest, session_id: str):
        try:
            history = await conversation_manager.get_conversation_history(
                session_id=session_id, limit=int(request.GET.get("limit", 50))
            )
            return JsonResponse({"success": True, "history": history})
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return JsonResponse(
                {"success": False, "error": "Internal server error"}, status=500
            )


class ConversationInfoView(View):
    """API view for getting conversation information"""

    async def get(self, request: HttpRequest, session_id: str):
        try:
            info = await conversation_manager.get_conversation_info(session_id)
            if info:
                return JsonResponse({"success": True, "conversation": info})
            else:
                return JsonResponse(
                    {"success": False, "error": "Conversation not found"}, status=404
                )
        except Exception as e:
            logger.error(f"Error getting conversation info: {str(e)}")
            return JsonResponse(
                {"success": False, "error": "Internal server error"}, status=500
            )
