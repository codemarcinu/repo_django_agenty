"""
Inventory app views implementing user interface for receipt processing pipeline.
Part of Prompt 8: Dashboard i widoki użytkownika.
"""

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.views.generic import ListView, DetailView, CreateView
from django.db.models import Q, Sum, Count, F
from django.contrib import messages
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import date, timedelta

from .models import (
    Product, Category, InventoryItem, Receipt, 
    ReceiptLineItem, ConsumptionEvent
)
from chatbot.services.inventory_service import get_inventory_service


def dashboard(request):
    """Main dashboard view with inventory summary and alerts."""
    inventory_service = get_inventory_service()
    
    # Get inventory summary
    summary = inventory_service.get_inventory_summary()
    
    # Get expiring items (next 7 days)
    expiring_items = inventory_service.get_expiring_items(days=7)[:5]
    
    # Get low stock items
    low_stock_items = inventory_service.get_low_stock_items()[:5]
    
    # Get recent receipts
    recent_receipts = Receipt.objects.filter(
        status='completed'
    ).order_by('-purchased_at')[:5]
    
    context = {
        'summary': summary,
        'expiring_items': expiring_items,
        'low_stock_items': low_stock_items,
        'recent_receipts': recent_receipts,
    }
    
    return render(request, 'inventory/dashboard.html', context)


class InventoryListView(ListView):
    """List view for inventory items with filtering and pagination."""
    model = InventoryItem
    template_name = 'inventory/inventory_list.html'
    context_object_name = 'items'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = InventoryItem.objects.select_related(
            'product', 'product__category'
        ).filter(
            quantity_remaining__gt=0
        ).order_by('-purchase_date')
        
        # Filter by search query
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(product__name__icontains=search) |
                Q(product__brand__icontains=search) |
                Q(product__category__name__icontains=search)
            )
        
        # Filter by location
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(storage_location=location)
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(product__category_id=category)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status == 'expiring':
            expiry_threshold = date.today() + timedelta(days=7)
            queryset = queryset.filter(expiry_date__lte=expiry_threshold)
        elif status == 'expired':
            queryset = queryset.filter(expiry_date__lt=date.today())
        elif status == 'low_stock':
            queryset = queryset.filter(
                quantity_remaining__lte=F('product__reorder_point')
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['categories'] = Category.objects.all().order_by('name')
        context['locations'] = InventoryItem.STORAGE_CHOICES
        
        # Add current filters
        context['current_search'] = self.request.GET.get('search', '')
        context['current_location'] = self.request.GET.get('location', '')
        context['current_category'] = self.request.GET.get('category', '')
        context['current_status'] = self.request.GET.get('status', '')
        
        return context


class ProductListView(ListView):
    """List view for products with filtering."""
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Product.objects.select_related('category').annotate(
            inventory_count=Count('inventoryitem', filter=Q(inventoryitem__quantity_remaining__gt=0)),
            total_quantity=Sum('inventoryitem__quantity_remaining', filter=Q(inventoryitem__quantity_remaining__gt=0))
        ).order_by('name')
        
        # Filter by search query
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(brand__icontains=search) |
                Q(category__name__icontains=search)
            )
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all().order_by('name')
        context['current_search'] = self.request.GET.get('search', '')
        context['current_category'] = self.request.GET.get('category', '')
        return context


class ProductDetailView(DetailView):
    """Detail view for a single product with inventory history."""
    model = Product
    template_name = 'inventory/product_detail.html'
    context_object_name = 'product'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        
        # Get current inventory items
        context['inventory_items'] = product.inventoryitem_set.filter(
            quantity_remaining__gt=0
        ).order_by('-purchase_date')
        
        # Get consumption history
        context['consumption_events'] = ConsumptionEvent.objects.filter(
            inventory_item__product=product
        ).select_related('inventory_item').order_by('-consumed_at')[:10]
        
        # Get receipt history
        context['receipt_items'] = ReceiptLineItem.objects.filter(
            matched_product=product
        ).select_related('receipt').order_by('-receipt__purchased_at')[:10]
        
        # Calculate statistics
        total_inventory = product.inventoryitem_set.filter(
            quantity_remaining__gt=0
        ).aggregate(
            total=Sum('quantity_remaining')
        )['total'] or 0
        
        context['total_inventory'] = total_inventory
        context['is_low_stock'] = total_inventory <= product.reorder_point
        
        return context


class ReceiptListView(ListView):
    """List view for receipts."""
    model = Receipt
    template_name = 'inventory/receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Receipt.objects.order_by('-purchased_at')
        
        # Filter by search query
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(store_name__icontains=search) |
                Q(processing_notes__icontains=search)
            )
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Receipt.STATUS_CHOICES
        context['current_search'] = self.request.GET.get('search', '')
        context['current_status'] = self.request.GET.get('status', '')
        return context


class ReceiptDetailView(DetailView):
    """Detail view for a single receipt."""
    model = Receipt
    template_name = 'inventory/receipt_detail.html'
    context_object_name = 'receipt'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        receipt = self.get_object()
        
        # Get line items
        context['line_items'] = receipt.line_items.select_related(
            'matched_product', 'matched_product__category'
        ).order_by('id')
        
        return context


def expiring_items(request):
    """View for items that are expiring soon."""
    days = request.GET.get('days', 7)
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 7
    
    inventory_service = get_inventory_service()
    items = inventory_service.get_expiring_items(days=days)
    
    # Add pagination
    paginator = Paginator(items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'items': page_obj,
        'days': days,
        'page_obj': page_obj,
    }
    
    return render(request, 'inventory/expiring_items.html', context)


def low_stock_items(request):
    """View for items with low stock."""
    inventory_service = get_inventory_service()
    items = inventory_service.get_low_stock_items()
    
    # Add pagination
    paginator = Paginator(items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'items': page_obj,
        'page_obj': page_obj,
    }
    
    return render(request, 'inventory/low_stock_items.html', context)


def inventory_by_location(request, location):
    """View for inventory items filtered by storage location."""
    items = InventoryItem.objects.filter(
        storage_location=location,
        quantity_remaining__gt=0
    ).select_related('product', 'product__category').order_by('-purchase_date')
    
    # Add pagination
    paginator = Paginator(items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get location display name
    location_display = dict(InventoryItem.STORAGE_CHOICES).get(location, location)
    
    context = {
        'items': page_obj,
        'location': location,
        'location_display': location_display,
        'page_obj': page_obj,
    }
    
    return render(request, 'inventory/inventory_by_location.html', context)


def recent_receipts(request):
    """View for recent receipts."""
    receipts = Receipt.objects.filter(
        status='completed'
    ).order_by('-purchased_at')[:20]
    
    context = {
        'receipts': receipts,
    }
    
    return render(request, 'inventory/recent_receipts.html', context)


class CategoryListView(ListView):
    """List view for categories."""
    model = Category
    template_name = 'inventory/category_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        return Category.objects.annotate(
            product_count=Count('product'),
            inventory_count=Count('product__inventoryitem', filter=Q(product__inventoryitem__quantity_remaining__gt=0))
        ).order_by('name')


def upload_receipt(request):
    """Simple upload form for receipts."""
    # This is a placeholder - the actual upload functionality
    # is handled by the API endpoint
    return render(request, 'inventory/upload_receipt.html')
