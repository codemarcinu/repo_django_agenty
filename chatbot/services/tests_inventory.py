"""
Tests for inventory service.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from inventory.models import Category, InventoryItem, Product, Receipt, ReceiptLineItem

from .inventory_service import InventoryService, get_inventory_service


class InventoryServiceTest(TestCase):
    """Test InventoryService functionality."""

    def setUp(self):
        """Set up test data."""
        self.service = InventoryService()

        # Create test categories
        self.dairy_category = Category.objects.create(
            name="Dairy", meta={"expiry_days": 7}
        )

        self.meat_category = Category.objects.create(
            name="Meat", meta={"expiry_days": 3}
        )

        self.pantry_category = Category.objects.create(
            name="Pantry Items", meta={"expiry_days": 365}
        )

        # Create test products
        self.milk_product = Product.objects.create(
            name="Mleko 3,2%",
            brand="Łaciate",
            category=self.dairy_category,
            reorder_point=Decimal("2.000"),
        )

        self.bread_product = Product.objects.create(
            name="Chleb graham", brand="Kępno", reorder_point=Decimal("1.000")
        )

        self.chicken_product = Product.objects.create(
            name="Filet z kurczaka",
            brand="Fresh",
            category=self.meat_category,
            reorder_point=Decimal("0.500"),
        )

        # Create test receipt
        self.receipt = Receipt.objects.create(
            store_name="Test Store",
            purchased_at=timezone.now(),
            total=Decimal("25.99"),
            source_file_path="/test/receipt.pdf",
            status="completed",
        )

        # Create test line items
        self.line_item_milk = ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Mleko UHT Łaciate 3,2% 1L",
            quantity=Decimal("2.000"),
            unit_price=Decimal("3.49"),
            line_total=Decimal("6.98"),
            matched_product=self.milk_product,
        )

        self.line_item_bread = ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Chleb graham 500g",
            quantity=Decimal("1.000"),
            unit_price=Decimal("4.20"),
            line_total=Decimal("4.20"),
            matched_product=self.bread_product,
        )

        self.line_item_chicken = ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Filet kurczak kg",
            quantity=Decimal("0.650"),
            unit_price=Decimal("22.99"),
            line_total=Decimal("14.94"),
            matched_product=self.chicken_product,
        )

    def test_service_initialization(self):
        """Test service initialization."""
        self.assertIsInstance(self.service.default_expiry_days, dict)
        self.assertIn("dairy", self.service.default_expiry_days)
        self.assertEqual(self.service.default_expiry_days["dairy"], 7)

    def test_calculate_expiry_date_from_category_meta(self):
        """Test expiry date calculation from category metadata."""
        purchase_date = date.today()

        # Test with dairy category (7 days from meta)
        expiry_date = self.service._calculate_expiry_date(
            self.milk_product, purchase_date
        )
        expected_date = purchase_date + timedelta(days=7)
        self.assertEqual(expiry_date, expected_date)

        # Test with meat category (3 days from meta)
        expiry_date = self.service._calculate_expiry_date(
            self.chicken_product, purchase_date
        )
        expected_date = purchase_date + timedelta(days=3)
        self.assertEqual(expiry_date, expected_date)

    def test_calculate_expiry_date_from_product_name(self):
        """Test expiry date calculation from product name heuristics."""
        purchase_date = date.today()

        # Test bread product (no category)
        expiry_date = self.service._calculate_expiry_date(
            self.bread_product, purchase_date
        )
        expected_date = purchase_date + timedelta(days=3)  # Bread heuristic
        self.assertEqual(expiry_date, expected_date)

    def test_guess_storage_location(self):
        """Test storage location guessing."""
        # Dairy product -> fridge
        location = self.service._guess_storage_location(self.milk_product)
        self.assertEqual(location, "fridge")

        # Meat product -> fridge
        location = self.service._guess_storage_location(self.chicken_product)
        self.assertEqual(location, "fridge")

        # No specific category -> pantry
        location = self.service._guess_storage_location(self.bread_product)
        self.assertEqual(location, "pantry")

    def test_guess_unit_from_product(self):
        """Test unit guessing from product names."""
        # Milk (liters)
        unit = self.service._guess_unit_from_product(self.line_item_milk)
        self.assertEqual(unit, "l")

        # Chicken (kg)
        unit = self.service._guess_unit_from_product(self.line_item_chicken)
        self.assertEqual(unit, "kg")

        # Bread (default to pieces)
        unit = self.service._guess_unit_from_product(self.line_item_bread)
        self.assertEqual(unit, "g")  # Should detect 'g' from '500g'

    def test_process_receipt_for_inventory_success(self):
        """Test successful receipt processing for inventory."""
        # Process receipt
        success, message = self.service.process_receipt_for_inventory(self.receipt.id)

        self.assertTrue(success)
        self.assertIn("3 items created", message)

        # Verify inventory items were created
        inventory_items = InventoryItem.objects.all()
        self.assertEqual(inventory_items.count(), 3)

        # Check milk item
        milk_item = InventoryItem.objects.get(product=self.milk_product)
        self.assertEqual(milk_item.quantity_remaining, Decimal("2.000"))
        self.assertEqual(milk_item.storage_location, "fridge")
        self.assertEqual(milk_item.unit, "l")
        self.assertIsNotNone(milk_item.expiry_date)

        # Check chicken item
        chicken_item = InventoryItem.objects.get(product=self.chicken_product)
        self.assertEqual(chicken_item.quantity_remaining, Decimal("0.650"))
        self.assertEqual(chicken_item.storage_location, "fridge")
        self.assertEqual(chicken_item.unit, "kg")

    def test_process_receipt_with_existing_inventory(self):
        """Test processing receipt when inventory items already exist."""
        purchase_date = self.receipt.purchased_at.date()

        # Create existing inventory item for milk
        existing_item = InventoryItem.objects.create(
            product=self.milk_product,
            purchase_date=purchase_date,
            expiry_date=purchase_date + timedelta(days=7),
            quantity_remaining=Decimal("1.000"),
            unit="l",
            storage_location="fridge",
        )

        # Process receipt
        success, message = self.service.process_receipt_for_inventory(self.receipt.id)

        self.assertTrue(success)
        self.assertIn("1 items updated", message)
        self.assertIn("2 items created", message)

        # Verify existing item was updated
        existing_item.refresh_from_db()
        self.assertEqual(existing_item.quantity_remaining, Decimal("3.000"))  # 1 + 2

        # Verify total items count
        self.assertEqual(InventoryItem.objects.count(), 3)  # 1 updated + 2 new

    def test_find_similar_inventory_items(self):
        """Test finding similar inventory items for merging."""
        purchase_date = date.today()
        expiry_date = purchase_date + timedelta(days=7)

        # Create existing item with exact same date
        existing_item = InventoryItem.objects.create(
            product=self.milk_product,
            purchase_date=purchase_date,
            expiry_date=expiry_date,
            quantity_remaining=Decimal("1.000"),
            unit="l",
            storage_location="fridge",
        )

        # Find similar items
        similar_items = self.service._find_similar_inventory_items(
            self.milk_product, purchase_date, expiry_date
        )

        self.assertEqual(len(similar_items), 1)
        self.assertEqual(similar_items[0], existing_item)

        # Test with slightly different dates (within 3-day range)
        similar_items = self.service._find_similar_inventory_items(
            self.milk_product,
            purchase_date + timedelta(days=2),
            expiry_date + timedelta(days=2),
        )

        self.assertEqual(len(similar_items), 1)

        # Test with too different dates (outside 3-day range)
        similar_items = self.service._find_similar_inventory_items(
            self.milk_product,
            purchase_date + timedelta(days=5),
            expiry_date + timedelta(days=5),
        )

        self.assertEqual(len(similar_items), 0)

    def test_get_inventory_summary(self):
        """Test inventory summary statistics."""
        # Create some inventory items
        self.service.process_receipt_for_inventory(self.receipt.id)

        # Create expired item
        expired_item = InventoryItem.objects.create(
            product=self.milk_product,
            purchase_date=date.today() - timedelta(days=10),
            expiry_date=date.today() - timedelta(days=1),  # Expired
            quantity_remaining=Decimal("0.5"),
            unit="l",
            storage_location="fridge",
        )

        # Create expiring soon item
        expiring_item = InventoryItem.objects.create(
            product=self.bread_product,
            purchase_date=date.today() - timedelta(days=1),
            expiry_date=date.today() + timedelta(days=1),  # Expires tomorrow
            quantity_remaining=Decimal("1.0"),
            unit="szt",
            storage_location="pantry",
        )

        summary = self.service.get_inventory_summary()

        self.assertIn("total_items", summary)
        self.assertIn("active_items", summary)
        self.assertIn("expired", summary)
        self.assertIn("soon_expiring", summary)
        self.assertIn("storage_breakdown", summary)

        self.assertEqual(summary["expired"], 1)
        self.assertEqual(summary["soon_expiring"], 1)
        self.assertGreater(summary["total_items"], 0)

    def test_get_expiring_items(self):
        """Test getting expiring items."""
        # Create item expiring tomorrow
        expiring_item = InventoryItem.objects.create(
            product=self.milk_product,
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=1),
            quantity_remaining=Decimal("1.0"),
            unit="l",
            storage_location="fridge",
        )

        # Create item expiring in 10 days
        future_item = InventoryItem.objects.create(
            product=self.bread_product,
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=10),
            quantity_remaining=Decimal("1.0"),
            unit="szt",
            storage_location="pantry",
        )

        # Get items expiring within 7 days
        expiring_items = self.service.get_expiring_items(days=7)

        self.assertEqual(len(expiring_items), 1)
        self.assertEqual(expiring_items[0], expiring_item)

    def test_get_low_stock_items(self):
        """Test getting low stock items."""
        # Create low stock item (below reorder point)
        low_stock_item = InventoryItem.objects.create(
            product=self.milk_product,  # reorder_point = 2.000
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=7),
            quantity_remaining=Decimal("1.5"),  # Below reorder point
            unit="l",
            storage_location="fridge",
        )

        # Create normal stock item
        normal_stock_item = InventoryItem.objects.create(
            product=self.chicken_product,  # reorder_point = 0.500
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=3),
            quantity_remaining=Decimal("2.0"),  # Above reorder point
            unit="kg",
            storage_location="fridge",
        )

        low_stock_items = self.service.get_low_stock_items()

        self.assertEqual(len(low_stock_items), 1)
        self.assertEqual(low_stock_items[0], low_stock_item)

    def test_cleanup_empty_items(self):
        """Test cleanup of empty inventory items."""
        # Create empty item
        empty_item = InventoryItem.objects.create(
            product=self.milk_product,
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=7),
            quantity_remaining=Decimal("0.0"),
            unit="l",
            storage_location="fridge",
        )

        # Create normal item
        normal_item = InventoryItem.objects.create(
            product=self.bread_product,
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=3),
            quantity_remaining=Decimal("1.0"),
            unit="szt",
            storage_location="pantry",
        )

        # Cleanup
        deleted_count = self.service.cleanup_empty_items()

        self.assertEqual(deleted_count, 1)
        self.assertEqual(InventoryItem.objects.count(), 1)
        self.assertTrue(InventoryItem.objects.filter(id=normal_item.id).exists())
        self.assertFalse(InventoryItem.objects.filter(id=empty_item.id).exists())

    def test_bulk_update_expiry_dates(self):
        """Test bulk update of missing expiry dates."""
        # Create items without expiry dates
        item_without_expiry = InventoryItem.objects.create(
            product=self.milk_product,
            purchase_date=date.today(),
            expiry_date=None,  # Missing expiry
            quantity_remaining=Decimal("1.0"),
            unit="l",
            storage_location="fridge",
        )

        item_with_expiry = InventoryItem.objects.create(
            product=self.bread_product,
            purchase_date=date.today(),
            expiry_date=date.today() + timedelta(days=3),  # Has expiry
            quantity_remaining=Decimal("1.0"),
            unit="szt",
            storage_location="pantry",
        )

        # Update expiry dates
        updated_count, error_count = self.service.bulk_update_expiry_dates()

        self.assertEqual(updated_count, 1)
        self.assertEqual(error_count, 0)

        # Check that expiry was added
        item_without_expiry.refresh_from_db()
        self.assertIsNotNone(item_without_expiry.expiry_date)
        self.assertEqual(
            item_without_expiry.expiry_date,
            date.today() + timedelta(days=7),  # Dairy category expiry
        )

    def test_process_receipt_for_inventory_errors(self):
        """Test error handling in receipt processing."""
        # Test with non-existent receipt
        success, message = self.service.process_receipt_for_inventory(99999)
        self.assertFalse(success)
        self.assertIn("not found", message)

        # Test with incomplete receipt
        incomplete_receipt = Receipt.objects.create(
            store_name="Incomplete Store",
            purchased_at=timezone.now(),
            total=Decimal("10.00"),
            source_file_path="/test/incomplete.pdf",
            status="pending_ocr",  # Not completed
        )

        success, message = self.service.process_receipt_for_inventory(
            incomplete_receipt.id
        )
        self.assertFalse(success)
        self.assertIn("not completed", message)


class InventoryServiceFactoryTest(TestCase):
    """Test inventory service factory function."""

    def test_get_inventory_service(self):
        """Test getting default inventory service instance."""
        service = get_inventory_service()

        self.assertIsInstance(service, InventoryService)
        self.assertIsNotNone(service.default_expiry_days)


class InventoryServiceIntegrationTest(TestCase):
    """Integration tests for InventoryService with realistic scenarios."""

    def setUp(self):
        """Set up realistic test data."""
        self.service = InventoryService()

        # Create realistic categories
        self.categories = {
            "dairy": Category.objects.create(name="Dairy", meta={"expiry_days": 7}),
            "bread": Category.objects.create(
                name="Bread & Bakery", meta={"expiry_days": 3}
            ),
            "meat": Category.objects.create(
                name="Meat & Poultry", meta={"expiry_days": 2}
            ),
        }

        # Create realistic products
        self.products = [
            Product.objects.create(
                name="Mleko UHT 2%",
                brand="Łaciate",
                category=self.categories["dairy"],
                reorder_point=Decimal("2.000"),
            ),
            Product.objects.create(
                name="Chleb żytni",
                brand="Putka",
                category=self.categories["bread"],
                reorder_point=Decimal("1.000"),
            ),
            Product.objects.create(
                name="Filet z kurczaka",
                brand="Drób",
                category=self.categories["meat"],
                reorder_point=Decimal("0.500"),
            ),
        ]

    def test_full_receipt_processing_workflow(self):
        """Test complete workflow from receipt to inventory."""
        # Create realistic receipt
        receipt = Receipt.objects.create(
            store_name="Biedronka",
            purchased_at=timezone.now(),
            total=Decimal("28.47"),
            source_file_path="/test/biedronka_receipt.pdf",
            status="completed",
        )

        # Create realistic line items
        line_items = [
            ReceiptLineItem.objects.create(
                receipt=receipt,
                product_name="Mleko UHT Łaciate 2% 1L",
                quantity=Decimal("3.000"),
                unit_price=Decimal("3.49"),
                line_total=Decimal("10.47"),
                matched_product=self.products[0],
            ),
            ReceiptLineItem.objects.create(
                receipt=receipt,
                product_name="Chleb żytni Putka 500g",
                quantity=Decimal("2.000"),
                unit_price=Decimal("4.20"),
                line_total=Decimal("8.40"),
                matched_product=self.products[1],
            ),
            ReceiptLineItem.objects.create(
                receipt=receipt,
                product_name="Filet kurczak kg",
                quantity=Decimal("0.850"),
                unit_price=Decimal("11.32"),
                line_total=Decimal("9.62"),
                matched_product=self.products[2],
            ),
        ]

        # Process receipt for inventory
        success, message = self.service.process_receipt_for_inventory(receipt.id)

        # Verify success
        self.assertTrue(success)
        self.assertIn("3 items created", message)

        # Verify inventory items
        inventory_items = InventoryItem.objects.all().order_by("product__name")
        self.assertEqual(inventory_items.count(), 3)

        # Check specific items
        chicken_item = inventory_items.get(product=self.products[2])
        self.assertEqual(chicken_item.quantity_remaining, Decimal("0.850"))
        self.assertEqual(chicken_item.storage_location, "fridge")
        self.assertEqual(chicken_item.unit, "kg")
        self.assertEqual(
            chicken_item.expiry_date, receipt.purchased_at.date() + timedelta(days=2)
        )

        milk_item = inventory_items.get(product=self.products[0])
        self.assertEqual(milk_item.quantity_remaining, Decimal("3.000"))
        self.assertEqual(milk_item.storage_location, "fridge")
        self.assertEqual(milk_item.unit, "l")

        # Test inventory summary
        summary = self.service.get_inventory_summary()
        self.assertEqual(summary["total_items"], 3)
        self.assertEqual(summary["active_items"], 3)
        self.assertEqual(summary["storage_breakdown"]["fridge"], 2)
        self.assertEqual(summary["storage_breakdown"]["pantry"], 1)

    def test_multiple_receipts_inventory_merging(self):
        """Test inventory merging across multiple receipts."""
        purchase_date = timezone.now()

        # First receipt
        receipt1 = Receipt.objects.create(
            store_name="Tesco",
            purchased_at=purchase_date,
            total=Decimal("10.47"),
            source_file_path="/test/tesco1.pdf",
            status="completed",
        )

        ReceiptLineItem.objects.create(
            receipt=receipt1,
            product_name="Mleko UHT 2% 1L",
            quantity=Decimal("2.000"),
            unit_price=Decimal("3.49"),
            line_total=Decimal("6.98"),
            matched_product=self.products[0],
        )

        # Second receipt (same day)
        receipt2 = Receipt.objects.create(
            store_name="Tesco",
            purchased_at=purchase_date,
            total=Decimal("10.47"),
            source_file_path="/test/tesco2.pdf",
            status="completed",
        )

        ReceiptLineItem.objects.create(
            receipt=receipt2,
            product_name="Mleko 2% Łaciate",
            quantity=Decimal("1.000"),
            unit_price=Decimal("3.49"),
            line_total=Decimal("3.49"),
            matched_product=self.products[0],
        )

        # Process both receipts
        success1, _ = self.service.process_receipt_for_inventory(receipt1.id)
        success2, _ = self.service.process_receipt_for_inventory(receipt2.id)

        self.assertTrue(success1)
        self.assertTrue(success2)

        # Should have merged into single inventory item
        milk_items = InventoryItem.objects.filter(product=self.products[0])
        self.assertEqual(milk_items.count(), 1)

        milk_item = milk_items.first()
        self.assertEqual(milk_item.quantity_remaining, Decimal("3.000"))  # 2 + 1
