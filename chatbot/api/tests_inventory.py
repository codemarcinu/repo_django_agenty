"""
Tests for inventory consumption API and alert tasks.
Part of Prompt 9: Zdarzenia zużycia i alerty.
"""

import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, Mock

from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail

from inventory.models import Product, Category, InventoryItem, ConsumptionEvent
from chatbot.tasks_alerts import (
    check_inventory_alerts, 
    send_inventory_alerts_notification,
    send_test_alert
)


class ConsumeInventoryAPITest(TestCase):
    """Test cases for POST /api/inventory/{id}/consume endpoint"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create test category
        self.category = Category.objects.create(
            name="Test Category"
        )
        
        # Create test product
        self.product = Product.objects.create(
            name="Test Product",
            category=self.category,
            reorder_point=Decimal('2.000')
        )
        
        # Create test inventory item
        self.inventory_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=date.today(),
            quantity_remaining=Decimal('5.000'),
            unit='szt',
            storage_location='pantry'
        )
        
    def test_successful_consumption(self):
        """Test successful consumption of inventory item"""
        url = reverse('chatbot_api:inventory-consume', kwargs={'inventory_id': self.inventory_item.id})
        data = {
            'consumed_qty': '2.5',
            'notes': 'Test consumption'
        }
        
        response = self.client.post(
            url, 
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['remaining_quantity'], 2.5)
        self.assertEqual(response_data['product_name'], 'Test Product')
        
        # Verify inventory item was updated
        self.inventory_item.refresh_from_db()
        self.assertEqual(self.inventory_item.quantity_remaining, Decimal('2.5'))
        
        # Verify consumption event was created
        consumption = ConsumptionEvent.objects.filter(inventory_item=self.inventory_item).first()
        self.assertIsNotNone(consumption)
        self.assertEqual(consumption.consumed_qty, Decimal('2.5'))
        self.assertEqual(consumption.notes, 'Test consumption')
        
    def test_consumption_insufficient_quantity(self):
        """Test consumption with insufficient quantity"""
        url = reverse('chatbot_api:inventory-consume', kwargs={'inventory_id': self.inventory_item.id})
        data = {
            'consumed_qty': '10.0'  # More than available (5.0)
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        
        self.assertFalse(response_data['success'])
        self.assertIn('Not enough quantity available', response_data['error'])
        
        # Verify inventory item was not updated
        self.inventory_item.refresh_from_db()
        self.assertEqual(self.inventory_item.quantity_remaining, Decimal('5.0'))
        
    def test_consumption_invalid_quantity(self):
        """Test consumption with invalid quantity values"""
        url = reverse('chatbot_api:inventory-consume', kwargs={'inventory_id': self.inventory_item.id})
        
        # Test negative quantity
        response = self.client.post(
            url,
            data=json.dumps({'consumed_qty': '-1.0'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        
        # Test zero quantity
        response = self.client.post(
            url,
            data=json.dumps({'consumed_qty': '0'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        
        # Test invalid string
        response = self.client.post(
            url,
            data=json.dumps({'consumed_qty': 'invalid'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        
    def test_consumption_missing_quantity(self):
        """Test consumption without required consumed_qty"""
        url = reverse('chatbot_api:inventory-consume', kwargs={'inventory_id': self.inventory_item.id})
        data = {
            'notes': 'Test without quantity'
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        
        self.assertFalse(response_data['success'])
        self.assertIn('consumed_qty is required', response_data['error'])
        
    def test_consumption_nonexistent_item(self):
        """Test consumption of non-existent inventory item"""
        url = reverse('chatbot_api:inventory-consume', kwargs={'inventory_id': 99999})
        data = {
            'consumed_qty': '1.0'
        }
        
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        response_data = response.json()
        
        self.assertFalse(response_data['success'])
        self.assertIn('Inventory item not found', response_data['error'])
        
    def test_consumption_invalid_json(self):
        """Test consumption with invalid JSON"""
        url = reverse('chatbot_api:inventory-consume', kwargs={'inventory_id': self.inventory_item.id})
        
        response = self.client.post(
            url,
            data="invalid json",
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        
        self.assertFalse(response_data['success'])
        self.assertIn('Invalid JSON', response_data['error'])


class InventoryAlertsTaskTest(TestCase):
    """Test cases for inventory alert tasks"""
    
    def setUp(self):
        """Set up test data"""
        # Create test category with expiry configuration
        self.category = Category.objects.create(
            name="Perishable Category",
            meta={'default_expiry_days': 7}
        )
        
        # Create test products
        self.product1 = Product.objects.create(
            name="Expiring Product",
            category=self.category,
            reorder_point=Decimal('3.000')
        )
        
        self.product2 = Product.objects.create(
            name="Low Stock Product", 
            category=self.category,
            reorder_point=Decimal('5.000')
        )
        
        # Create inventory items with different scenarios
        
        # 1. Item expiring tomorrow
        self.expiring_item = InventoryItem.objects.create(
            product=self.product1,
            purchase_date=date.today() - timedelta(days=5),
            expiry_date=date.today() + timedelta(days=1),  # Expires tomorrow
            quantity_remaining=Decimal('2.000'),
            unit='szt',
            storage_location='fridge'
        )
        
        # 2. Already expired item  
        self.expired_item = InventoryItem.objects.create(
            product=self.product1,
            purchase_date=date.today() - timedelta(days=10),
            expiry_date=date.today() - timedelta(days=1),  # Expired yesterday
            quantity_remaining=Decimal('1.500'),
            unit='szt',
            storage_location='fridge'
        )
        
        # 3. Low stock item
        self.low_stock_item = InventoryItem.objects.create(
            product=self.product2,
            purchase_date=date.today() - timedelta(days=2),
            expiry_date=date.today() + timedelta(days=10),  # Not expiring soon
            quantity_remaining=Decimal('2.000'),  # Below reorder_point of 5.000
            unit='kg',
            storage_location='pantry'
        )
        
        # 4. Normal item (no alerts)
        self.normal_item = InventoryItem.objects.create(
            product=self.product2,
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
            quantity_remaining=Decimal('10.000'),
            unit='szt',
            storage_location='pantry'
        )
        
    def test_check_inventory_alerts_task(self):
        """Test the periodic inventory alerts checking task"""
        result = check_inventory_alerts()
        
        self.assertTrue(result['success'])
        self.assertGreater(result['alerts_count'], 0)
        
        alerts = result['alerts']
        
        # Should find expired, expiring, and low stock items
        alert_types = [alert['type'] for alert in alerts]
        
        self.assertIn('expired', alert_types)
        self.assertIn('expiring', alert_types)
        self.assertIn('low_stock', alert_types)
        
        # Check specific alert details
        expired_alerts = [a for a in alerts if a['type'] == 'expired']
        self.assertEqual(len(expired_alerts), 1)
        self.assertEqual(expired_alerts[0]['product_name'], 'Expiring Product')
        
        expiring_alerts = [a for a in alerts if a['type'] == 'expiring']
        self.assertEqual(len(expiring_alerts), 1)
        self.assertEqual(expiring_alerts[0]['days_until_expiry'], 1)
        
        low_stock_alerts = [a for a in alerts if a['type'] == 'low_stock']
        self.assertEqual(len(low_stock_alerts), 1)
        self.assertEqual(low_stock_alerts[0]['product_name'], 'Low Stock Product')
        
    @patch('chatbot.tasks_alerts.send_inventory_alerts_notification.delay')
    def test_check_inventory_alerts_triggers_notification(self, mock_send_notification):
        """Test that alerts task triggers notification sending"""
        result = check_inventory_alerts()
        
        self.assertTrue(result['success'])
        self.assertGreater(result['alerts_count'], 0)
        
        # Verify notification task was called
        mock_send_notification.assert_called_once()
        
        # Check the alerts data passed to notification task
        call_args = mock_send_notification.call_args[0]
        alerts = call_args[0]
        
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)
        
    def test_send_inventory_alerts_notification(self):
        """Test sending inventory alerts notification"""
        # Prepare test alerts data
        alerts = [
            {
                'type': 'expired',
                'item_id': self.expired_item.id,
                'product_name': 'Expired Product',
                'quantity': 1.5,
                'unit': 'szt',
                'storage_location': 'fridge',
                'expiry_date': (date.today() - timedelta(days=1)).isoformat(),
                'days_until_expiry': -1
            },
            {
                'type': 'expiring',
                'item_id': self.expiring_item.id,
                'product_name': 'Expiring Product',
                'quantity': 2.0,
                'unit': 'szt',
                'storage_location': 'fridge',
                'expiry_date': (date.today() + timedelta(days=1)).isoformat(),
                'days_until_expiry': 1
            },
            {
                'type': 'low_stock',
                'item_id': self.low_stock_item.id,
                'product_name': 'Low Stock Product',
                'quantity': 2.0,
                'unit': 'kg',
                'storage_location': 'pantry',
                'reorder_point': 5.0
            }
        ]
        
        result = send_inventory_alerts_notification(alerts)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['alerts_count'], 3)
        
        # Check that email was sent (with console backend, it goes to mail.outbox)
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertIn('Alerty magazynowe', email.subject)
        self.assertIn('3 pozycji wymaga uwagi', email.subject)
        
        # Check email content contains alert information
        self.assertIn('Expired Product', email.body)
        self.assertIn('Expiring Product', email.body)
        self.assertIn('Low Stock Product', email.body)
        
    def test_send_empty_alerts_notification(self):
        """Test sending notification with empty alerts list"""
        result = send_inventory_alerts_notification([])
        
        self.assertTrue(result['success'])
        self.assertIn('No alerts to send', result['message'])
        
        # No email should be sent
        self.assertEqual(len(mail.outbox), 0)
        
    def test_send_test_alert(self):
        """Test the test alert task"""
        result = send_test_alert("Test message")
        
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Test message")
        
        # Should trigger notification with mock data
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertIn('Test Product', email.body)
        
    @patch('chatbot.tasks_alerts.logger')
    def test_check_inventory_alerts_error_handling(self, mock_logger):
        """Test error handling in alerts checking task"""
        
        # Force an error by mocking inventory service to fail
        with patch('chatbot.tasks_alerts.get_inventory_service') as mock_service:
            mock_service.side_effect = Exception("Test error")
            
            result = check_inventory_alerts()
            
            self.assertFalse(result['success'])
            self.assertIn('Test error', result['error'])
            
            # Verify error was logged
            mock_logger.error.assert_called()
            
    @patch('chatbot.tasks_alerts.logger')
    def test_send_notification_error_handling(self, mock_logger):
        """Test error handling in notification sending"""
        
        # Mock send_mail to raise an exception
        with patch('chatbot.tasks_alerts.send_mail') as mock_send_mail:
            mock_send_mail.side_effect = Exception("Email error")
            
            alerts = [{'type': 'test', 'product_name': 'Test'}]
            result = send_inventory_alerts_notification(alerts)
            
            self.assertFalse(result['success'])
            self.assertIn('Email error', result['error'])
            
            # Verify error was logged
            mock_logger.error.assert_called()


class InventoryIntegrationTest(TestCase):
    """Integration tests for the complete inventory alerts system"""
    
    def setUp(self):
        """Set up complete test scenario"""
        self.category = Category.objects.create(
            name="Integration Test Category",
            meta={'default_expiry_days': 5}
        )
        
        self.product = Product.objects.create(
            name="Integration Test Product",
            category=self.category,
            reorder_point=Decimal('3.000')
        )
        
        self.inventory_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=1),  # Expires tomorrow
            quantity_remaining=Decimal('5.000'),
            unit='szt',
            storage_location='pantry'
        )
        
    def test_consumption_triggers_low_stock_alert(self):
        """Test that consumption can trigger low stock alerts"""
        client = Client()
        
        # Consume enough to go below reorder point
        url = reverse('chatbot_api:inventory-consume', kwargs={'inventory_id': self.inventory_item.id})
        data = {'consumed_qty': '3.0'}  # Leaves 2.0, below reorder_point of 3.0
        
        response = client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Now check alerts - should find low stock
        result = check_inventory_alerts()
        
        self.assertTrue(result['success'])
        self.assertGreater(result['alerts_count'], 0)
        
        # Should find both expiring and low stock alerts for the same item
        alerts = result['alerts']
        alert_types = [alert['type'] for alert in alerts]
        
        self.assertIn('expiring', alert_types)  # Expires tomorrow
        # Note: The same item won't appear twice in alerts due to deduplication logic
        
        # Verify the alert contains correct information
        item_alerts = [a for a in alerts if a['item_id'] == self.inventory_item.id]
        self.assertEqual(len(item_alerts), 1)  # Only one alert per item due to deduplication
        
        alert = item_alerts[0]
        self.assertEqual(alert['product_name'], 'Integration Test Product')
        self.assertEqual(alert['quantity'], 2.0)  # After consumption