# chatbot/views.py
"""
Views for Django Agent chatbot application.
Provides web interface for agent interactions.
"""
import json
import logging
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.forms import ModelForm
from django.http import Http404, HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView

from inventory.models import Product, Receipt, ReceiptLineItem

from .models import Agent, Document, ProductCorrection
from .services.agent_factory import agent_factory
from .services.receipt_service import get_receipt_service
from .utils.cache_utils import CachedViewMixin

logger = logging.getLogger(__name__)


class DashboardView(CachedViewMixin, View):
    """Main dashboard view with overview of all features"""

    cache_timeout = 300  # Cache for 5 minutes

    def get(self, request: HttpRequest):
        # Get cached statistics using fat model methods
        agent_stats = Agent.get_statistics()
        # pantry_stats = InventoryItem.get_statistics() # TODO: Uncomment when InventoryItem is fully integrated
        receipt_service = get_receipt_service()
        # receipt_stats = receipt_service.get_processing_statistics() # TODO: Uncomment when new stats are implemented
        # recent_receipts = receipt_service.get_recent_receipts(5) # TODO: Uncomment when new recent receipts are implemented

        context = {
            "agents_count": agent_stats["active_agents"],
            "documents_count": Document.objects.count(),  # TODO: Add statistics method to Document
            # "pantry_items_count": pantry_stats["total_items"], # TODO: Uncomment
            # "receipt_stats": receipt_stats, # TODO: Uncomment
            # "recent_receipts": recent_receipts, # TODO: Uncomment
            # "pantry_alerts": { # TODO: Uncomment
            #     "expired_count": pantry_stats["expired_count"],
            #     "expiring_soon_count": pantry_stats["expiring_soon_count"],
            #     "low_stock_count": pantry_stats["low_stock_count"],
            # },
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
        model = Receipt  # Use the new inventory.Receipt model
        fields = ["receipt_file"]
        labels = {
            "receipt_file": "Plik paragonu (obraz lub PDF)"
        }


class ReceiptUploadView(FormView):
    template_name = "chatbot/receipt_upload.html"
    form_class = ReceiptUploadForm

    def form_valid(self, form):
        logger.info("=== STARTING NEW RECEIPT UPLOAD PROCESS ===")
        try:
            # Zapisz paragon w bazie danych, powiązując go z zalogowanym użytkownikiem
            new_receipt = form.save(commit=False)
            new_receipt.user = self.request.user # Assuming user is authenticated due to @login_required
            new_receipt.status = 'pending'
            new_receipt.save()
            logger.info(f"✅ New Receipt record created successfully with ID: {new_receipt.id}")

            # Importuj zadanie Celery lokalnie, aby uniknąć cyklicznych zależności
            from .tasks import orchestrate_receipt_processing

            # Uruchom zadanie Celery w tle
            orchestrate_receipt_processing.delay(new_receipt.id)
            logger.info(f"✅ Orchestration task queued for receipt {new_receipt.id}")

            # Check if it's an AJAX request
            if self.request.headers.get('x-requested-with') == 'XMLHttpRequest' or self.request.accepts('application/json'):
                return JsonResponse({
                    'success': True,
                    'receipt_id': new_receipt.id,
                    'message': 'Upload successful, processing started.'
                }, status=200)
            else:
                # Przekieruj użytkownika na stronę statusu
                self.success_url = reverse_lazy('chatbot:receipt_status', kwargs={'receipt_id': new_receipt.id})
                return super().form_valid(form)
        except Exception as e:
            logger.error(f"❌ Failed to queue orchestration task for receipt: {e}", exc_info=True)
            # If an error occurs before saving, new_receipt might not exist.
            # If it exists, update its status to failed.
            new_receipt_id = None
            if 'new_receipt' in locals() and new_receipt.id:
                new_receipt.status = 'failed'
                new_receipt.processing_notes = f"Failed to start processing: {e}"
                new_receipt.save()
                new_receipt_id = new_receipt.id

            # Always return JSON for AJAX requests, even on error
            if self.request.headers.get('x-requested-with') == 'XMLHttpRequest' or self.request.accepts('application/json'):
                return JsonResponse({
                    'success': False,
                    'receipt_id': new_receipt_id, # Include ID if available
                    'error': f'Server error: {str(e)}'
                }, status=500)
            else:
                # For non-AJAX requests, re-raise the exception or handle it gracefully
                raise
        finally:
            logger.info("=== NEW RECEIPT UPLOAD PROCESS COMPLETED ===")


class ReceiptStatusView(View):
    def get(self, request, receipt_id):
        try:
            receipt = Receipt.objects.get(id=receipt_id)
        except Receipt.DoesNotExist:
            raise Http404("Paragon nie został znaleziony")

        # Determine status and redirect if ready for review
        if receipt.status == 'matching_completed': # Or 'pending_review' if we add that status
            return HttpResponseRedirect(reverse_lazy("chatbot:receipt_review", kwargs={"receipt_id": receipt.id}))

        context = {
            "receipt": receipt,
            "status_display": receipt.get_status_display(),
            "processing_notes": receipt.processing_notes,
            "title": f"Status Przetwarzania Paragonu #{receipt.id}"
        }
        return render(request, "chatbot/receipt_processing_status.html", context)


class ReceiptReviewView(View):
    def get(self, request, receipt_id):
        try:
            receipt = Receipt.objects.prefetch_related("line_items", "line_items__matched_product").get(id=receipt_id)
        except Receipt.DoesNotExist:
            raise Http404("Paragon nie został znaleziony")

        # TODO: Add a check here to redirect to status page if not ready

        # Prepare line items for the template
        line_items_data = []
        for item in receipt.line_items.all():
            line_items_data.append({
                "id": item.id,
                "product_name": item.product_name,  # Original name from OCR/LLM
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "line_total": item.line_total,
                "matched_product_id": item.matched_product.id if item.matched_product else None,
                "matched_product_name": item.matched_product.name if item.matched_product else "-- Brak dopasowania --",
                "match_confidence": item.meta.get("match_confidence", 0.0),
                "match_type": item.meta.get("match_type", "none"),
            })

        context = {
            "receipt": receipt,
            "line_items_json": json.dumps(line_items_data, cls=DjangoJSONEncoder),
            "title": f"Weryfikacja Paragonu #{receipt.id}"
        }
        return render(request, "chatbot/receipt_review.html", context)

    def post(self, request, receipt_id):
        try:
            with transaction.atomic():
                receipt = Receipt.objects.get(id=receipt_id)
                reviewed_items = json.loads(request.body.decode("utf-8"))

                for item_data in reviewed_items:
                    line_item = ReceiptLineItem.objects.get(id=item_data['id'], receipt=receipt)

                    # Update line item with reviewed data
                    line_item.quantity = Decimal(item_data.get('quantity', line_item.quantity))
                    line_item.unit_price = Decimal(item_data.get('unit_price', line_item.unit_price))
                    line_item.line_total = line_item.quantity * line_item.unit_price

                    # Update the matched product link
                    product_id = item_data.get('matched_product_id')
                    if product_id:
                        line_item.matched_product = Product.objects.get(id=product_id)
                    else:
                        # Handle creation of a new product if necessary (or link to a ghost product)
                        # For now, we just detach it if no ID is provided
                        line_item.matched_product = None

                    # Get the original product name before updating
                    original_product_name = line_item.product_name

                    # Update the original product name if user corrected it
                    line_item.product_name = item_data.get('product_name', line_item.product_name)

                    # If the product name was corrected by the user, record it
                    if original_product_name != line_item.product_name:
                        ProductCorrection.objects.create(
                            original_product_name=original_product_name,
                            corrected_product_name=line_item.product_name,
                            receipt_line_item=line_item,
                            matched_product=line_item.matched_product, # This will be None if no product was matched
                            user=request.user if request.user.is_authenticated else None,
                        )

                    line_item.save()

                # Dispatch the finalization task
                from .tasks import finalize_receipt_inventory
                finalize_receipt_inventory.delay(receipt.id)

                # Mark as pending finalization
                receipt.status = 'pending_inventory'
                receipt.save()

                return JsonResponse({
                    "success": True,
                    "message": "Paragon został zapisany i jest finalizowany w tle.",
                    "redirect_url": reverse_lazy("inventory:inventory_list") # Or some other appropriate page
                })

        except Receipt.DoesNotExist:
            return JsonResponse({"success": False, "error": "Paragon nie został znaleziony"}, status=404)
        except Product.DoesNotExist:
            return JsonResponse({"success": False, "error": "Jeden z wybranych produktów nie istnieje"}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Nieprawidłowe dane JSON"}, status=400)
        except Exception as e:
            logger.error(f"Error in receipt review for {receipt_id}: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": "Wystąpił nieoczekiwany błąd"}, status=500)


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
