# chatbot/views.py
"""
API Views for Django Agent chatbot application.
Frontend layer has been removed - these views only provide API functionality.
"""
import json
import logging
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import Http404, HttpRequest, JsonResponse
from django.views import View
import os
from django.conf import settings
from django.http import HttpResponse

from inventory.models import Product, Receipt, ReceiptLineItem

from .models import Agent, Document, ProductCorrection
from .services.agent_factory import agent_factory
from .services.receipt_service import get_receipt_service

logger = logging.getLogger(__name__)


# API-based view classes only - frontend layer has been removed

class ReceiptUploadAPI(View):
    """API for receipt uploads"""
    
    def post(self, request):
        logger.info("=== STARTING NEW RECEIPT UPLOAD PROCESS (API) ===")
        try:
            # Create a new receipt from the uploaded file
            receipt_file = request.FILES.get('receipt_file')
            if not receipt_file:
                return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)
                
            new_receipt = Receipt(
                receipt_file=receipt_file,
                user=request.user if request.user.is_authenticated else None,
                status='pending'
            )
            new_receipt.save()
            logger.info(f"✅ New Receipt record created successfully with ID: {new_receipt.id}")

            # Queue processing task
            from .tasks import orchestrate_receipt_processing
            orchestrate_receipt_processing.delay(new_receipt.id)
            logger.info(f"✅ Orchestration task queued for receipt {new_receipt.id}")

            return JsonResponse({
                'success': True,
                'receipt_id': new_receipt.id,
                'message': 'Upload successful, processing started.'
            }, status=200)
        except Exception as e:
            logger.error(f"❌ Failed to process receipt upload: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': f'Server error: {str(e)}'
            }, status=500)
        finally:
            logger.info("=== RECEIPT UPLOAD PROCESS COMPLETED (API) ===")


class ReceiptStatusAPI(View):
    """API for checking receipt processing status"""
    
    def get(self, request, receipt_id):
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            return JsonResponse({
                'success': True,
                'receipt_id': receipt.id,
                'status': receipt.status,
                'status_display': receipt.get_status_display(),
                'processing_step': receipt.processing_step,
                'processing_notes': receipt.processing_notes,
                'created_at': receipt.created_at.isoformat() if receipt.created_at else None,
                'updated_at': receipt.updated_at.isoformat() if receipt.updated_at else None
            })
        except Receipt.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Receipt not found'}, status=404)
        except Exception as e:
            logger.error(f"Error getting receipt status: {e}", exc_info=True)
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class OCRReviewAPI(View):
    """API for reviewing and editing OCR text"""
    
    def get(self, request, receipt_id):
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            if receipt.processing_step not in ['ocr_completed', 'quality_gate']:
                return JsonResponse({
                    'success': False,
                    'error': f'Receipt is not ready for OCR review (current step: {receipt.processing_step})'
                }, status=400)
                
            return JsonResponse({
                'success': True,
                'receipt_id': receipt.id,
                'ocr_text': receipt.raw_ocr_text or ""
            })
        except Receipt.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Receipt not found'}, status=404)
        except Exception as e:
            logger.error(f"Error getting OCR text: {e}", exc_info=True)
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    def post(self, request, receipt_id):
        logger.info(f"[OCR Review] Received user confirmation for OCR text of Receipt ID: {receipt_id}.")
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            data = json.loads(request.body.decode("utf-8"))
            edited_ocr_text = data.get('ocr_text', '').strip()

            if not edited_ocr_text:
                return JsonResponse({"success": False, "error": "OCR text cannot be empty"}, status=400)

            # Update the OCR text
            receipt.raw_ocr_text = edited_ocr_text
            receipt.save(update_fields=['raw_ocr_text'])

            # Continue with parsing
            from .tasks import continue_receipt_processing_after_ocr_review
            logger.info(f"[OCR Review] Triggering 'continue_receipt_processing_after_ocr_review' task for Receipt ID: {receipt_id}.")
            continue_receipt_processing_after_ocr_review.delay(receipt_id)

            return JsonResponse({
                "success": True,
                "message": "OCR text updated. Continuing processing..."
            })
        except Receipt.DoesNotExist:
            return JsonResponse({"success": False, "error": "Receipt not found"}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
        except Exception as e:
            logger.error(f"Error updating OCR text: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": str(e)}, status=500)


class ReceiptReviewAPI(View):
    """API for reviewing and updating receipt line items"""
    
    def get(self, request, receipt_id):
        try:
            receipt = Receipt.objects.prefetch_related("line_items", "line_items__matched_product").get(id=receipt_id)
            
            # Prepare line items for the response
            line_items_data = []
            for item in receipt.line_items.all():
                line_items_data.append({
                    "id": item.id,
                    "product_name": item.product_name,
                    "quantity": float(item.quantity),
                    "unit_price": float(item.unit_price),
                    "line_total": float(item.line_total),
                    "matched_product_id": item.matched_product.id if item.matched_product else None,
                    "matched_product_name": item.matched_product.name if item.matched_product else None,
                    "match_confidence": item.meta.get("match_confidence", 0.0),
                    "match_type": item.meta.get("match_type", "none"),
                })
            
            receipt_data = {
                "id": receipt.id,
                "status": receipt.status,
                "store_name": receipt.store_name,
                "receipt_date": receipt.receipt_date.isoformat() if receipt.receipt_date else None,
                "total_amount": float(receipt.total_amount) if receipt.total_amount else None,
                "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
                "line_items": line_items_data
            }
            
            return JsonResponse({
                "success": True,
                "receipt": receipt_data
            })
        except Receipt.DoesNotExist:
            return JsonResponse({"success": False, "error": "Receipt not found"}, status=404)
        except Exception as e:
            logger.error(f"Error getting receipt details: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": str(e)}, status=500)
    
    def post(self, request, receipt_id):
        logger.info(f"[Receipt Review] Received user confirmation for final products of Receipt ID: {receipt_id}.")
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
                            matched_product=line_item.matched_product,
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
                    "message": "Receipt saved and finalization in progress."
                })
        except Receipt.DoesNotExist:
            return JsonResponse({"success": False, "error": "Receipt not found"}, status=404)
        except Product.DoesNotExist:
            return JsonResponse({"success": False, "error": "One of the selected products does not exist"}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
        except Exception as e:
            logger.error(f"Error in receipt review for {receipt_id}: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": str(e)}, status=500)


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


from django.views.generic import TemplateView

class LiveLogsView(View):
    """
    A simple view to display live logs from the app.log file.
    For development purposes only.
    """
    def get(self, request):
        log_file_path = os.path.join(settings.LOG_DIR, 'app.log')
        try:
            with open(log_file_path, 'r') as f:
                logs = f.read()
            return HttpResponse(logs, content_type='text/plain')
        except FileNotFoundError:
            return HttpResponse("Log file not found.", status=404, content_type='text/plain')
        except Exception as e:
            return HttpResponse(f"Error reading log file: {e}", status=500, content_type='text/plain')

class LiveLogsPageView(TemplateView):
    template_name = "live_logs.html"
