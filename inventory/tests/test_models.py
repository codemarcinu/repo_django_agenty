import pytest
from decimal import Decimal
from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from inventory.models import (
    Category, Product, Receipt, ReceiptLineItem,
    InventoryItem, ConsumptionEvent, Rule
)


@pytest.mark.unit
class CategoryModelTest(TestCase):
    """Test Category model with hierarchical structure and metadata."""

    def test_category_creation(self):
        """Test basic category creation."""
        category = Category.objects.create(
            name="Nabiał",
            meta={"expiry_days": 7, "storage": "fridge"}
        )

        self.assertEqual(str(category), "Nabiał")
        self.assertEqual(category.get_default_expiry_days(), 7)
        self.assertIsNotNone(category.created_at)

    def test_category_hierarchy(self):
        """Test parent-child category relationships."""
        parent = Category.objects.create(name="Nabiał")
        child = Category.objects.create(name="Sery", parent=parent)

        self.assertEqual(str(child), "Nabiał → Sery")
        self.assertEqual(child.get_full_path(), "Nabiał → Sery")
        self.assertIn(child, parent.subcategories.all())

    def test_category_default_expiry(self):
        """Test default expiry calculation from metadata."""
        category_no_meta = Category.objects.create(name="Test")
        category_with_meta = Category.objects.create(
            name="Dairy",
            meta={"expiry_days": 5}
        )

        self.assertEqual(category_no_meta.get_default_expiry_days(), 30)  # Default
        self.assertEqual(category_with_meta.get_default_expiry_days(), 5)


@pytest.mark.unit
class ProductModelTest(TestCase):
    """Test Product catalog with normalization and matching capabilities."""

    def setUp(self):
        self.category = Category.objects.create(name="Nabiał")

    def test_product_creation(self):
        """Test basic product creation."""
        product = Product.objects.create(
            name="Mleko 3.2%",
            brand="Łaciate",
            barcode="1234567890123",
            category=self.category,
            reorder_point=Decimal("2.0")
        )

        self.assertEqual(str(product), "Łaciate Mleko 3.2%")
        self.assertEqual(product.barcode, "1234567890123")
        self.assertEqual(product.reorder_point, Decimal("2.0"))

    def test_product_without_brand(self):
        """Test product without brand uses just name."""
        product = Product.objects.create(name="Chleb razowy")
        self.assertEqual(str(product), "Chleb razowy")

    def test_product_aliases(self):
        """Test alias management for fuzzy matching."""
        product = Product.objects.create(name="Mleko UHT")

        # Add aliases
        product.add_alias("Mleko uht")
        product.add_alias("Mleko UHT 3.2%")

        self.assertEqual(len(product.aliases), 2)

        # Test getting all names
        all_names = product.get_all_names()
        self.assertIn("Mleko UHT", all_names)
        self.assertIn("Mleko uht", all_names)

    def test_product_alias_increment(self):
        """Test that adding same alias increments count."""
        product = Product.objects.create(name="Ser")

        product.add_alias("Ser gouda")
        product.add_alias("Ser gouda")  # Add again

        alias_entry = product.aliases[0]
        self.assertEqual(alias_entry["name"], "Ser gouda")
        self.assertEqual(alias_entry["count"], 2)


@pytest.mark.unit
class ReceiptModelTest(TestCase):
    """Test unified Receipt model with processing pipeline."""

    def test_receipt_creation(self):
        """Test basic receipt creation."""
        file_content = b"Test receipt content"
        uploaded_file = ContentFile(file_content, name="receipt.pdf")

        receipt = Receipt.objects.create(
            receipt_file=uploaded_file,
            store_name="Biedronka",
            total=Decimal("45.67"),
            status="uploaded"
        )

        self.assertEqual(str(receipt), "Receipt 1 - Biedronka - Status: uploaded")
        self.assertEqual(receipt.total, Decimal("45.67"))
        self.assertEqual(receipt.status, "uploaded")

    def test_receipt_status_transitions(self):
        """Test receipt status workflow."""
        receipt = Receipt.objects.create(status="pending")

        # Test processing states
        receipt.mark_as_processing("ocr_in_progress")
        self.assertEqual(receipt.status, "processing")
        self.assertEqual(receipt.processing_step, "ocr_in_progress")

        # Test OCR completion
        receipt.mark_ocr_done("Extracted text content")
        self.assertEqual(receipt.processing_step, "ocr_completed")
        self.assertEqual(receipt.raw_ocr_text, "Extracted text content")

        # Test LLM processing
        receipt.mark_llm_processing()
        self.assertEqual(receipt.processing_step, "parsing_in_progress")

        # Test LLM completion
        extracted_data = {"products": [{"name": "Mleko", "quantity": 1.0}]}
        receipt.mark_llm_done(extracted_data)
        self.assertEqual(receipt.processing_step, "parsing_completed")
        self.assertEqual(receipt.extracted_data, extracted_data)

        # Test completion
        receipt.mark_as_completed()
        self.assertEqual(receipt.status, "completed")
        self.assertEqual(receipt.processing_step, "done")
        self.assertIsNotNone(receipt.processed_at)

    def test_receipt_error_handling(self):
        """Test receipt error states."""
        receipt = Receipt.objects.create(status="processing")

        receipt.mark_as_error("OCR failed: image quality too low")
        self.assertEqual(receipt.status, "error")
        self.assertEqual(receipt.processing_step, "failed")
        self.assertIn("image quality", receipt.error_message)

    def test_receipt_review_workflow(self):
        """Test receipt review workflow."""
        receipt = Receipt.objects.create(status="processing")

        receipt.mark_as_ready_for_review()
        self.assertEqual(receipt.status, "review_pending")
        self.assertEqual(receipt.processing_step, "review_pending")
        self.assertTrue(receipt.is_ready_for_review())

    def test_receipt_statistics(self):
        """Test receipt statistics calculation."""
        # Create receipts with different statuses
        Receipt.objects.create(status="completed")
        Receipt.objects.create(status="pending")
        Receipt.objects.create(status="error")

        stats = Receipt.get_statistics()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["error"], 1)


@pytest.mark.unit
class ReceiptLineItemModelTest(TestCase):
    """Test ReceiptLineItem model with validation."""

    def setUp(self):
        self.receipt = Receipt.objects.create(
            store_name="Test Store",
            total=Decimal("10.00")
        )
        self.product = Product.objects.create(name="Test Product")

    def test_line_item_creation(self):
        """Test basic line item creation."""
        item = ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Mleko UHT",
            quantity=Decimal("2.0"),
            unit_price=Decimal("3.50"),
            line_total=Decimal("7.00"),
            vat_code="B"
        )

        self.assertEqual(str(item), "Mleko UHT x2.0 = 7.00")
        self.assertEqual(item.calculate_line_total(), Decimal("7.00"))

    def test_line_total_validation(self):
        """Test line total validation within tolerance."""
        item = ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Test Item",
            quantity=Decimal("2.0"),
            unit_price=Decimal("5.00"),
            line_total=Decimal("10.01")  # 1 cent over
        )

        # Should pass with default tolerance of 0.05
        self.assertTrue(item.validate_line_total())

    def test_line_item_with_matched_product(self):
        """Test line item with matched product."""
        item = ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Test Product",
            quantity=Decimal("1.0"),
            unit_price=Decimal("5.00"),
            line_total=Decimal("5.00"),
            matched_product=self.product
        )

        self.assertEqual(item.matched_product, self.product)


@pytest.mark.unit
class InventoryItemModelTest(TestCase):
    """Test InventoryItem model with expiry and stock management."""

    def setUp(self):
        self.product = Product.objects.create(name="Test Product")
        self.purchase_date = timezone.now().date()

    def test_inventory_item_creation(self):
        """Test basic inventory item creation."""
        item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=self.purchase_date,
            quantity_remaining=Decimal("5.0"),
            unit="szt",
            storage_location="fridge"
        )

        self.assertEqual(str(item), "Test Product - 5.0szt")
        self.assertEqual(item.quantity_remaining, Decimal("5.0"))

    def test_inventory_item_expiry(self):
        """Test expiry date calculations."""
        future_date = self.purchase_date + timedelta(days=5)
        past_date = self.purchase_date - timedelta(days=1)

        expired_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=self.purchase_date,
            expiry_date=past_date,
            quantity_remaining=Decimal("1.0")
        )

        fresh_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=self.purchase_date,
            expiry_date=future_date,
            quantity_remaining=Decimal("1.0")
        )

        self.assertTrue(expired_item.is_expired())
        self.assertFalse(fresh_item.is_expired())

        self.assertEqual(expired_item.days_until_expiry(), -1)
        self.assertEqual(fresh_item.days_until_expiry(), 5)

    def test_inventory_item_expiring_soon(self):
        """Test expiring soon detection."""
        soon_date = self.purchase_date + timedelta(days=1)
        later_date = self.purchase_date + timedelta(days=10)

        expiring_soon = InventoryItem.objects.create(
            product=self.product,
            purchase_date=self.purchase_date,
            expiry_date=soon_date,
            quantity_remaining=Decimal("1.0")
        )

        not_expiring_soon = InventoryItem.objects.create(
            product=self.product,
            purchase_date=self.purchase_date,
            expiry_date=later_date,
            quantity_remaining=Decimal("1.0")
        )

        self.assertTrue(expiring_soon.is_expiring_soon(days=2))
        self.assertFalse(not_expiring_soon.is_expiring_soon(days=2))

    def test_inventory_item_consumption(self):
        """Test inventory consumption."""
        item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=self.purchase_date,
            quantity_remaining=Decimal("10.0")
        )

        # Consume some quantity
        consumption = item.consume(Decimal("3.0"), "Used in recipe")

        self.assertEqual(item.quantity_remaining, Decimal("7.0"))
        self.assertEqual(consumption.consumed_qty, Decimal("3.0"))
        self.assertEqual(consumption.inventory_item, item)
        self.assertEqual(consumption.notes, "Used in recipe")

    def test_inventory_item_consumption_too_much(self):
        """Test consumption validation."""
        item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=self.purchase_date,
            quantity_remaining=Decimal("5.0")
        )

        with self.assertRaises(ValueError):
            item.consume(Decimal("10.0"))  # More than available

    def test_inventory_item_stock_management(self):
        """Test stock level operations."""
        item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=self.purchase_date,
            quantity_remaining=Decimal("5.0")
        )

        # Add quantity
        item.add_quantity(Decimal("3.0"))
        self.assertEqual(item.quantity_remaining, Decimal("8.0"))

        # Subtract quantity
        item.subtract_quantity(Decimal("2.0"))
        self.assertEqual(item.quantity_remaining, Decimal("6.0"))

        # Subtract more than available (should not go negative)
        item.subtract_quantity(Decimal("10.0"))
        self.assertEqual(item.quantity_remaining, Decimal("0.0"))

    def test_inventory_item_low_stock(self):
        """Test low stock detection."""
        low_stock_product = Product.objects.create(
            name="Low Stock Product",
            reorder_point=Decimal("1.0")
        )

        low_stock_item = InventoryItem.objects.create(
            product=low_stock_product,
            purchase_date=self.purchase_date,
            quantity_remaining=Decimal("0.5")  # Below reorder point
        )

        self.assertTrue(low_stock_item.is_low_stock())

    def test_inventory_item_class_methods(self):
        """Test class methods for inventory queries."""
        product = Product.objects.create(name="Class Test Product")
        purchase_date = timezone.now().date()

        # Create expired item
        expired_date = purchase_date - timedelta(days=1)
        InventoryItem.objects.create(
            product=product,
            purchase_date=purchase_date,
            expiry_date=expired_date,
            quantity_remaining=Decimal("1.0")
        )

        # Create expiring soon item
        soon_date = purchase_date + timedelta(days=2)
        InventoryItem.objects.create(
            product=product,
            purchase_date=purchase_date,
            expiry_date=soon_date,
            quantity_remaining=Decimal("1.0")
        )

        expired_items = InventoryItem.get_expired_items()
        expiring_soon_items = InventoryItem.get_expiring_soon(days=3)

        self.assertEqual(expired_items.count(), 1)
        self.assertEqual(expiring_soon_items.count(), 1)


@pytest.mark.unit
class ConsumptionEventModelTest(TestCase):
    """Test ConsumptionEvent model."""

    def setUp(self):
        self.product = Product.objects.create(name="Test Product")
        self.inventory_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=timezone.now().date(),
            quantity_remaining=Decimal("10.0")
        )

    def test_consumption_event_creation(self):
        """Test consumption event creation."""
        consumption = ConsumptionEvent.objects.create(
            inventory_item=self.inventory_item,
            consumed_qty=Decimal("2.5"),
            notes="Used in cooking"
        )

        self.assertEqual(str(consumption), "Consumed 2.5 of Test Product")
        self.assertEqual(consumption.consumed_qty, Decimal("2.5"))
        self.assertEqual(consumption.notes, "Used in cooking")


@pytest.mark.unit
class RuleModelTest(TestCase):
    """Test Rule model for business rules engine."""

    def test_rule_creation(self):
        """Test basic rule creation."""
        rule = Rule.objects.create(
            name="Dairy Expiry Rule",
            description="Set expiry for dairy products",
            condition={"field": "product.category.name", "operator": "equals", "value": "Nabiał"},
            action={"action_type": "set_expiry", "params": {"days": 7}},
            priority=10,
            is_active=True
        )

        self.assertEqual(str(rule), "Dairy Expiry Rule")
        self.assertEqual(rule.priority, 10)
        self.assertTrue(rule.is_active)
        self.assertEqual(rule.condition["value"], "Nabiał")


@pytest.mark.unit
class ModelIntegrationTest(TestCase):
    """Test integration between models."""

    def test_complete_receipt_workflow(self):
        """Test complete receipt to inventory workflow."""
        # Create category and product
        category = Category.objects.create(name="Nabiał", meta={"expiry_days": 7})
        product = Product.objects.create(name="Mleko UHT", category=category)

        # Create receipt with line item
        receipt = Receipt.objects.create(
            store_name="Test Store",
            total=Decimal("10.00"),
            status="completed"
        )

        line_item = ReceiptLineItem.objects.create(
            receipt=receipt,
            product_name="Mleko UHT",
            quantity=Decimal("2.0"),
            unit_price=Decimal("5.00"),
            line_total=Decimal("10.00"),
            matched_product=product
        )

        # Verify relationships
        self.assertEqual(receipt.line_items.count(), 1)
        self.assertEqual(line_item.receipt, receipt)
        self.assertEqual(line_item.matched_product, product)

    def test_inventory_lifecycle(self):
        """Test complete inventory item lifecycle."""
        product = Product.objects.create(name="Test Product")
        purchase_date = timezone.now().date()
        expiry_date = purchase_date + timedelta(days=7)

        # Create inventory item
        item = InventoryItem.objects.create(
            product=product,
            purchase_date=purchase_date,
            expiry_date=expiry_date,
            quantity_remaining=Decimal("10.0"),
            storage_location="fridge"
        )

        # Consume some quantity
        consumption1 = item.consume(Decimal("3.0"), "Breakfast")
        self.assertEqual(item.quantity_remaining, Decimal("7.0"))

        # Consume more
        consumption2 = item.consume(Decimal("2.0"), "Lunch")
        self.assertEqual(item.quantity_remaining, Decimal("5.0"))

        # Check consumption events
        self.assertEqual(item.consumption_events.count(), 2)

        # Verify consumption order (most recent first)
        consumptions = list(item.consumption_events.all())
        self.assertEqual(consumptions[0].consumed_qty, Decimal("2.0"))  # Most recent
        self.assertEqual(consumptions[1].consumed_qty, Decimal("3.0"))  # Older
