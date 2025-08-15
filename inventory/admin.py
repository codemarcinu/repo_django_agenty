"""
Django admin configuration for inventory models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from decimal import Decimal

from .models import (
    Category, Product, Receipt, ReceiptLineItem, 
    InventoryItem, ConsumptionEvent
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Category model."""
    
    list_display = ['name', 'parent', 'get_full_path', 'get_products_count', 'created_at']
    list_filter = ['parent', 'created_at']
    search_fields = ['name']
    ordering = ['name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'parent')
        }),
        ('Metadata', {
            'fields': ('meta',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_products_count(self, obj):
        """Get count of products in this category."""
        return obj.products.count()
    get_products_count.short_description = 'Products'
    
    def get_full_path(self, obj):
        """Display full category path."""
        return obj.get_full_path()
    get_full_path.short_description = 'Full Path'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin interface for Product model."""
    
    list_display = [
        'name', 'brand', 'barcode', 'category', 
        'is_active', 'reorder_point', 'get_inventory_count'
    ]
    list_filter = ['is_active', 'category', 'created_at']
    search_fields = ['name', 'brand', 'barcode']
    ordering = ['name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'brand', 'barcode', 'category', 'is_active')
        }),
        ('Inventory Settings', {
            'fields': ('reorder_point',)
        }),
        ('Data', {
            'fields': ('nutrition', 'aliases'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = []
    
    def get_inventory_count(self, obj):
        """Get count of inventory items for this product."""
        return obj.inventory_items.count()
    get_inventory_count.short_description = 'Inventory Items'


class ReceiptLineItemInline(admin.TabularInline):
    """Inline admin for receipt line items."""
    
    model = ReceiptLineItem
    extra = 0
    fields = [
        'product_name', 'quantity', 'unit_price', 'line_total', 
        'vat_code', 'matched_product'
    ]
    readonly_fields = ['line_total']
    
    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly after creation."""
        if obj:  # Editing existing object
            return self.readonly_fields + ['product_name', 'quantity', 'unit_price']
        return self.readonly_fields


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    """Admin interface for Receipt model."""
    
    list_display = [
        'id', 'store_name', 'purchased_at', 'total', 'currency', 
        'status', 'get_items_count', 'created_at'
    ]
    list_filter = ['status', 'currency', 'store_name', 'purchased_at', 'created_at']
    search_fields = ['store_name', 'source_file_path']
    ordering = ['-purchased_at']
    date_hierarchy = 'purchased_at'
    
    fieldsets = (
        (None, {
            'fields': ('store_name', 'purchased_at', 'total', 'currency', 'status')
        }),
        ('Processing', {
            'fields': ('source_file_path', 'processing_notes'),
        }),
        ('OCR Data', {
            'fields': ('raw_text',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ReceiptLineItemInline]
    
    def get_items_count(self, obj):
        """Get count of line items in receipt."""
        return obj.line_items.count()
    get_items_count.short_description = 'Items'
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly after creation."""
        readonly = list(self.readonly_fields)
        if obj and obj.status in ['completed', 'error']:
            readonly.extend(['total', 'currency', 'purchased_at'])
        return readonly


@admin.register(ReceiptLineItem)
class ReceiptLineItemAdmin(admin.ModelAdmin):
    """Admin interface for ReceiptLineItem model."""
    
    list_display = [
        'get_receipt_info', 'product_name', 'quantity', 'unit_price', 
        'line_total', 'vat_code', 'matched_product', 'get_validation_status'
    ]
    list_filter = ['vat_code', 'matched_product__isnull', 'receipt__status']
    search_fields = ['product_name', 'receipt__store_name']
    ordering = ['-receipt__purchased_at', 'product_name']
    
    fieldsets = (
        (None, {
            'fields': ('receipt', 'product_name', 'matched_product')
        }),
        ('Quantities & Prices', {
            'fields': ('quantity', 'unit_price', 'line_total', 'vat_code')
        }),
        ('Metadata', {
            'fields': ('meta',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_receipt_info(self, obj):
        """Display receipt information."""
        url = reverse('admin:inventory_receipt_change', args=[obj.receipt.id])
        return format_html(
            '<a href="{}">{} - {}</a>',
            url, obj.receipt.store_name, obj.receipt.purchased_at.date()
        )
    get_receipt_info.short_description = 'Receipt'
    
    def get_validation_status(self, obj):
        """Show validation status of line total."""
        if obj.validate_line_total():
            return format_html('<span style="color: green;">✓ Valid</span>')
        else:
            return format_html('<span style="color: red;">✗ Invalid</span>')
    get_validation_status.short_description = 'Validation'


class ConsumptionEventInline(admin.TabularInline):
    """Inline admin for consumption events."""
    
    model = ConsumptionEvent
    extra = 0
    fields = ['consumed_qty', 'consumed_at', 'notes']
    readonly_fields = ['consumed_at']
    ordering = ['-consumed_at']


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    """Admin interface for InventoryItem model."""
    
    list_display = [
        'get_product_name', 'purchase_date', 'expiry_date', 
        'quantity_remaining', 'unit', 'storage_location', 
        'get_status_indicators', 'updated_at'
    ]
    list_filter = [
        'unit', 'storage_location', 'purchase_date', 'expiry_date',
        'product__category'
    ]
    search_fields = ['product__name', 'product__brand', 'batch_id']
    ordering = ['expiry_date', 'product__name']
    date_hierarchy = 'purchase_date'
    
    fieldsets = (
        (None, {
            'fields': ('product', 'purchase_date', 'expiry_date')
        }),
        ('Quantity & Storage', {
            'fields': ('quantity_remaining', 'unit', 'storage_location', 'batch_id')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ConsumptionEventInline]
    
    def get_product_name(self, obj):
        """Display product name with link."""
        url = reverse('admin:inventory_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    get_product_name.short_description = 'Product'
    
    def get_status_indicators(self, obj):
        """Show status indicators for inventory item."""
        indicators = []
        
        if obj.is_expired():
            indicators.append('<span style="color: red;">🚫 Expired</span>')
        elif obj.is_expiring_soon():
            indicators.append('<span style="color: orange;">⚠️ Expiring Soon</span>')
        
        if obj.is_low_stock():
            indicators.append('<span style="color: red;">📉 Low Stock</span>')
        
        if not indicators:
            indicators.append('<span style="color: green;">✓ OK</span>')
        
        return format_html(' '.join(indicators))
    get_status_indicators.short_description = 'Status'
    
    def get_queryset(self, request):
        """Optimize queries."""
        return super().get_queryset(request).select_related('product', 'product__category')


@admin.register(ConsumptionEvent)
class ConsumptionEventAdmin(admin.ModelAdmin):
    """Admin interface for ConsumptionEvent model."""
    
    list_display = [
        'get_product_name', 'consumed_qty', 'consumed_at', 
        'get_inventory_item_info', 'notes'
    ]
    list_filter = ['consumed_at', 'inventory_item__product__category']
    search_fields = [
        'inventory_item__product__name', 'notes',
        'inventory_item__product__brand'
    ]
    ordering = ['-consumed_at']
    date_hierarchy = 'consumed_at'
    
    fieldsets = (
        (None, {
            'fields': ('inventory_item', 'consumed_qty', 'consumed_at', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at']
    
    def get_product_name(self, obj):
        """Display product name."""
        return obj.inventory_item.product.name
    get_product_name.short_description = 'Product'
    
    def get_inventory_item_info(self, obj):
        """Display inventory item information."""
        url = reverse('admin:inventory_inventoryitem_change', 
                     args=[obj.inventory_item.id])
        return format_html(
            '<a href="{}">{} ({}{})</a>',
            url, 
            obj.inventory_item.product.name,
            obj.inventory_item.quantity_remaining,
            obj.inventory_item.unit
        )
    get_inventory_item_info.short_description = 'Inventory Item'
    
    def get_queryset(self, request):
        """Optimize queries."""
        return super().get_queryset(request).select_related(
            'inventory_item', 'inventory_item__product'
        )


# Customize admin site
admin.site.site_header = "Inventory Management System"
admin.site.site_title = "Inventory Admin"
admin.site.index_title = "Receipt Processing Pipeline Administration"
