"""
Inventory app API views for the receipt processing pipeline.
Frontend layer has been removed - these views only provide API functionality.
"""

import json
from datetime import date, timedelta

from celery.result import AsyncResult
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import Http404, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt  # For API endpoint

from chatbot.services.inventory_service import get_inventory_service
from chatbot.services.optimized_queries import (
    get_inventory_items_for_listing,
    get_product_details,
    get_receipts_for_listing,
)

from .models import (
    Category,
    InventoryItem,
    Product,
    Receipt,
    ReceiptLineItem,
)


def dashboard_api(request):
    """API endpoint for dashboard data with inventory summary and alerts."""
    inventory_service = get_inventory_service()

    # Get inventory summary
    summary = inventory_service.get_inventory_summary()

    # Get expiring items (next 7 days)
    expiring_items_data = []
    for item in inventory_service.get_expiring_items(days=7)[:5]:
        expiring_items_data.append({
            'id': item.id,
            'product_name': item.product.name if item.product else None,
            'quantity_remaining': float(item.quantity_remaining),
            'expiry_date': item.expiry_date.isoformat() if item.expiry_date else None,
            'days_until_expiry': (item.expiry_date - date.today()).days if item.expiry_date else None,
        })

    # Get low stock items
    low_stock_items_data = []
    for item in inventory_service.get_low_stock_items()[:5]:
        low_stock_items_data.append({
            'id': item.id,
            'product_name': item.product.name if item.product else None,
            'quantity_remaining': float(item.quantity_remaining),
            'reorder_point': float(item.product.reorder_point) if item.product and item.product.reorder_point else 0,
        })

    # Get recent receipts
    recent_receipts_data = []
    for receipt in get_receipts_for_listing().filter(status="completed")[:5]:
        recent_receipts_data.append({
            'id': receipt.id,
            'store_name': receipt.store_name,
            'receipt_date': receipt.receipt_date.isoformat() if receipt.receipt_date else None,
            'total_amount': float(receipt.total_amount) if receipt.total_amount else None,
        })

    # Get advanced statistics
    top_categories = inventory_service.get_top_spending_categories(days=30)
    heatmap_data = inventory_service.get_consumption_heatmap_data(days=30)
    recent_activity = inventory_service.get_recent_activity(days=7)
    
    # Convert data to JSON-serializable format
    top_categories_data = [{'category': c[0], 'amount': float(c[1])} for c in top_categories]
    
    response_data = {
        "summary": summary,
        "expiring_items": expiring_items_data,
        "low_stock_items": low_stock_items_data,
        "recent_receipts": recent_receipts_data,
        "top_categories": top_categories_data,
        "heatmap_data": heatmap_data,
        "recent_activity": recent_activity,
    }

    return JsonResponse(response_data)

def monitoring_api(request):
    """API endpoint for monitoring dashboard data with receipt processing statistics."""
    # Aggregate data
    receipt_status_counts = Receipt.objects.values('status').annotate(count=Count('id'))
    receipt_step_counts = Receipt.objects.values('processing_step').annotate(count=Count('id'))

    # Convert querysets to dicts for easier JSON serialization
    status_data = {item['status']: item['count'] for item in receipt_status_counts}
    step_data = {item['processing_step']: item['count'] for item in receipt_step_counts}

    # Get 10 most recent error receipts
    error_receipts = Receipt.objects.filter(status='error').order_by('-updated_at')[:10]
    error_receipts_data = []
    for r in error_receipts:
        error_receipts_data.append({
            'id': r.id,
            'store_name': r.store_name,
            'purchased_at': r.purchased_at.isoformat() if r.purchased_at else None,
            'error_message': r.error_message,
            'updated_at': r.updated_at.isoformat(),
        })

    # Calculate average processing time
    # This requires a bit more complex query, let's simplify for now
    total_completed = status_data.get('completed', 0)
    average_processing_time = "N/A"  # Placeholder for actual calculation

    response_data = {
        'status_counts': status_data,
        'step_counts': step_data,
        'error_receipts': error_receipts_data,
        'average_processing_time': average_processing_time,
        'total_pending': status_data.get('pending', 0) + status_data.get('review_pending', 0),
        'total_processing': status_data.get('processing', 0),
        'total_errors': status_data.get('error', 0),
    }
    
    return JsonResponse(response_data)


class InventoryItemsAPI(View):
    """API view for inventory items with filtering and pagination."""

    def get(self, request):
        queryset = get_inventory_items_for_listing()

        # Filter by search query
        search = request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(product__name__icontains=search)
                | Q(product__brand__icontains=search)
                | Q(product__category__name__icontains=search)
            )

        # Filter by location
        location = request.GET.get("location")
        if location:
            queryset = queryset.filter(storage_location=location)

        # Filter by category
        category = request.GET.get("category")
        if category:
            queryset = queryset.filter(product__category_id=category)

        # Filter by status
        status = request.GET.get("status")
        if status == "expiring":
            expiry_threshold = date.today() + timedelta(days=7)
            queryset = queryset.filter(expiry_date__lte=expiry_threshold)
        elif status == "expired":
            queryset = queryset.filter(expiry_date__lt=date.today())
        elif status == "low_stock":
            queryset = queryset.filter(
                quantity_remaining__lte=F("product__reorder_point")
            )

        # Pagination
        page_size = int(request.GET.get("page_size", 20))
        page = int(request.GET.get("page", 1))
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        # Format response data
        items_data = []
        for item in page_obj:
            items_data.append({
                "id": item.id,
                "product_id": item.product.id if item.product else None,
                "product_name": item.product.name if item.product else None,
                "product_brand": item.product.brand if item.product else None,
                "category": item.product.category.name if item.product and item.product.category else None,
                "quantity_remaining": float(item.quantity_remaining),
                "storage_location": item.storage_location,
                "storage_location_display": item.get_storage_location_display(),
                "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
            })

        # Get filter options
        categories = [{"id": c.id, "name": c.name} for c in Category.objects.all().order_by("name")]
        locations = [{"value": choice[0], "display": choice[1]} for choice in InventoryItem.STORAGE_CHOICES]

        response_data = {
            "items": items_data,
            "total_items": paginator.count,
            "page": page,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "filter_options": {
                "categories": categories,
                "locations": locations,
            },
            "filters_applied": {
                "search": search or "",
                "location": location or "",
                "category": category or "",
                "status": status or "",
            }
        }

        return JsonResponse(response_data)


class ProductsAPI(View):
    """API view for products with filtering and pagination."""

    def get(self, request):
        queryset = (
            Product.objects.select_related("category")
            .annotate(
                inventory_count=Count(
                    "inventory_items", filter=Q(inventory_items__quantity_remaining__gt=0)
                ),
                total_quantity=Sum(
                    "inventory_items__quantity_remaining",
                    filter=Q(inventory_items__quantity_remaining__gt=0),
                ),
            )
            .order_by("name")
        )

        # Filter by search query
        search = request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(brand__icontains=search)
                | Q(category__name__icontains=search)
            )

        # Filter by category
        category = request.GET.get("category")
        if category:
            queryset = queryset.filter(category_id=category)

        # Pagination
        page_size = int(request.GET.get("page_size", 20))
        page = int(request.GET.get("page", 1))
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        # Format response data
        products_data = []
        for product in page_obj:
            products_data.append({
                "id": product.id,
                "name": product.name,
                "brand": product.brand,
                "category_id": product.category.id if product.category else None,
                "category_name": product.category.name if product.category else None,
                "is_active": product.is_active,
                "reorder_point": float(product.reorder_point) if product.reorder_point else None,
                "inventory_count": product.inventory_count,
                "total_quantity": float(product.total_quantity) if product.total_quantity else 0,
            })

        # Get categories for filter options
        categories = [{"id": c.id, "name": c.name} for c in Category.objects.all().order_by("name")]

        response_data = {
            "products": products_data,
            "total_products": paginator.count,
            "page": page,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "filter_options": {
                "categories": categories,
            },
            "filters_applied": {
                "search": search or "",
                "category": category or "",
            }
        }

        return JsonResponse(response_data)


class ProductDetailAPI(View):
    """API view for a single product with inventory history."""

    def get(self, request, pk):
        try:
            # Use optimized query to get the product with all related data
            product = get_product_details(pk)
            
            # Prepare product data for JSON response
            inventory_items = []
            for item in product.inventory_items.all():
                inventory_items.append({
                    "id": item.id,
                    "quantity_remaining": float(item.quantity_remaining),
                    "storage_location": item.storage_location,
                    "storage_location_display": item.get_storage_location_display(),
                    "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "updated_at": item.updated_at.isoformat() if item.updated_at else None
                })
            
            # Get aliases
            aliases = []
            if hasattr(product, 'aliases'):
                for alias in product.aliases.all():
                    aliases.append({
                        "id": alias.id,
                        "name": alias.name,
                        "confidence": float(alias.confidence) if alias.confidence else None,
                        "count": alias.count
                    })
            
            # Build response data
            response_data = {
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "brand": product.brand,
                    "category_id": product.category.id if product.category else None,
                    "category_name": product.category.name if product.category else None,
                    "is_active": product.is_active,
                    "reorder_point": float(product.reorder_point) if product.reorder_point else None,
                    "created_at": product.created_at.isoformat() if product.created_at else None,
                    "updated_at": product.updated_at.isoformat() if product.updated_at else None
                },
                "inventory_items": inventory_items,
                "aliases": aliases,
                "total_inventory_count": len(inventory_items),
                "total_quantity": sum(float(item["quantity_remaining"]) for item in inventory_items)
            }
            
            return JsonResponse(response_data)
        except Product.DoesNotExist:
            return JsonResponse({"error": "Product not found"}, status=404)


class ReceiptsAPI(View):
    """API view for receipts with filtering and pagination."""

    def get(self, request):
        queryset = get_receipts_for_listing()

        # Filter by search query
        search = request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(store_name__icontains=search) | Q(processing_notes__icontains=search)
            )

        # Filter by status
        status = request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        # Pagination
        page_size = int(request.GET.get("page_size", 20))
        page = int(request.GET.get("page", 1))
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        # Format response data
        receipts_data = []
        for receipt in page_obj:
            receipts_data.append({
                "id": receipt.id,
                "store_name": receipt.store_name,
                "receipt_date": receipt.receipt_date.isoformat() if receipt.receipt_date else None,
                "total_amount": float(receipt.total_amount) if receipt.total_amount else None,
                "status": receipt.status,
                "status_display": receipt.get_status_display() if hasattr(receipt, 'get_status_display') else receipt.status,
                "processing_step": receipt.processing_step,
                "item_count": receipt.line_items.count(),
                "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
                "updated_at": receipt.updated_at.isoformat() if receipt.updated_at else None,
            })

        # Status choices for filter options
        status_choices = [{"value": status[0], "display": status[1]} for status in Receipt.STATUS_CHOICES]

        response_data = {
            "receipts": receipts_data,
            "total_receipts": paginator.count,
            "page": page,
            "page_size": page_size,
            "total_pages": paginator.num_pages,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "filter_options": {
                "status_choices": status_choices,
            },
            "filters_applied": {
                "search": search or "",
                "status": status or "",
            }
        }

        return JsonResponse(response_data)


class ReceiptDetailAPI(View):
    """API view for a single receipt with its line items."""

    def get(self, request, pk):
        try:
            receipt = Receipt.objects.get(pk=pk)
            
            # Get line items
            line_items = receipt.line_items.select_related(
                "matched_product", "matched_product__category"
            ).order_by("id")
            
            # Prepare receipt data for JSON response
            line_items_data = []
            for item in line_items:
                line_items_data.append({
                    "id": item.id,
                    "product_name": item.product_name,
                    "quantity": float(item.quantity) if item.quantity else None,
                    "unit_price": float(item.unit_price) if item.unit_price else None,
                    "line_total": float(item.line_total) if item.line_total else None,
                    "matched_product_id": item.matched_product.id if item.matched_product else None,
                    "matched_product_name": item.matched_product.name if item.matched_product else None,
                    "matched_product_brand": item.matched_product.brand if item.matched_product else None,
                    "matched_product_category": item.matched_product.category.name if item.matched_product and item.matched_product.category else None,
                })
            
            # Build response data
            response_data = {
                "receipt": {
                    "id": receipt.id,
                    "store_name": receipt.store_name,
                    "receipt_date": receipt.receipt_date.isoformat() if receipt.receipt_date else None,
                    "receipt_file": receipt.receipt_file.url if receipt.receipt_file else None,
                    "status": receipt.status,
                    "status_display": receipt.get_status_display() if hasattr(receipt, 'get_status_display') else receipt.status,
                    "processing_step": receipt.processing_step,
                    "processing_notes": receipt.processing_notes,
                    "total_amount": float(receipt.total_amount) if receipt.total_amount else None,
                    "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
                    "updated_at": receipt.updated_at.isoformat() if receipt.updated_at else None,
                },
                "line_items": line_items_data,
                "total_items": len(line_items_data),
            }
            
            return JsonResponse(response_data)
        except Receipt.DoesNotExist:
            return JsonResponse({"error": "Receipt not found"}, status=404)


def expiring_items_api(request):
    """API endpoint for items that are expiring soon."""
    days = request.GET.get("days", 7)
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 7

    inventory_service = get_inventory_service()
    items = inventory_service.get_expiring_items(days=days)

    # Pagination
    page_size = int(request.GET.get("page_size", 20))
    page = int(request.GET.get("page", 1))
    paginator = Paginator(items, page_size)
    page_obj = paginator.get_page(page)

    # Format response data
    items_data = []
    for item in page_obj:
        items_data.append({
            "id": item.id,
            "product_id": item.product.id if item.product else None,
            "product_name": item.product.name if item.product else None,
            "product_brand": item.product.brand if item.product else None,
            "category": item.product.category.name if item.product and item.product.category else None,
            "quantity_remaining": float(item.quantity_remaining),
            "storage_location": item.storage_location,
            "storage_location_display": item.get_storage_location_display(),
            "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
            "days_until_expiry": (item.expiry_date - date.today()).days if item.expiry_date else None,
        })

    response_data = {
        "items": items_data,
        "total_items": paginator.count,
        "page": page,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
        "days": days
    }

    return JsonResponse(response_data)


def low_stock_items_api(request):
    """API endpoint for items with low stock."""
    inventory_service = get_inventory_service()
    items = inventory_service.get_low_stock_items()

    # Pagination
    page_size = int(request.GET.get("page_size", 20))
    page = int(request.GET.get("page", 1))
    paginator = Paginator(items, page_size)
    page_obj = paginator.get_page(page)

    # Format response data
    items_data = []
    for item in page_obj:
        items_data.append({
            "id": item.id,
            "product_id": item.product.id if item.product else None,
            "product_name": item.product.name if item.product else None,
            "product_brand": item.product.brand if item.product else None,
            "category": item.product.category.name if item.product and item.product.category else None,
            "quantity_remaining": float(item.quantity_remaining),
            "storage_location": item.storage_location,
            "storage_location_display": item.get_storage_location_display(),
            "reorder_point": float(item.product.reorder_point) if item.product and item.product.reorder_point else None,
        })

    response_data = {
        "items": items_data,
        "total_items": paginator.count,
        "page": page,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    }

    return JsonResponse(response_data)


def inventory_by_location_api(request, location):
    """API endpoint for inventory items filtered by storage location."""
    items = get_inventory_items_for_listing().filter(storage_location=location)

    # Pagination
    page_size = int(request.GET.get("page_size", 20))
    page = int(request.GET.get("page", 1))
    paginator = Paginator(items, page_size)
    page_obj = paginator.get_page(page)

    # Get location display name
    location_display = dict(InventoryItem.STORAGE_CHOICES).get(location, location)

    # Format response data
    items_data = []
    for item in page_obj:
        items_data.append({
            "id": item.id,
            "product_id": item.product.id if item.product else None,
            "product_name": item.product.name if item.product else None,
            "product_brand": item.product.brand if item.product else None,
            "category": item.product.category.name if item.product and item.product.category else None,
            "quantity_remaining": float(item.quantity_remaining),
            "storage_location": item.storage_location,
            "storage_location_display": item.get_storage_location_display(),
            "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
        })

    response_data = {
        "items": items_data,
        "total_items": paginator.count,
        "page": page,
        "page_size": page_size,
        "total_pages": paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
        "location": location,
        "location_display": location_display,
    }

    return JsonResponse(response_data)


def recent_receipts_api(request):
    """API endpoint for recent receipts."""
    receipts = get_receipts_for_listing().filter(status="completed")[:20]

    # Format response data
    receipts_data = []
    for receipt in receipts:
        receipts_data.append({
            "id": receipt.id,
            "store_name": receipt.store_name,
            "receipt_date": receipt.receipt_date.isoformat() if receipt.receipt_date else None,
            "total_amount": float(receipt.total_amount) if receipt.total_amount else None,
            "status": receipt.status,
            "status_display": receipt.get_status_display() if hasattr(receipt, 'get_status_display') else receipt.status,
            "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
        })

    response_data = {
        "receipts": receipts_data,
        "count": len(receipts_data),
    }

    return JsonResponse(response_data)


class CategoriesAPI(View):
    """API view for categories."""

    def get(self, request):
        categories = Category.objects.annotate(
            product_count=Count("products"),
            inventory_count=Count(
                "products__inventory_items",
                filter=Q(products__inventory_items__quantity_remaining__gt=0),
            ),
        ).order_by("name")
        
        # Format response data
        categories_data = []
        for category in categories:
            categories_data.append({
                "id": category.id,
                "name": category.name,
                "product_count": category.product_count,
                "inventory_count": category.inventory_count,
            })
        
        response_data = {
            "categories": categories_data,
            "count": len(categories_data)
        }
        
        return JsonResponse(response_data)


def upload_receipt_api(request):
    """API endpoint for getting receipt upload instructions."""
    
    # Return instructions for uploading receipts via API
    response_data = {
        "message": "Please use the POST endpoint to upload a receipt file",
        "endpoint": "/api/receipts/upload/",
        "method": "POST",
        "content_type": "multipart/form-data",
        "parameters": {
            "receipt_file": "The receipt file to upload (image or PDF)"
        },
        "authentication": "Optional, depends on server configuration",
        "response": {
            "success": "Boolean indicating if the upload was successful",
            "receipt_id": "ID of the created receipt if successful",
            "message": "Status message",
            "error": "Error message if unsuccessful"
        }
    }
    
    return JsonResponse(response_data)


def receipt_processing_status(request, receipt_id):
    """
    Checks the status of a receipt processing task.
    """
    try:
        receipt = Receipt.objects.get(pk=receipt_id)
        if receipt.task_id:
            task_result = AsyncResult(receipt.task_id)
            status = task_result.status
            result = task_result.result
        else:
            status = receipt.status
            result = receipt.processing_notes

        return JsonResponse({
            "receipt_id": receipt_id,
            "status": status,
            "result": result
        })
    except Receipt.DoesNotExist:
        return JsonResponse({"error": "Receipt not found"}, status=404)


def receipt_review(request, receipt_id):
    """
    View for reviewing and correcting receipt data.
    """
    try:
        receipt = Receipt.objects.get(pk=receipt_id)
        line_items = receipt.line_items.select_related('matched_product').order_by('id')
        all_products = Product.objects.all().values('id', 'name', 'brand', 'category__name')

        # Prepare data for JSON serialization
        receipt_data = {
            'id': receipt.id,
            'store_name': receipt.store_name,
            'purchased_at': receipt.purchased_at.isoformat() if receipt.purchased_at else None,
            'total': str(receipt.total) if receipt.total else None,
            'status': receipt.status,
        }

        line_items_data = []
        for item in line_items:
            line_items_data.append({
                'id': item.id,
                'product_name': item.product_name,
                'quantity': str(item.quantity),
                'unit_price': str(item.unit_price),
                'line_total': str(item.line_total),
                'matched_product_id': item.matched_product.id if item.matched_product else None,
                'matched_product_name': item.matched_product.name if item.matched_product else None,
                'original_name': item.product_name, # Store original name for feedback loop
            })

        products_data = []
        for product in all_products:
            products_data.append({
                'id': product['id'],
                'name': product['name'],
                'brand': product['brand'],
                'category_name': product['category__name'],
            })

        context = {
            'receipt': receipt, # For Django template rendering (e.g., receipt ID in title)
            'receipt_json': JsonResponse(receipt_data, safe=False).content.decode('utf-8'),
            'line_items_json': JsonResponse(line_items_data, safe=False).content.decode('utf-8'),
            'all_products_json': JsonResponse(products_data, safe=False).content.decode('utf-8'),
        }

        return render(request, "inventory/receipt_review.html", context)
    except Receipt.DoesNotExist:
        return JsonResponse({"error": "Receipt not found"}, status=404)

@csrf_exempt # For API endpoint, consider proper CSRF handling in production
def correct_receipt_data(request, receipt_id):
    if request.method == 'POST':
        try:
            receipt = Receipt.objects.get(pk=receipt_id)
            data = json.loads(request.body)
            line_items_data = data.get('line_items', [])

            with transaction.atomic():
                for item_data in line_items_data:
                    item_id = item_data.get('id')
                    is_deleted = item_data.get('is_deleted', False)
                    is_new_product = item_data.get('is_new_product', False)
                    original_name = item_data.get('original_name', '')

                    if is_deleted:
                        if item_id:
                            ReceiptLineItem.objects.filter(id=item_id, receipt=receipt).delete()
                        continue

                    line_item = None
                    if item_id:
                        try:
                            line_item = ReceiptLineItem.objects.get(id=item_id, receipt=receipt)
                        except ReceiptLineItem.DoesNotExist:
                            # This should ideally not happen if frontend sends correct IDs
                            continue
                    else:
                        # This case is for newly added line items (not yet implemented in frontend)
                        # For now, we assume all items come from existing receipt
                        continue

                    # Update line item fields
                    line_item.product_name = item_data.get('product_name', line_item.product_name)
                    line_item.quantity = item_data.get('quantity', line_item.quantity)
                    line_item.unit_price = item_data.get('unit_price', line_item.unit_price)
                    line_item.line_total = item_data.get('line_total', line_item.line_total)

                    matched_product_id = item_data.get('matched_product_id')
                    if is_new_product:
                        # Create new product
                        new_product_name = item_data.get('product_name')
                        if new_product_name:
                            product, created = Product.objects.get_or_create(name=new_product_name, defaults={'is_active': True})
                            line_item.matched_product = product
                            # Add original name as alias for new product
                            if original_name and original_name != new_product_name:
                                product.add_alias(original_name)
                        else:
                            line_item.matched_product = None # No product name provided for new product
                    elif matched_product_id:
                        # Link to existing product
                        try:
                            product = Product.objects.get(id=matched_product_id)
                            line_item.matched_product = product
                            # Add original name as alias for existing product
                            if original_name and original_name != product.name:
                                product.add_alias(original_name)
                        except Product.DoesNotExist:
                            line_item.matched_product = None # Product not found
                    else:
                        line_item.matched_product = None # No product matched

                    line_item.save()

                # Mark receipt as completed after review
                receipt.status = "completed"
                receipt.processing_step = "done"
                receipt.save()

            return JsonResponse({"status": "success", "message": "Receipt data corrected successfully."})

        except Receipt.DoesNotExist:
            return JsonResponse({"error": "Receipt not found"}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt # For API endpoint, consider proper CSRF handling in production
def get_monitoring_data(request):
    """API endpoint to provide monitoring data for auto-refresh."""
    if request.method == 'GET':
        receipt_status_counts = Receipt.objects.values('status').annotate(count=Count('id'))
        receipt_step_counts = Receipt.objects.values('processing_step').annotate(count=Count('id'))

        status_data = {item['status']: item['count'] for item in receipt_status_counts}
        step_data = {item['processing_step']: item['count'] for item in receipt_step_counts}

        error_receipts = Receipt.objects.filter(status='error').order_by('-updated_at')[:10]
        error_receipts_data = []
        for r in error_receipts:
            error_receipts_data.append({
                'id': r.id,
                'store_name': r.store_name,
                'purchased_at': r.purchased_at.isoformat() if r.purchased_at else None,
                'error_message': r.error_message,
                'updated_at': r.updated_at.isoformat(),
            })

        total_completed = status_data.get('completed', 0)
        average_processing_time = "N/A"

        response_data = {
            'status_counts': status_data,
            'step_counts': step_data,
            'error_receipts': error_receipts_data,
            'average_processing_time': average_processing_time,
            'total_pending': status_data.get('pending', 0) + status_data.get('review_pending', 0),
            'total_processing': status_data.get('processing', 0),
            'total_errors': status_data.get('error', 0),
        }
        return JsonResponse(response_data)
    return JsonResponse({"error": "Invalid request method"}, status=405)
