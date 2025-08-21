"""
Inventory app views implementing user interface for receipt processing pipeline.
Part of Prompt 8: Dashboard i widoki użytkownika.
"""

import json
from datetime import date, timedelta

from celery.result import AsyncResult
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt  # For API endpoint
from django.views.generic import DetailView, ListView

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


def dashboard(request):
    """Main dashboard view with inventory summary and alerts."""
    inventory_service = get_inventory_service()

    # Get inventory summary
    summary = inventory_service.get_inventory_summary()

    # Get expiring items (next 7 days)
    expiring_items = inventory_service.get_expiring_items(days=7)[:5]

    # Get low stock items
    low_stock_items = inventory_service.get_low_stock_items()[:5]

    # Get recent receipts (optimized)
    recent_receipts = get_receipts_for_listing().filter(status="completed")[:5]

    # Get advanced statistics (Prompt 10 features)
    top_categories = inventory_service.get_top_spending_categories(days=30)
    heatmap_data = inventory_service.get_consumption_heatmap_data(days=30)
    recent_activity = inventory_service.get_recent_activity(days=7)

    context = {
        "summary": summary,
        "expiring_items": expiring_items,
        "low_stock_items": low_stock_items,
        "recent_receipts": recent_receipts,
        "top_categories": top_categories,
        "heatmap_data": heatmap_data,
        "recent_activity": recent_activity,
    }

    return render(request, "inventory/dashboard.html", context)

def monitoring_dashboard(request):
    """Monitoring dashboard view with receipt processing statistics."""
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
    # For a more accurate average, we'd need to calculate timedelta for each completed receipt
    # and then average them. For simplicity, we'll just get counts for now.
    total_completed = status_data.get('completed', 0)
    total_processing_time = 0 # Placeholder for actual calculation
    if total_completed > 0:
        # This is a simplified average. A more accurate one would iterate through completed receipts
        # and sum (processed_at - uploaded_at) or (updated_at - created_at)
        # For now, we'll just indicate it's not directly calculated here.
        average_processing_time = "N/A"
    else:
        average_processing_time = "N/A"

    context = {
        'status_counts_json': json.dumps(status_data),
        'step_counts_json': json.dumps(step_data),
        'error_receipts_json': json.dumps(error_receipts_data),
        'average_processing_time': average_processing_time,
        'total_pending': status_data.get('pending', 0) + status_data.get('review_pending', 0),
        'total_processing': status_data.get('processing', 0),
        'total_errors': status_data.get('error', 0),
    }

    return render(request, "inventory/monitoring_dashboard.html", context)


class InventoryListView(ListView):
    """List view for inventory items with filtering and pagination."""

    model = InventoryItem
    template_name = "inventory/inventory_list.html"
    context_object_name = "items"
    paginate_by = 20

    def get_queryset(self):
        queryset = get_inventory_items_for_listing()

        # Filter by search query
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(product__name__icontains=search)
                | Q(product__brand__icontains=search)
                | Q(product__category__name__icontains=search)
            )

        # Filter by location
        location = self.request.GET.get("location")
        if location:
            queryset = queryset.filter(storage_location=location)

        # Filter by category
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(product__category_id=category)

        # Filter by status
        status = self.request.GET.get("status")
        if status == "expiring":
            expiry_threshold = date.today() + timedelta(days=7)
            queryset = queryset.filter(expiry_date__lte=expiry_threshold)
        elif status == "expired":
            queryset = queryset.filter(expiry_date__lt=date.today())
        elif status == "low_stock":
            queryset = queryset.filter(
                quantity_remaining__lte=F("product__reorder_point")
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter options
        context["categories"] = Category.objects.all().order_by("name")
        context["locations"] = InventoryItem.STORAGE_CHOICES

        # Add current filters
        context["current_search"] = self.request.GET.get("search", "")
        context["current_location"] = self.request.GET.get("location", "")
        context["current_category"] = self.request.GET.get("category", "")
        context["current_status"] = self.request.GET.get("status", "")

        return context


class ProductListView(ListView):
    """List view for products with filtering."""

    model = Product
    template_name = "inventory/product_list.html"
    context_object_name = "products"
    paginate_by = 20

    def get_queryset(self):
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
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(brand__icontains=search)
                | Q(category__name__icontains=search)
            )

        # Filter by category
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category_id=category)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all().order_by("name")
        context["current_search"] = self.request.GET.get("search", "")
        context["current_category"] = self.request.GET.get("category", "")
        return context


class ProductDetailView(DetailView):
    """Detail view for a single product with inventory history."""

    model = Product
    template_name = "inventory/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        """Use optimized query to prefetch all related data."""
        return get_product_details(self.kwargs['pk'])


class ReceiptListView(ListView):
    """List view for receipts."""

    model = Receipt
    template_name = "inventory/receipt_list.html"
    context_object_name = "receipts"
    paginate_by = 20

    def get_queryset(self):
        queryset = get_receipts_for_listing()

        # Filter by search query
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(store_name__icontains=search) | Q(processing_notes__icontains=search)
            )

        # Filter by status
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = Receipt.STATUS_CHOICES
        context["current_search"] = self.request.GET.get("search", "")
        context["current_status"] = self.request.GET.get("status", "")
        return context


class ReceiptDetailView(DetailView):
    """Detail view for a single receipt."""

    model = Receipt
    template_name = "inventory/receipt_detail.html"
    context_object_name = "receipt"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        receipt = self.get_object()

        # Get line items
        context["line_items"] = receipt.line_items.select_related(
            "matched_product", "matched_product__category"
        ).order_by("id")

        return context


def expiring_items(request):
    """View for items that are expiring soon."""
    days = request.GET.get("days", 7)
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 7

    inventory_service = get_inventory_service()
    items = inventory_service.get_expiring_items(days=days)

    # Add pagination
    paginator = Paginator(items, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "items": page_obj,
        "days": days,
        "page_obj": page_obj,
    }

    return render(request, "inventory/expiring_items.html", context)


def low_stock_items(request):
    """View for items with low stock."""
    inventory_service = get_inventory_service()
    items = inventory_service.get_low_stock_items()

    # Add pagination
    paginator = Paginator(items, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "items": page_obj,
        "page_obj": page_obj,
    }

    return render(request, "inventory/low_stock_items.html", context)


def inventory_by_location(request, location):
    """View for inventory items filtered by storage location."""
    items = get_inventory_items_for_listing().filter(storage_location=location)

    # Add pagination
    paginator = Paginator(items, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get location display name
    location_display = dict(InventoryItem.STORAGE_CHOICES).get(location, location)

    context = {
        "items": page_obj,
        "location": location,
        "location_display": location_display,
        "page_obj": page_obj,
    }

    return render(request, "inventory/inventory_by_location.html", context)


def recent_receipts(request):
    """View for recent receipts."""
    receipts = get_receipts_for_listing().filter(status="completed")[:20]

    context = {
        "receipts": receipts,
    }

    return render(request, "inventory/recent_receipts.html", context)


class CategoryListView(ListView):
    """List view for categories."""

    model = Category
    template_name = "inventory/category_list.html"
    context_object_name = "categories"

    def get_queryset(self):
        return Category.objects.annotate(
            product_count=Count("products"),
            inventory_count=Count(
                "products__inventory_items",
                filter=Q(products__inventory_items__quantity_remaining__gt=0),
            ),
        ).order_by("name")


def upload_receipt(request):
    """Simple upload form for receipts."""
    # This is a placeholder - the actual upload functionality
    # is handled by the API endpoint
    return render(request, "inventory/upload_receipt.html")


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
            'receipt_json': JsonResponse(receipt_data).content.decode('utf-8'),
            'line_items_json': JsonResponse(line_items_data).content.decode('utf-8'),
            'all_products_json': JsonResponse(products_data).content.decode('utf-8'),
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
