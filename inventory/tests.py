"""
Unit tests for inventory models.
Tests the receipt processing pipeline models.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from .models import (
    Category, Product, Receipt, ReceiptLineItem, 
    InventoryItem, ConsumptionEvent
)


class CategoryModelTest(TestCase):
    """Test Category model functionality."""
    
    def setUp(self):
        self.parent_category = Category.objects.create(
            name="Nabiał",
            meta={"expiry_days": 14}
        )
        self.child_category = Category.objects.create(
            name="Mleko",
            parent=self.parent_category,
            meta={"expiry_days": 7}
        )
    
    def test_category_creation(self):
        """Test basic category creation."""
        category = Category.objects.create(name="Test Category")
        self.assertEqual(category.name, "Test Category")
        self.assertEqual(category.meta, {})
        self.assertIsNone(category.parent)
    
    def test_category_hierarchy(self):
        """Test hierarchical category structure."""
        self.assertEqual(self.child_category.parent, self.parent_category)
        self.assertIn(self.child_category, self.parent_category.subcategories.all())
    
    def test_get_full_path(self):
        """Test full path generation."""
        expected_path = "Nabiał → Mleko"
        self.assertEqual(self.child_category.get_full_path(), expected_path)
        self.assertEqual(self.parent_category.get_full_path(), "Nabiał")
    
    def test_get_default_expiry_days(self):
        """Test expiry days extraction from metadata."""
        self.assertEqual(self.parent_category.get_default_expiry_days(), 14)
        self.assertEqual(self.child_category.get_default_expiry_days(), 7)
        
        # Test default value
        category_no_meta = Category.objects.create(name="No Meta")
        self.assertEqual(category_no_meta.get_default_expiry_days(), 30)
    
    def test_category_str_representation(self):
        """Test string representation."""
        self.assertEqual(str(self.parent_category), "Nabiał")
        self.assertEqual(str(self.child_category), "Nabiał → Mleko")


class ProductModelTest(TestCase):
    """Test Product model functionality."""
    
    def setUp(self):
        self.category = Category.objects.create(name="Beverages")
        self.product = Product.objects.create(
            name="Coca Cola",
            brand="Coca Cola Company",
            barcode="1234567890123",
            category=self.category,
            nutrition={"calories": 139, "sugar": "39g"},
            aliases=["Coke", "Cola"],
            reorder_point=Decimal('2.000')
        )
    
    def test_product_creation(self):
        """Test basic product creation."""
        self.assertEqual(self.product.name, "Coca Cola")
        self.assertEqual(self.product.brand, "Coca Cola Company")
        self.assertEqual(self.product.barcode, "1234567890123")
        self.assertEqual(self.product.category, self.category)
        self.assertTrue(self.product.is_active)
    
    def test_product_defaults(self):
        """Test product default values."""
        product = Product.objects.create(name="Simple Product")
        self.assertEqual(product.brand, "")
        self.assertEqual(product.barcode, "")
        self.assertEqual(product.nutrition, {})
        self.assertEqual(product.aliases, [])
        self.assertTrue(product.is_active)
        self.assertEqual(product.reorder_point, Decimal('1.000'))
    
    def test_add_alias(self):
        """Test adding aliases to product."""
        initial_count = len(self.product.aliases)
        self.product.add_alias("Pepsi Alternative")
        
        self.product.refresh_from_db()
        self.assertEqual(len(self.product.aliases), initial_count + 1)
        self.assertIn("Pepsi Alternative", self.product.aliases)
        
        # Test duplicate alias prevention
        self.product.add_alias("Coke")  # Already exists
        self.product.refresh_from_db()
        self.assertEqual(self.product.aliases.count("Coke"), 1)
    
    def test_get_all_names(self):
        """Test getting all possible product names."""
        names = self.product.get_all_names()
        expected_names = ["Coca Cola", "Coca Cola Company Coca Cola", "Coke", "Cola"]
        self.assertEqual(set(names), set(expected_names))
        
        # Test product without brand
        product_no_brand = Product.objects.create(
            name="Generic Cola",
            aliases=["Generic"]
        )
        names_no_brand = product_no_brand.get_all_names()
        self.assertEqual(set(names_no_brand), {"Generic Cola", "Generic"})
    
    def test_product_str_representation(self):
        """Test string representation."""
        self.assertEqual(str(self.product), "Coca Cola Company Coca Cola")
        
        product_no_brand = Product.objects.create(name="Generic")
        self.assertEqual(str(product_no_brand), "Generic")
    
    def test_ghost_product(self):
        """Test ghost product creation."""
        ghost = Product.objects.create(
            name="Unknown Product",
            is_active=False
        )
        self.assertFalse(ghost.is_active)


class ReceiptModelTest(TestCase):
    """Test Receipt model functionality."""
    
    def setUp(self):
        self.receipt = Receipt.objects.create(
            store_name="Test Store",
            purchased_at=timezone.now(),
            total=Decimal('25.99'),
            currency='PLN',
            raw_text={"lines": ["line1", "line2"], "confidence": 0.95},
            source_file_path="/test/receipt.pdf",
            status='completed'
        )
    
    def test_receipt_creation(self):
        """Test basic receipt creation."""
        self.assertEqual(self.receipt.store_name, "Test Store")
        self.assertEqual(self.receipt.total, Decimal('25.99'))
        self.assertEqual(self.receipt.currency, 'PLN')
        self.assertEqual(self.receipt.status, 'completed')
    
    def test_receipt_defaults(self):
        """Test receipt default values."""
        receipt = Receipt.objects.create(
            purchased_at=timezone.now(),
            total=Decimal('10.00'),
            source_file_path="/test/receipt2.pdf"
        )
        self.assertEqual(receipt.store_name, "")
        self.assertEqual(receipt.currency, 'PLN')
        self.assertEqual(receipt.status, 'pending_ocr')
        self.assertEqual(receipt.raw_text, {})
        self.assertEqual(receipt.processing_notes, "")
    
    def test_get_total_from_items(self):
        """Test calculating total from line items."""
        # Create line items
        ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Item 1",
            quantity=Decimal('1.000'),
            unit_price=Decimal('10.00'),
            line_total=Decimal('10.00')
        )
        ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Item 2",
            quantity=Decimal('2.000'),
            unit_price=Decimal('7.99'),
            line_total=Decimal('15.98')
        )
        
        calculated_total = self.receipt.get_total_from_items()
        self.assertEqual(calculated_total, Decimal('25.98'))
    
    def test_get_total_discrepancy(self):
        """Test total discrepancy calculation."""
        ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Item 1",
            quantity=Decimal('1.000'),
            unit_price=Decimal('25.50'),
            line_total=Decimal('25.50')
        )
        
        discrepancy = self.receipt.get_total_discrepancy()
        self.assertEqual(discrepancy, Decimal('0.49'))  # |25.99 - 25.50|
    
    def test_receipt_str_representation(self):
        """Test string representation."""
        expected = f"Receipt {self.receipt.id} - Test Store ({self.receipt.purchased_at.date()})"
        self.assertEqual(str(self.receipt), expected)


class ReceiptLineItemModelTest(TestCase):
    """Test ReceiptLineItem model functionality."""
    
    def setUp(self):
        self.receipt = Receipt.objects.create(
            purchased_at=timezone.now(),
            total=Decimal('10.00'),
            source_file_path="/test/receipt.pdf"
        )
        self.product = Product.objects.create(name="Test Product")
        self.line_item = ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Test Product Name",
            quantity=Decimal('2.000'),
            unit_price=Decimal('5.00'),
            line_total=Decimal('10.00'),
            vat_code='A',
            meta={"original_text": "2x Test Product 10.00 A"},
            matched_product=self.product
        )
    
    def test_line_item_creation(self):
        """Test basic line item creation."""
        self.assertEqual(self.line_item.product_name, "Test Product Name")
        self.assertEqual(self.line_item.quantity, Decimal('2.000'))
        self.assertEqual(self.line_item.unit_price, Decimal('5.00'))
        self.assertEqual(self.line_item.line_total, Decimal('10.00'))
        self.assertEqual(self.line_item.vat_code, 'A')
        self.assertEqual(self.line_item.matched_product, self.product)
    
    def test_calculate_line_total(self):
        """Test line total calculation."""
        calculated = self.line_item.calculate_line_total()
        self.assertEqual(calculated, Decimal('10.00'))
    
    def test_validate_line_total(self):
        """Test line total validation."""
        # Valid line total
        self.assertTrue(self.line_item.validate_line_total())
        
        # Invalid line total (exceeds tolerance)
        self.line_item.line_total = Decimal('20.00')
        self.assertFalse(self.line_item.validate_line_total())
        
        # Within tolerance
        self.line_item.line_total = Decimal('10.04')
        self.assertTrue(self.line_item.validate_line_total())
    
    def test_line_item_defaults(self):
        """Test line item default values."""
        item = ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Simple Item",
            quantity=Decimal('1.000'),
            unit_price=Decimal('5.00'),
            line_total=Decimal('5.00')
        )
        self.assertEqual(item.vat_code, "")
        self.assertEqual(item.meta, {})
        self.assertIsNone(item.matched_product)
    
    def test_line_item_str_representation(self):
        """Test string representation."""
        expected = "Test Product Name x2.000 = 10.00"
        self.assertEqual(str(self.line_item), expected)


class InventoryItemModelTest(TestCase):
    """Test InventoryItem model functionality."""
    
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Product",
            reorder_point=Decimal('5.000')
        )
        self.inventory_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=7),
            quantity_remaining=Decimal('10.000'),
            unit='szt',
            storage_location='pantry',
            batch_id='BATCH001'
        )
    
    def test_inventory_item_creation(self):
        """Test basic inventory item creation."""
        self.assertEqual(self.inventory_item.product, self.product)
        self.assertEqual(self.inventory_item.quantity_remaining, Decimal('10.000'))
        self.assertEqual(self.inventory_item.unit, 'szt')
        self.assertEqual(self.inventory_item.storage_location, 'pantry')
        self.assertEqual(self.inventory_item.batch_id, 'BATCH001')
    
    def test_inventory_item_defaults(self):
        """Test inventory item default values."""
        item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=date.today(),
            quantity_remaining=Decimal('5.000')
        )
        self.assertEqual(item.unit, 'szt')
        self.assertEqual(item.storage_location, 'pantry')
        self.assertEqual(item.batch_id, '')
        self.assertIsNone(item.expiry_date)
    
    def test_is_expired(self):
        """Test expiry checking."""
        # Not expired
        self.assertFalse(self.inventory_item.is_expired())
        
        # Expired
        self.inventory_item.expiry_date = date.today() - timedelta(days=1)
        self.assertTrue(self.inventory_item.is_expired())
        
        # No expiry date
        self.inventory_item.expiry_date = None
        self.assertFalse(self.inventory_item.is_expired())
    
    def test_days_until_expiry(self):
        """Test days until expiry calculation."""
        self.assertEqual(self.inventory_item.days_until_expiry(), 7)
        
        # Expired item
        self.inventory_item.expiry_date = date.today() - timedelta(days=2)
        self.assertEqual(self.inventory_item.days_until_expiry(), -2)
        
        # No expiry date
        self.inventory_item.expiry_date = None
        self.assertIsNone(self.inventory_item.days_until_expiry())
    
    def test_is_expiring_soon(self):
        """Test expiring soon detection."""
        # Expires in 7 days, default threshold is 2 days
        self.assertFalse(self.inventory_item.is_expiring_soon())
        
        # Expires tomorrow
        self.inventory_item.expiry_date = date.today() + timedelta(days=1)
        self.assertTrue(self.inventory_item.is_expiring_soon())
        
        # Custom threshold
        self.inventory_item.expiry_date = date.today() + timedelta(days=5)
        self.assertTrue(self.inventory_item.is_expiring_soon(days=7))
    
    def test_is_low_stock(self):
        """Test low stock detection."""
        # Above reorder point
        self.assertFalse(self.inventory_item.is_low_stock())
        
        # Below reorder point
        self.inventory_item.quantity_remaining = Decimal('3.000')
        self.assertTrue(self.inventory_item.is_low_stock())
        
        # At reorder point
        self.inventory_item.quantity_remaining = Decimal('5.000')
        self.assertTrue(self.inventory_item.is_low_stock())
    
    def test_consume(self):
        """Test consumption functionality."""
        initial_quantity = self.inventory_item.quantity_remaining
        consume_qty = Decimal('3.000')
        
        consumption = self.inventory_item.consume(consume_qty, "Test consumption")
        
        # Check inventory item updated
        self.inventory_item.refresh_from_db()
        self.assertEqual(
            self.inventory_item.quantity_remaining, 
            initial_quantity - consume_qty
        )
        
        # Check consumption event created
        self.assertIsInstance(consumption, ConsumptionEvent)
        self.assertEqual(consumption.consumed_qty, consume_qty)
        self.assertEqual(consumption.notes, "Test consumption")
        self.assertEqual(consumption.inventory_item, self.inventory_item)
    
    def test_consume_too_much(self):
        """Test consuming more than available."""
        with self.assertRaises(ValueError):
            self.inventory_item.consume(Decimal('15.000'))
    
    def test_inventory_item_str_representation(self):
        """Test string representation."""
        expected = "Test Product - 10.000szt"
        self.assertEqual(str(self.inventory_item), expected)


class ConsumptionEventModelTest(TestCase):
    """Test ConsumptionEvent model functionality."""
    
    def setUp(self):
        self.product = Product.objects.create(name="Test Product")
        self.inventory_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=date.today(),
            quantity_remaining=Decimal('10.000')
        )
        self.consumption = ConsumptionEvent.objects.create(
            inventory_item=self.inventory_item,
            consumed_qty=Decimal('2.500'),
            notes="Test consumption"
        )
    
    def test_consumption_creation(self):
        """Test basic consumption event creation."""
        self.assertEqual(self.consumption.inventory_item, self.inventory_item)
        self.assertEqual(self.consumption.consumed_qty, Decimal('2.500'))
        self.assertEqual(self.consumption.notes, "Test consumption")
        self.assertIsNotNone(self.consumption.consumed_at)
    
    def test_consumption_defaults(self):
        """Test consumption event default values."""
        consumption = ConsumptionEvent.objects.create(
            inventory_item=self.inventory_item,
            consumed_qty=Decimal('1.000')
        )
        self.assertEqual(consumption.notes, "")
        self.assertIsNotNone(consumption.consumed_at)
    
    def test_consumption_str_representation(self):
        """Test string representation."""
        expected = "Consumed 2.500 of Test Product"
        self.assertEqual(str(self.consumption), expected)
    
    def test_consumption_ordering(self):
        """Test consumption events are ordered by consumed_at desc."""
        older_consumption = ConsumptionEvent.objects.create(
            inventory_item=self.inventory_item,
            consumed_qty=Decimal('1.000'),
            consumed_at=timezone.now() - timedelta(hours=1)
        )
        
        consumption_events = list(ConsumptionEvent.objects.all())
        self.assertEqual(consumption_events[0], self.consumption)  # Most recent first
        self.assertEqual(consumption_events[1], older_consumption)


class ModelValidationTest(TestCase):
    """Test model validation and constraints."""
    
    def test_negative_quantities(self):
        """Test that negative quantities are not allowed."""
        product = Product.objects.create(name="Test Product")
        
        with self.assertRaises(ValidationError):
            item = InventoryItem.objects.create(
                product=product,
                purchase_date=date.today(),
                quantity_remaining=Decimal('-1.000')
            )
            item.full_clean()
    
    def test_zero_quantity_edge_case(self):
        """Test zero quantity handling."""
        product = Product.objects.create(name="Test Product")
        
        # Should allow zero quantity
        item = InventoryItem.objects.create(
            product=product,
            purchase_date=date.today(),
            quantity_remaining=Decimal('0.000')
        )
        item.full_clean()  # Should not raise
    
    def test_receipt_line_item_minimal_quantity(self):
        """Test minimal quantity validation for receipt line items."""
        receipt = Receipt.objects.create(
            purchased_at=timezone.now(),
            total=Decimal('1.00'),
            source_file_path="/test/receipt.pdf"
        )
        
        with self.assertRaises(ValidationError):
            item = ReceiptLineItem.objects.create(
                receipt=receipt,
                product_name="Test",
                quantity=Decimal('0.000'),  # Below minimum 0.001
                unit_price=Decimal('1.00'),
                line_total=Decimal('1.00')
            )
            item.full_clean()
