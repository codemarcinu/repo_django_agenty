"""
Optimized database queries for receipt processing system.
Implements query optimization from FAZA 5 of the plan.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional

from django.db.models import (
    Count, Sum, Avg, Q, F, Value, Case, When,
    Prefetch, OuterRef, Subquery, DecimalField, IntegerField
)
from django.db.models.functions import TruncDate, Coalesce
from django.utils import timezone

from inventory.models import (
    Receipt, ReceiptLineItem, Product, Category, 
    InventoryItem
)

logger = logging.getLogger(__name__)


class OptimizedReceiptService:
    """
    Optimized queries for receipt operations.
    Implements the database optimization strategy from FAZA 5.
    """

    def get_receipts_with_items(self, limit: int = 50):
        """
        Get receipts with optimized prefetching of related items.
        
        Args:
            limit: Maximum number of receipts to return
            
        Returns:
            Optimized QuerySet with prefetched relations
        """
        return Receipt.objects.prefetch_related(
            Prefetch(
                'line_items',
                queryset=ReceiptLineItem.objects.select_related(
                    'matched_product__category'
                ).order_by('id')
            )
        ).annotate(
            line_items_count=Count('line_items'),
            total_items_quantity=Coalesce(Sum('line_items__quantity'), 0, output_field=DecimalField())
        ).order_by('-created_at')[:limit]

    def get_inventory_summary(self):
        """
        Get inventory summary with single query and aggregation.
        
        Returns:
            QuerySet with aggregated inventory data
        """
        return InventoryItem.objects.select_related(
            'product__category'
        ).values(
            'product__name',
            'product__category__name'
        ).annotate(
            total_quantity=Sum('quantity_remaining'),
            item_count=Count('id'),
            last_updated=F('updated_at')
        ).filter(
            total_quantity__gt=0  # Only items in stock
        ).order_by('total_quantity')

    def get_recent_receipts_with_stats(self, days: int = 7):
        """
        Get recent receipts with processing statistics.
        
        Args:
            days: Number of days to look back
            
        Returns:
            QuerySet with processing time calculations
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return Receipt.objects.filter(
            created_at__gte=cutoff_date
        ).annotate(
            processing_duration=Case(
                When(
                    processed_at__isnull=False,
                    then=F('processed_at') - F('created_at')
                ),
                default=Value(None)
            ),
            items_count=Count('line_items'),
            is_recent=Case(
                When(
                    created_at__gte=timezone.now() - timedelta(hours=24),
                    then=Value(True)
                ),
                default=Value(False)
            )
        ).order_by('-created_at')

    def get_processing_analytics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive processing analytics with optimized queries.
        
        Args:
            days: Number of days for analysis
            
        Returns:
            Dictionary with analytics data
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Single query for basic stats
        basic_stats = Receipt.objects.filter(
            created_at__gte=cutoff_date
        ).aggregate(
            total_receipts=Count('id'),
            completed_receipts=Count('id', filter=Q(status='completed')),
            error_receipts=Count('id', filter=Q(status='error')),
            avg_processing_time=Avg(
                F('processed_at') - F('created_at'),
                filter=Q(processed_at__isnull=False)
            ),
            total_items_processed=Sum('line_items__quantity')
        )
        
        # Daily breakdown with single query
        daily_breakdown = Receipt.objects.filter(
            created_at__gte=cutoff_date
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            receipts_count=Count('id'),
            completed_count=Count('id', filter=Q(status='completed')),
            error_count=Count('id', filter=Q(status='error')),
            avg_items=Avg('line_items__quantity')
        ).order_by('day')
        
        # Top categories by receipt frequency
        top_categories = Category.objects.annotate(
            receipt_count=Count(
                'products__receipt_items__receipt',
                filter=Q(
                    products__receipt_items__receipt__created_at__gte=cutoff_date
                )
            )
        ).filter(
            receipt_count__gt=0
        ).order_by('-receipt_count')[:10]
        
        # Calculate success rate
        success_rate = 0
        if basic_stats['total_receipts'] > 0:
            success_rate = (basic_stats['completed_receipts'] / basic_stats['total_receipts']) * 100
        
        return {
            'summary': {
                'total_receipts': basic_stats['total_receipts'],
                'success_rate': success_rate,
                'error_rate': (basic_stats['error_receipts'] / basic_stats['total_receipts'] * 100) if basic_stats['total_receipts'] > 0 else 0,
                'avg_processing_time_seconds': basic_stats['avg_processing_time'].total_seconds() if basic_stats['avg_processing_time'] else None,
                'total_items_processed': basic_stats['total_items_processed'] or 0
            },
            'daily_breakdown': list(daily_breakdown),
            'top_categories': [
                {
                    'name': cat.name,
                    'receipt_count': cat.receipt_count
                }
                for cat in top_categories
            ],
            'period_days': days,
            'generated_at': timezone.now().isoformat()
        }

    def get_problematic_receipts(self, days: int = 7):
        """
        Get receipts with processing issues using optimized queries.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            QuerySet of receipts with issues
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return Receipt.objects.filter(
            Q(created_at__gte=cutoff_date) &
            (
                Q(status='error') |  # Failed receipts
                Q(  # Stuck in processing for too long
                    status__in=['processing_ocr', 'ocr_in_progress', 'processing_parsing'],
                    created_at__lt=timezone.now() - timedelta(hours=2)
                ) |
                Q(  # Low confidence OCR results
                    raw_text__confidence__lt=0.7
                )
            )
        ).annotate(
            processing_time=F('updated_at') - F('created_at'),
            issue_type=Case(
                When(status='error', then=Value('processing_error')),
                When(
                    status__in=['processing_ocr', 'ocr_in_progress'],
                    then=Value('stuck_in_ocr')
                ),
                When(
                    status='processing_parsing',
                    then=Value('stuck_in_parsing')
                ),
                default=Value('unknown')
            )
        ).order_by('-created_at')

    def get_high_value_receipts(self, min_amount: Decimal = Decimal('100.00')):
        """
        Get high-value receipts with optimized queries.
        
        Args:
            min_amount: Minimum receipt total
            
        Returns:
            QuerySet of high-value receipts
        """
        return Receipt.objects.filter(
            total__gte=min_amount,
            status='completed'
        ).prefetch_related(
            'line_items__matched_product'
        ).annotate(
            items_count=Count('line_items'),
            unique_products=Count('line_items__matched_product', distinct=True)
        ).order_by('-total')


class OptimizedInventoryService:
    """
    Optimized queries for inventory operations.
    """

    def get_low_stock_items(self, threshold_days: int = 7):
        """
        Get items that are running low or expiring soon.
        
        Args:
            threshold_days: Days threshold for expiry warning
            
        Returns:
            QuerySet of items needing attention
        """
        from django.utils import timezone
        from datetime import timedelta
        
        threshold_date = timezone.now().date() + timedelta(days=threshold_days)
        
        return InventoryItem.objects.filter(
            Q(quantity_remaining__lte=F('product__reorder_point')) |
            Q(expiry_date__lte=threshold_date, expiry_date__gt=timezone.now().date())
        ).select_related(
            'product__category'
        ).annotate(
            issue_type=Case(
                When(
                    quantity_remaining__lte=F('product__reorder_point'),
                    then=Value('low_stock')
                ),
                When(
                    expiry_date__lte=threshold_date,
                    then=Value('expiring_soon')
                ),
                default=Value('ok')
            ),
            stock_level_percent=Case(
                When(
                    product__reorder_point__gt=0,
                    then=F('quantity_remaining') * 100 / F('product__reorder_point')
                ),
                default=Value(100),
                output_field=DecimalField()
            )
        ).order_by('expiry_date', 'quantity_remaining')

    def get_category_consumption_stats(self, days: int = 30):
        """
        Get consumption statistics by category.
        
        Args:
            days: Analysis period in days
            
        Returns:
            QuerySet with category consumption data
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return Category.objects.annotate(
            total_consumed=Sum(
                'products__inventoryitem__quantity_consumed',
                filter=Q(
                    products__inventoryitem__updated_at__gte=cutoff_date
                )
            ),
            items_count=Count(
                'products__inventoryitem',
                filter=Q(
                    products__inventoryitem__quantity_remaining__gt=0
                )
            ),
            # Removed avg_expiry_days as days_until_expiry field doesn't exist
            last_purchase=Subquery(
                Receipt.objects.filter(
                    line_items__matched_product__category=OuterRef('pk'),
                    status='completed'
                ).order_by('-created_at').values('created_at')[:1]
            )
        ).filter(
            total_consumed__isnull=False
        ).order_by('-total_consumed')


# Convenience functions for easy access as specified in Prompt 4
def get_receipts_for_listing():
    """
    Get receipts for listing with optimized prefetch_related.
    Eliminates N+1 problem by prefetching line_items and matched_products.
    """
    return Receipt.objects.prefetch_related(
        'line_items__matched_product__category'
    ).order_by('-purchased_at')


def get_inventory_items_for_listing():
    """
    Get inventory items for listing with optimized select_related.
    Eliminates N+1 problem by selecting product and category in single query.
    """
    return InventoryItem.objects.select_related(
        'product__category'
    ).filter(quantity_remaining__gt=0).order_by('-purchase_date')


def get_product_details(product_id: int):
    """
    Get a single product with all related data prefetched for detail view.
    """
    return Product.objects.prefetch_related(
        Prefetch('inventory_items', queryset=InventoryItem.objects.filter(quantity_remaining__gt=0).order_by('-purchase_date')),
        Prefetch('receipt_items', queryset=ReceiptLineItem.objects.select_related('receipt').order_by('-receipt__purchased_at')),
        Prefetch('inventory_items__consumption_events', queryset=ConsumptionEvent.objects.order_by('-consumed_at'))
    ).get(id=product_id)


def get_optimized_receipt_service() -> OptimizedReceiptService:
    """Get optimized receipt service instance."""
    return OptimizedReceiptService()


def get_optimized_inventory_service() -> OptimizedInventoryService:
    """Get optimized inventory service instance."""
    return OptimizedInventoryService()


# Performance monitoring decorators
def monitor_query_performance(func):
    """Decorator to monitor query performance."""
    def wrapper(*args, **kwargs):
        import time
        from django.db import connection
        
        start_time = time.time()
        initial_queries = len(connection.queries)
        
        result = func(*args, **kwargs)
        
        end_time = time.time()
        final_queries = len(connection.queries)
        
        duration = end_time - start_time
        query_count = final_queries - initial_queries
        
        logger.info(
            f"Query performance - Function: {func.__name__}, "
            f"Duration: {duration:.3f}s, Queries: {query_count}"
        )
        
        # Alert on slow queries
        if duration > 1.0 or query_count > 10:
            logger.warning(
                f"Slow query detected - {func.__name__}: {duration:.3f}s, {query_count} queries"
            )
        
        return result
    return wrapper


# Usage examples for testing
@monitor_query_performance
def get_dashboard_data():
    """Example of optimized dashboard data retrieval."""
    receipt_service = get_optimized_receipt_service()
    inventory_service = get_optimized_inventory_service()
    
    return {
        'recent_receipts': list(receipt_service.get_recent_receipts_with_stats()),
        'inventory_summary': list(receipt_service.get_inventory_summary()),
        'low_stock_items': list(inventory_service.get_low_stock_items()),
        'analytics': receipt_service.get_processing_analytics(days=7)
    }