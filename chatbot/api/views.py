import json
import logging
from .serializers import DocumentSerializer
from decimal import Decimal, InvalidOperation

from asgiref.sync import sync_to_async
from django.http import HttpRequest, JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView

from inventory.models import InventoryItem, Receipt, ConsumptionEvent

from ..conversation_manager import conversation_manager
from ..models import Agent, Document  # Import Document model
from ..services.agent_factory import agent_factory
from ..services.exceptions import (
    AgentNotFoundError,  # Corrected import # Corrected import
)
from ..services.product_matcher import get_product_matcher

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def agent_endpoint(request):
    try:
        if request.method == 'GET':
            # Logika GET
            data = {'message': 'Success', 'data': []}
            return JsonResponse(data, status=200)

        elif request.method == 'POST':
            # Logika POST
            data = {'message': 'Created', 'id': 1}
            return JsonResponse(data, status=201)

    except AgentNotFoundError as e:
        return JsonResponse(
            {'error': str(e)},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception:
        return JsonResponse(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ReceiptStatusAPIView(View):
    def get(self, request, receipt_id):
        try:
            receipt = Receipt.objects.get(id=receipt_id)
        except Receipt.DoesNotExist:
            return JsonResponse({"error": "Paragon nie został znaleziony"}, status=404)

        response_data = {
            "status": receipt.status,
            "processing_notes": receipt.processing_notes,
        }

        if receipt.status == 'matching_completed':
            response_data["redirect_url"] = reverse_lazy("chatbot:receipt_review", kwargs={"receipt_id": receipt.id})
        elif receipt.status == 'completed':
            response_data["redirect_url"] = reverse_lazy("inventory:inventory_list") # Or wherever the final destination is

        return JsonResponse(response_data)


class ProductSearchAPIView(View):
    def get(self, request: HttpRequest):
        query = request.GET.get("q", "").strip()
        if not query:
            return JsonResponse({"products": []})

        matcher = get_product_matcher()
        products = matcher.search_products(query)

        results = []
        for product in products:
            results.append({
                "id": product.id,
                "name": product.name,
                "category_name": product.category.name if product.category else None,
            })

        logger.info(f"API search for '{query}' returned {len(results)} results.")
        return JsonResponse({"products": results})


class AgentListView(View):
    """API view for listing available agents"""

    def get(self, request: HttpRequest):
        try:
            agents = []
            for agent in Agent.objects.filter(is_active=True).order_by("name"):
                agents.append(
                    {
                        "name": agent.name,
                        "type": agent.agent_type,
                        "capabilities": agent.capabilities,
                        "description": (
                            agent.persona_prompt[:200] + "..."
                            if len(agent.persona_prompt) > 200
                            else agent.persona_prompt
                        ),
                    }
                )
            return JsonResponse({"success": True, "agents": agents})
        except Exception as e:
            logger.error(f"Error listing agents: {str(e)}")
            return JsonResponse({"success": False, "error": str(e)}, status=500)


@method_decorator(csrf_exempt, name="dispatch") # Exempted because this API is expected to be used with token-based authentication and not session cookies.
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
            return JsonResponse({"success": True, "session_id": session_id}, status=201)
        except ValueError as e:
            return JsonResponse({"success": False, "error": str(e)}, status=400)
        except AgentNotFoundError as e: # Catch AgentNotFoundError specifically
            return JsonResponse({"success": False, "error": str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error creating conversation: {str(e)}")
            return JsonResponse(
                {"success": False, "error": "Internal server error"}, status=500
            )


@method_decorator(csrf_exempt, name="dispatch") # Exempted because this API is expected to be used with token-based authentication and not session cookies.
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
            # Get the main router agent instead of the agent from the conversation
            try:
                router_agent_model = await sync_to_async(Agent.objects.get)(
                    agent_type="router", is_active=True
                )
                agent = await agent_factory.create_agent_from_db(router_agent_model.name)
            except Agent.DoesNotExist:
                return JsonResponse(
                    {"success": False, "error": "No active router agent found."},
                    status=500,
                )
            except Agent.MultipleObjectsReturned:
                return JsonResponse(
                    {"success": False, "error": "Multiple active router agents found."},
                    status=500,
                )

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
                        "agent": agent.name, # Use the processing agent's name
                        "metadata": response.metadata,
                    }
                )
            else:
                return JsonResponse(
                    {"success": False, "error": response.error, "agent": agent.name}
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


class ConversationListView(View):
    """API view for listing conversations"""

    async def get(self, request: HttpRequest):
        try:
            # Get user_id from request (for now, use anonymous)
            user_id = request.GET.get("user_id", "anonymous")

            # Get conversations from conversation manager
            conversations_data = await conversation_manager.get_user_conversations(user_id)

            # Format conversations for frontend
            conversations = []
            for conv in conversations_data:
                conversations.append({
                    "id": conv.get("session_id"),
                    "title": conv.get("title", "Nowa rozmowa"),
                    "timestamp": conv.get("created_at"),
                    "last_message": conv.get("last_message", ""),
                    "message_count": conv.get("message_count", 0)
                })

            return JsonResponse({"success": True, "conversations": conversations})
        except Exception as e:
            logger.error(f"Error listing conversations: {str(e)}")
            return JsonResponse(
                {"success": False, "error": "Internal server error"}, status=500
            )


class ConsumeInventoryView(View):
    """API endpoint for consuming inventory items - POST /api/inventory/{id}/consume"""

    @method_decorator(csrf_exempt) # Exempted because this API is expected to be used with token-based authentication and not session cookies.
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, inventory_id):
        """Consume quantity from inventory item"""
        try:
            data = json.loads(request.body.decode("utf-8"))
            consumed_qty = data.get("consumed_qty")
            notes = data.get("notes", "")

            # Validate input
            if consumed_qty is None:
                return JsonResponse(
                    {"success": False, "error": "consumed_qty is required"}, status=400
                )

            try:
                consumed_qty = Decimal(str(consumed_qty))
            except (InvalidOperation, ValueError):
                return JsonResponse(
                    {"success": False, "error": "consumed_qty must be a valid number"},
                    status=400,
                )

            if consumed_qty <= 0:
                return JsonResponse(
                    {"success": False, "error": "consumed_qty must be greater than 0"},
                    status=400,
                )

            # Get inventory item
            try:
                inventory_item = InventoryItem.objects.select_related("product").get(
                    id=inventory_id
                )
            except InventoryItem.DoesNotExist:
                return JsonResponse(
                    {"success": False, "error": "Inventory item not found"}, status=404
                )

            # Check if enough quantity available
            if consumed_qty > inventory_item.quantity_remaining:
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"Not enough quantity available. Current: {inventory_item.quantity_remaining}, requested: {consumed_qty}",
                    },
                    status=400,
                )

            # Consume the quantity (this will create ConsumptionEvent)
            consumption_event = inventory_item.consume(consumed_qty, notes)

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Consumed {consumed_qty} {inventory_item.unit} of {inventory_item.product.name}",
                    "consumption_event_id": consumption_event.id,
                    "remaining_quantity": float(inventory_item.quantity_remaining),
                    "product_name": inventory_item.product.name,
                    "consumed_at": consumption_event.consumed_at.isoformat(),
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "error": "Invalid JSON in request body"}, status=400
            )
        except Exception as e:
            logger.error(f"Error consuming inventory {inventory_id}: {str(e)}")
            return JsonResponse(
                {"success": False, "error": "Internal server error"}, status=500
            )


class DocumentListAPIView(ListAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer


class InventoryItemsView(View):
    """API view for listing inventory items"""

    def get(self, request: HttpRequest):
        try:
            # Get query parameters
            limit = int(request.GET.get('limit', 50))
            offset = int(request.GET.get('offset', 0))

            # Get inventory items with product information
            inventory_items = InventoryItem.objects.select_related('product').order_by('-created_at')[offset:offset+limit]

            items = []
            for item in inventory_items:
                items.append({
                    'id': item.id,
                    'product': {
                        'id': item.product.id,
                        'name': item.product.name,
                        'category': item.product.category.name if item.product.category else None
                    },
                    'quantity_remaining': float(item.quantity_remaining),
                    'unit': item.unit,
                    'expiry_date': item.expiry_date.isoformat() if item.expiry_date else None,
                    'created_at': item.created_at.isoformat(),
                    'notes': item.notes
                })

            return JsonResponse({
                'success': True,
                'items': items,
                'count': len(items)
            })
        except Exception as e:
            logger.error(f"Error listing inventory items: {str(e)}")
            return JsonResponse(
                {'success': False, 'error': 'Internal server error'}, status=500
            )

    def post(self, request: HttpRequest):
        try:
            data = json.loads(request.body.decode("utf-8"))

            # Validate required fields
            required_fields = ['product_id', 'quantity', 'unit']
            for field in required_fields:
                if field not in data:
                    return JsonResponse(
                        {'success': False, 'error': f'{field} is required'},
                        status=400
                    )

            # Create inventory item
            inventory_item = InventoryItem.objects.create(
                product_id=data['product_id'],
                quantity_remaining=data['quantity'],
                unit=data['unit'],
                expiry_date=data.get('expiry_date'),
                notes=data.get('notes', '')
            )

            return JsonResponse({
                'success': True,
                'message': 'Inventory item created successfully',
                'item_id': inventory_item.id
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': 'Invalid JSON in request body'},
                status=400
            )
        except Exception as e:
            logger.error(f"Error creating inventory item: {str(e)}")
            return JsonResponse(
                {'success': False, 'error': 'Internal server error'}, status=500
            )


class InventoryStatisticsView(View):
    """API view for inventory statistics"""

    def get(self, request: HttpRequest):
        try:
            from django.db.models import Sum, Count
            from django.utils import timezone
            import datetime

            # Calculate statistics
            total_items = InventoryItem.objects.count()
            total_value = InventoryItem.objects.aggregate(
                total=Sum('quantity_remaining')
            )['total'] or 0

            # Expiring items (next 7 days)
            week_from_now = timezone.now() + datetime.timedelta(days=7)
            expiring_count = InventoryItem.objects.filter(
                expiry_date__lte=week_from_now,
                expiry_date__gte=timezone.now()
            ).count()

            # Low stock items (less than 1)
            low_stock_count = InventoryItem.objects.filter(
                quantity_remaining__lt=1
            ).count()

            return JsonResponse({
                'success': True,
                'statistics': {
                    'total_items': total_items,
                    'total_quantity': float(total_value),
                    'expiring_items': expiring_count,
                    'low_stock_items': low_stock_count
                }
            })
        except Exception as e:
            logger.error(f"Error getting inventory statistics: {str(e)}")
            return JsonResponse(
                {'success': False, 'error': 'Internal server error'}, status=500
            )


class ExpiringItemsView(View):
    """API view for getting expiring items"""

    def get(self, request: HttpRequest):
        try:
            from django.utils import timezone
            import datetime

            # Get days parameter (default 7)
            days = int(request.GET.get('days', 7))
            target_date = timezone.now() + datetime.timedelta(days=days)

            # Get expiring items
            expiring_items = InventoryItem.objects.select_related('product').filter(
                expiry_date__lte=target_date,
                expiry_date__gte=timezone.now(),
                quantity_remaining__gt=0
            ).order_by('expiry_date')

            items = []
            for item in expiring_items:
                days_until_expiry = (item.expiry_date - timezone.now()).days
                items.append({
                    'id': item.id,
                    'product': {
                        'id': item.product.id,
                        'name': item.product.name
                    },
                    'quantity_remaining': float(item.quantity_remaining),
                    'unit': item.unit,
                    'expiry_date': item.expiry_date.isoformat(),
                    'days_until_expiry': days_until_expiry,
                    'notes': item.notes
                })

            return JsonResponse({
                'success': True,
                'items': items,
                'count': len(items)
            })
        except Exception as e:
            logger.error(f"Error getting expiring items: {str(e)}")
            return JsonResponse(
                {'success': False, 'error': 'Internal server error'}, status=500
            )


class RecentReceiptsView(View):
    """API view for getting recent receipts"""

    def get(self, request: HttpRequest):
        try:
            limit = int(request.GET.get('limit', 10))

            # Get recent receipts
            receipts = Receipt.objects.order_by('-created_at')[:limit]

            receipts_list = []
            for receipt in receipts:
                receipts_list.append({
                    'id': receipt.id,
                    'filename': receipt.receipt_file.name if receipt.receipt_file else 'Nieznany plik',
                    'store_name': receipt.store_name,
                    'status': receipt.status,
                    'total_amount': float(receipt.total) if receipt.total else None,
                    'currency': receipt.currency,
                    'created_at': receipt.created_at.isoformat(),
                    'purchased_at': receipt.purchased_at.isoformat() if receipt.purchased_at else None,
                    'processed_at': receipt.processed_at.isoformat() if receipt.processed_at else None,
                    'processing_notes': receipt.processing_notes,
                    'line_items_count': receipt.line_items.count()
                })

            return JsonResponse({
                'success': True,
                'receipts': receipts_list,
                'count': len(receipts_list)
            })
        except Exception as e:
            logger.error(f"Error getting recent receipts: {str(e)}")
            return JsonResponse(
                {'success': False, 'error': 'Internal server error'}, status=500
            )


class AnalyticsView(View):
    """API view for analytics data"""

    def get(self, request: HttpRequest):
        try:
            from django.utils import timezone
            import datetime
            from django.db.models import Sum

            # Get time range
            time_range = request.GET.get('time_range', '30days')

            # Calculate date range
            if time_range == '7days':
                days = 7
            elif time_range == '30days':
                days = 30
            elif time_range == '90days':
                days = 90
            else:
                days = 30

            start_date = timezone.now() - datetime.timedelta(days=days)

            # Get consumption data
            consumption_events = ConsumptionEvent.objects.filter(
                consumed_at__gte=start_date
            ).select_related('inventory_item__product')

            # Calculate analytics
            total_consumed = consumption_events.aggregate(
                total=Sum('consumed_quantity')
            )['total'] or 0

            # Get top consumed products
            top_products_data = consumption_events.values(
                'inventory_item__product__name'
            ).annotate(
                total_consumed=Sum('consumed_quantity')
            ).order_by('-total_consumed')[:10]

            top_products = [
                {
                    'product_name': item['inventory_item__product__name'],
                    'total_consumed': float(item['total_consumed'])
                }
                for item in top_products_data
            ]

            # Calculate waste data (items with 0 quantity)
            waste_items = InventoryItem.objects.filter(
                quantity_remaining=0,
                updated_at__gte=start_date
            ).count()

            return JsonResponse({
                'success': True,
                'analytics': {
                    'time_range': time_range,
                    'total_consumed': float(total_consumed),
                    'waste_items': waste_items,
                    'top_products': top_products
                }
            })
        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            return JsonResponse(
                {'success': False, 'error': 'Internal server error'}, status=500
            )
