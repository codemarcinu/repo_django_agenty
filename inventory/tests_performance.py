"""
Performance tests for dashboard - Prompt 10: Panel przeglądu (dashboard) - rozszerzenie.
Tests to ensure dashboard response time is under 150ms.
"""

import time
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.test.utils import override_settings
from django.core.cache import cache

from inventory.models import (
    Product, Category, InventoryItem, Receipt, 
    ReceiptLineItem, ConsumptionEvent
)
from chatbot.services.inventory_service import get_inventory_service


class DashboardPerformanceTest(TestCase):
    """Performance tests for dashboard views"""
    
    def setUp(self):
        """Set up performance test data with realistic volume"""
        self.client = Client()
        
        # Create test categories
        self.categories = []
        for i in range(10):
            category = Category.objects.create(
                name=f"Category {i}",
                meta={'default_expiry_days': 7 + (i * 3)}
            )
            self.categories.append(category)
        
        # Create test products (100 products)
        self.products = []
        for i in range(100):
            product = Product.objects.create(
                name=f"Product {i}",
                brand=f"Brand {i % 5}",
                category=self.categories[i % 10],
                reorder_point=Decimal(str(2 + (i % 5)))
            )
            self.products.append(product)
        
        # Create test receipts (50 receipts)
        self.receipts = []
        for i in range(50):
            receipt = Receipt.objects.create(
                store_name=f"Store {i % 5}",
                purchased_at=date.today() - timedelta(days=i),
                total=Decimal(str(20 + (i * 5))),
                currency='PLN',
                status='completed'
            )
            self.receipts.append(receipt)
            
            # Create line items for each receipt (3-8 items per receipt)
            items_count = 3 + (i % 6)
            for j in range(items_count):
                ReceiptLineItem.objects.create(
                    receipt=receipt,
                    product_name=f"Product {j} from receipt {i}",
                    quantity=Decimal(str(1 + (j % 3))),
                    unit_price=Decimal(str(5.99 + j)),
                    line_total=Decimal(str((1 + (j % 3)) * (5.99 + j))),
                    matched_product=self.products[(i * j) % 100]
                )
        
        # Create inventory items (300 items)
        for i in range(300):
            expiry_offset = 1 + (i % 30)  # Some expired, some expiring, some fresh
            if i < 50:
                # Expired items
                expiry_date = date.today() - timedelta(days=expiry_offset)
            elif i < 100:
                # Expiring soon
                expiry_date = date.today() + timedelta(days=expiry_offset % 5)
            else:
                # Fresh items
                expiry_date = date.today() + timedelta(days=10 + expiry_offset)
                
            InventoryItem.objects.create(
                product=self.products[i % 100],
                purchase_date=date.today() - timedelta(days=10 + (i % 20)),
                expiry_date=expiry_date,
                quantity_remaining=Decimal(str(1 + (i % 10))),
                unit='szt',
                storage_location=['fridge', 'freezer', 'pantry', 'cabinet'][i % 4]
            )
        
        # Create consumption events (200 events)
        inventory_items = list(InventoryItem.objects.all()[:200])
        for i, item in enumerate(inventory_items):
            ConsumptionEvent.objects.create(
                inventory_item=item,
                consumed_qty=Decimal('0.5'),
                consumed_at=date.today() - timedelta(days=i % 30),
                notes=f"Consumption event {i}"
            )
        
    def test_dashboard_response_time(self):
        """Test that dashboard loads within 150ms target"""
        url = reverse('inventory:dashboard')
        
        # Clear cache to ensure fresh queries
        cache.clear()
        
        start_time = time.time()
        response = self.client.get(url)
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(
            response_time_ms, 
            150, 
            f"Dashboard response time {response_time_ms:.1f}ms exceeds 150ms target"
        )
        
        print(f"Dashboard response time: {response_time_ms:.1f}ms")
        
    def test_dashboard_with_cache_response_time(self):
        """Test that dashboard loads faster with cache"""
        url = reverse('inventory:dashboard')
        
        # First request to warm up cache
        self.client.get(url)
        
        # Second request should be faster
        start_time = time.time()
        response = self.client.get(url)
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(
            response_time_ms, 
            100, 
            f"Cached dashboard response time {response_time_ms:.1f}ms exceeds 100ms target"
        )
        
        print(f"Cached dashboard response time: {response_time_ms:.1f}ms")
        
    def test_inventory_service_methods_performance(self):
        """Test individual InventoryService methods performance"""
        inventory_service = get_inventory_service()
        
        methods_to_test = [
            ('get_inventory_summary', {}),
            ('get_expiring_items', {'days': 7}),
            ('get_low_stock_items', {}),
            ('get_top_spending_categories', {'days': 30}),
            ('get_consumption_heatmap_data', {'days': 30}),
            ('get_recent_activity', {'days': 7}),
        ]
        
        for method_name, kwargs in methods_to_test:
            with self.subTest(method=method_name):
                method = getattr(inventory_service, method_name)
                
                start_time = time.time()
                result = method(**kwargs)
                end_time = time.time()
                
                response_time_ms = (end_time - start_time) * 1000
                
                # Each method should complete in under 50ms
                self.assertLess(
                    response_time_ms, 
                    50, 
                    f"{method_name} took {response_time_ms:.1f}ms, exceeds 50ms target"
                )
                
                # Ensure method returns data
                self.assertIsNotNone(result)
                
                print(f"{method_name}: {response_time_ms:.1f}ms")
                
    def test_query_optimization(self):
        """Test that database queries are optimized"""
        from django.test.utils import override_settings
        from django.db import connection
        
        # Enable query logging
        with override_settings(DEBUG=True):
            url = reverse('inventory:dashboard')
            
            # Reset query log
            connection.queries_log.clear()
            
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, 200)
            
            # Check number of queries
            query_count = len(connection.queries)
            
            print(f"Dashboard generated {query_count} database queries")
            
            # Should not have excessive queries (target: under 25)
            self.assertLess(
                query_count, 
                25, 
                f"Dashboard made {query_count} queries, target is under 25"
            )
            
            # Print slow queries for debugging
            slow_queries = [
                (i, float(q['time'])) 
                for i, q in enumerate(connection.queries) 
                if float(q['time']) > 0.01
            ]
            
            if slow_queries:
                print("Slow queries (>10ms):")
                for i, time_taken in slow_queries[:5]:  # Show top 5
                    print(f"  Query {i}: {time_taken*1000:.1f}ms")
                    print(f"    SQL: {connection.queries[i]['sql'][:100]}...")
    
    @override_settings(DEBUG=True)            
    def test_large_dataset_performance(self):
        """Test dashboard performance with larger dataset"""
        # Add more data
        additional_categories = []
        for i in range(10, 25):  # Add 15 more categories
            category = Category.objects.create(name=f"Large Category {i}")
            additional_categories.append(category)
        
        # Add 200 more products
        additional_products = []
        for i in range(100, 300):
            product = Product.objects.create(
                name=f"Large Product {i}",
                category=additional_categories[(i - 100) % 15],
                reorder_point=Decimal('3.0')
            )
            additional_products.append(product)
        
        # Add 500 more inventory items
        for i in range(300, 800):
            InventoryItem.objects.create(
                product=additional_products[(i - 300) % 200],
                purchase_date=date.today() - timedelta(days=(i % 60)),
                expiry_date=date.today() + timedelta(days=(i % 45)),
                quantity_remaining=Decimal(str(1 + (i % 8))),
                unit='szt',
                storage_location=['fridge', 'freezer', 'pantry', 'cabinet'][i % 4]
            )
        
        print(f"Testing with {Product.objects.count()} products, {InventoryItem.objects.count()} inventory items")
        
        url = reverse('inventory:dashboard')
        
        start_time = time.time()
        response = self.client.get(url)
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        self.assertEqual(response.status_code, 200)
        
        # More lenient target for large dataset (250ms)
        self.assertLess(
            response_time_ms, 
            250, 
            f"Large dataset dashboard response time {response_time_ms:.1f}ms exceeds 250ms target"
        )
        
        print(f"Large dataset dashboard response time: {response_time_ms:.1f}ms")


class InventoryListPerformanceTest(TestCase):
    """Performance tests for inventory list view"""
    
    def setUp(self):
        """Set up test data for list view performance"""
        self.client = Client()
        
        # Create category
        self.category = Category.objects.create(name="Test Category")
        
        # Create products
        self.products = []
        for i in range(50):
            product = Product.objects.create(
                name=f"Product {i}",
                category=self.category,
                reorder_point=Decimal('2.0')
            )
            self.products.append(product)
        
        # Create many inventory items for pagination testing
        for i in range(200):
            InventoryItem.objects.create(
                product=self.products[i % 50],
                purchase_date=date.today() - timedelta(days=(i % 30)),
                expiry_date=date.today() + timedelta(days=(i % 60)),
                quantity_remaining=Decimal(str(1 + (i % 10))),
                unit='szt',
                storage_location='pantry'
            )
    
    def test_inventory_list_response_time(self):
        """Test inventory list view performance"""
        url = reverse('inventory:inventory_list')
        
        start_time = time.time()
        response = self.client.get(url)
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(
            response_time_ms, 
            100, 
            f"Inventory list response time {response_time_ms:.1f}ms exceeds 100ms target"
        )
        
        print(f"Inventory list response time: {response_time_ms:.1f}ms")
        
    def test_inventory_list_with_filters_performance(self):
        """Test inventory list with filters performance"""
        url = reverse('inventory:inventory_list')
        params = {
            'search': 'Product',
            'location': 'pantry',
            'status': 'low_stock'
        }
        
        start_time = time.time()
        response = self.client.get(url, params)
        end_time = time.time()
        
        response_time_ms = (end_time - start_time) * 1000
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(
            response_time_ms, 
            100, 
            f"Filtered inventory list response time {response_time_ms:.1f}ms exceeds 100ms target"
        )
        
        print(f"Filtered inventory list response time: {response_time_ms:.1f}ms")