import json
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from inventory.models import (
    Category, Product, Receipt, ReceiptLineItem,
    InventoryItem
)


@pytest.mark.unit
class DashboardViewTest(TestCase):
    """Test inventory dashboard views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )

    def test_dashboard_view_loads(self):
        """Test dashboard view loads successfully."""
        response = self.client.get(reverse("inventory:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertIn("summary", response.context)
        self.assertIn("expiring_items", response.context)
        self.assertIn("low_stock_items", response.context)

    def test_monitoring_dashboard_view(self):
        """Test monitoring dashboard view loads."""
        response = self.client.get(reverse("inventory:monitoring_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monitoring")
        self.assertIn("status_counts_json", response.context)
        self.assertIn("step_counts_json", response.context)


@pytest.mark.unit
class InventoryListViewTest(TestCase):
    """Test inventory list view with filtering."""

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(
            name="Test Product",
            category=self.category
        )
        self.inventory_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=timezone.now().date(),
            quantity_remaining=Decimal("10.0"),
            storage_location="fridge"
        )

    def test_inventory_list_view_loads(self):
        """Test inventory list view loads successfully."""
        response = self.client.get(reverse("inventory:inventory_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Product")
        self.assertIn("items", response.context)
        self.assertIn("categories", response.context)

    def test_inventory_list_search_filter(self):
        """Test inventory list search filtering."""
        response = self.client.get(
            reverse("inventory:inventory_list"),
            {"search": "Test Product"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["items"]), 1)

        # Test no results search
        response = self.client.get(
            reverse("inventory:inventory_list"),
            {"search": "Nonexistent Product"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["items"]), 0)

    def test_inventory_list_location_filter(self):
        """Test inventory list location filtering."""
        response = self.client.get(
            reverse("inventory:inventory_list"),
            {"location": "fridge"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["items"]), 1)

        # Test different location
        response = self.client.get(
            reverse("inventory:inventory_list"),
            {"location": "pantry"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["items"]), 0)

    def test_inventory_list_category_filter(self):
        """Test inventory list category filtering."""
        response = self.client.get(
            reverse("inventory:inventory_list"),
            {"category": self.category.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["items"]), 1)

    def test_inventory_list_status_filters(self):
        """Test inventory list status-based filtering."""
        # Test expiring items filter
        future_date = timezone.now().date() + timedelta(days=3)
        expiring_item = InventoryItem.objects.create(
            product=Product.objects.create(name="Expiring Product"),
            purchase_date=timezone.now().date(),
            expiry_date=future_date,
            quantity_remaining=Decimal("5.0")
        )

        response = self.client.get(
            reverse("inventory:inventory_list"),
            {"status": "expiring"}
        )

        self.assertEqual(response.status_code, 200)
        # Should include the expiring item
        self.assertTrue(len(response.context["items"]) >= 1)

        # Test expired items filter
        past_date = timezone.now().date() - timedelta(days=1)
        expired_item = InventoryItem.objects.create(
            product=Product.objects.create(name="Expired Product"),
            purchase_date=timezone.now().date(),
            expiry_date=past_date,
            quantity_remaining=Decimal("1.0")
        )

        response = self.client.get(
            reverse("inventory:inventory_list"),
            {"status": "expired"}
        )

        self.assertEqual(response.status_code, 200)
        # Should include the expired item
        self.assertTrue(len(response.context["items"]) >= 1)

        # Test low stock filter
        low_stock_product = Product.objects.create(
            name="Low Stock Product",
            reorder_point=Decimal("2.0")
        )
        low_stock_item = InventoryItem.objects.create(
            product=low_stock_product,
            purchase_date=timezone.now().date(),
            quantity_remaining=Decimal("1.0")  # Below reorder point
        )

        response = self.client.get(
            reverse("inventory:inventory_list"),
            {"status": "low_stock"}
        )

        self.assertEqual(response.status_code, 200)
        # Should include the low stock item
        self.assertTrue(len(response.context["items"]) >= 1)


@pytest.mark.unit
class ProductListViewTest(TestCase):
    """Test product list view with filtering."""

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(
            name="Test Product",
            brand="Test Brand",
            category=self.category
        )

    def test_product_list_view_loads(self):
        """Test product list view loads successfully."""
        response = self.client.get(reverse("inventory:product_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Product")
        self.assertIn("products", response.context)
        self.assertIn("categories", response.context)

    def test_product_list_search_filter(self):
        """Test product list search filtering."""
        response = self.client.get(
            reverse("inventory:product_list"),
            {"search": "Test Product"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["products"]), 1)

    def test_product_list_category_filter(self):
        """Test product list category filtering."""
        response = self.client.get(
            reverse("inventory:product_list"),
            {"category": self.category.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["products"]), 1)


@pytest.mark.unit
class ProductDetailViewTest(TestCase):
    """Test product detail view."""

    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(
            name="Test Product",
            brand="Test Brand"
        )

    def test_product_detail_view_loads(self):
        """Test product detail view loads successfully."""
        response = self.client.get(
            reverse("inventory:product_detail", kwargs={"pk": self.product.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["product"], self.product)


@pytest.mark.unit
class ReceiptListViewTest(TestCase):
    """Test receipt list view with filtering."""

    def setUp(self):
        self.client = Client()
        self.receipt = Receipt.objects.create(
            store_name="Test Store",
            status="completed"
        )

    def test_receipt_list_view_loads(self):
        """Test receipt list view loads successfully."""
        response = self.client.get(reverse("inventory:receipt_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Store")
        self.assertIn("receipts", response.context)

    def test_receipt_list_search_filter(self):
        """Test receipt list search filtering."""
        response = self.client.get(
            reverse("inventory:receipt_list"),
            {"search": "Test Store"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["receipts"]), 1)

    def test_receipt_list_status_filter(self):
        """Test receipt list status filtering."""
        response = self.client.get(
            reverse("inventory:receipt_list"),
            {"status": "completed"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["receipts"]), 1)


@pytest.mark.unit
class ReceiptDetailViewTest(TestCase):
    """Test receipt detail view."""

    def setUp(self):
        self.client = Client()
        self.receipt = Receipt.objects.create(
            store_name="Test Store",
            status="completed"
        )

    def test_receipt_detail_view_loads(self):
        """Test receipt detail view loads successfully."""
        response = self.client.get(
            reverse("inventory:receipt_detail", kwargs={"pk": self.receipt.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["receipt"], self.receipt)
        self.assertIn("line_items", response.context)


@pytest.mark.unit
class ExpiringItemsViewTest(TestCase):
    """Test expiring items view."""

    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(name="Test Product")
        self.expiring_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timedelta(days=3),
            quantity_remaining=Decimal("5.0")
        )

    def test_expiring_items_view_loads(self):
        """Test expiring items view loads successfully."""
        response = self.client.get(reverse("inventory:expiring_items"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.context)
        self.assertIn("days", response.context)

    def test_expiring_items_custom_days(self):
        """Test expiring items view with custom days parameter."""
        response = self.client.get(
            reverse("inventory:expiring_items"),
            {"days": "14"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["days"], 14)


@pytest.mark.unit
class LowStockItemsViewTest(TestCase):
    """Test low stock items view."""

    def setUp(self):
        self.client = Client()
        self.low_stock_product = Product.objects.create(
            name="Low Stock Product",
            reorder_point=Decimal("2.0")
        )
        self.low_stock_item = InventoryItem.objects.create(
            product=self.low_stock_product,
            purchase_date=timezone.now().date(),
            quantity_remaining=Decimal("1.0")  # Below reorder point
        )

    def test_low_stock_items_view_loads(self):
        """Test low stock items view loads successfully."""
        response = self.client.get(reverse("inventory:low_stock_items"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.context)


@pytest.mark.unit
class InventoryByLocationViewTest(TestCase):
    """Test inventory by location view."""

    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(name="Fridge Product")
        self.fridge_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=timezone.now().date(),
            quantity_remaining=Decimal("5.0"),
            storage_location="fridge"
        )

    def test_inventory_by_location_view_loads(self):
        """Test inventory by location view loads successfully."""
        response = self.client.get(
            reverse("inventory:inventory_by_location", kwargs={"location": "fridge"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("items", response.context)
        self.assertIn("location", response.context)
        self.assertEqual(response.context["location"], "fridge")


@pytest.mark.unit
class CategoryListViewTest(TestCase):
    """Test category list view."""

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name="Test Category")

    def test_category_list_view_loads(self):
        """Test category list view loads successfully."""
        response = self.client.get(reverse("inventory:category_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("categories", response.context)
        self.assertEqual(len(response.context["categories"]), 1)


@pytest.mark.unit
class ReceiptProcessingStatusViewTest(TestCase):
    """Test receipt processing status API view."""

    def setUp(self):
        self.client = Client()
        self.receipt = Receipt.objects.create(
            store_name="Test Store",
            status="processing"
        )

    def test_receipt_processing_status_valid(self):
        """Test receipt processing status with valid receipt."""
        response = self.client.get(
            reverse("inventory:receipt_processing_status", kwargs={"receipt_id": self.receipt.pk})
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("receipt_id", data)
        self.assertIn("status", data)
        self.assertEqual(data["receipt_id"], self.receipt.pk)

    def test_receipt_processing_status_invalid(self):
        """Test receipt processing status with invalid receipt ID."""
        response = self.client.get(
            reverse("inventory:receipt_processing_status", kwargs={"receipt_id": 99999})
        )

        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)


@pytest.mark.unit
class ReceiptReviewViewTest(TestCase):
    """Test receipt review view."""

    def setUp(self):
        self.client = Client()
        self.receipt = Receipt.objects.create(
            store_name="Test Store",
            status="review_pending"
        )

    def test_receipt_review_view_loads(self):
        """Test receipt review view loads successfully."""
        response = self.client.get(
            reverse("inventory:receipt_review", kwargs={"receipt_id": self.receipt.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("receipt", response.context)
        self.assertIn("receipt_json", response.context)
        self.assertIn("line_items_json", response.context)

    def test_receipt_review_view_invalid_receipt(self):
        """Test receipt review view with invalid receipt ID."""
        response = self.client.get(
            reverse("inventory:receipt_review", kwargs={"receipt_id": 99999})
        )

        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)


@pytest.mark.unit
class CorrectReceiptDataViewTest(TestCase):
    """Test correct receipt data API view."""

    def setUp(self):
        self.client = Client()
        self.receipt = Receipt.objects.create(
            store_name="Test Store",
            status="review_pending"
        )

    def test_correct_receipt_data_post(self):
        """Test correcting receipt data via POST."""
        line_item = ReceiptLineItem.objects.create(
            receipt=self.receipt,
            product_name="Test Product",
            quantity=Decimal("1.0"),
            unit_price=Decimal("5.00"),
            line_total=Decimal("5.00")
        )

        data = {
            "line_items": [
                {
                    "id": line_item.id,
                    "product_name": "Updated Product",
                    "quantity": "2.0",
                    "unit_price": "6.00",
                    "line_total": "12.00",
                    "is_deleted": False
                }
            ]
        }

        response = self.client.post(
            reverse("inventory:correct_receipt_data", kwargs={"receipt_id": self.receipt.pk}),
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "success")

        # Check that receipt is now completed
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "completed")

    def test_correct_receipt_data_invalid_receipt(self):
        """Test correcting receipt data with invalid receipt ID."""
        data = {"line_items": []}

        response = self.client.post(
            reverse("inventory:correct_receipt_data", kwargs={"receipt_id": 99999}),
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)
        result = response.json()
        self.assertIn("error", result)

    def test_correct_receipt_data_invalid_json(self):
        """Test correcting receipt data with invalid JSON."""
        response = self.client.post(
            reverse("inventory:correct_receipt_data", kwargs={"receipt_id": self.receipt.pk}),
            data="invalid json",
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        result = response.json()
        self.assertIn("error", result)

    def test_correct_receipt_data_get_method(self):
        """Test that GET method is not allowed for correct receipt data."""
        response = self.client.get(
            reverse("inventory:correct_receipt_data", kwargs={"receipt_id": self.receipt.pk})
        )

        self.assertEqual(response.status_code, 405)
        result = response.json()
        self.assertIn("error", result)


@pytest.mark.unit
class GetMonitoringDataViewTest(TestCase):
    """Test get monitoring data API view."""

    def setUp(self):
        self.client = Client()

    def test_get_monitoring_data_get(self):
        """Test getting monitoring data via GET."""
        # Create some test receipts with different statuses
        Receipt.objects.create(status="completed")
        Receipt.objects.create(status="pending")
        Receipt.objects.create(status="error")

        response = self.client.get(reverse("inventory:get_monitoring_data"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status_counts", data)
        self.assertIn("step_counts", data)
        self.assertIn("error_receipts", data)
        self.assertIn("total_pending", data)
        self.assertIn("total_processing", data)
        self.assertIn("total_errors", data)

        # Check that status counts include our test receipts
        self.assertEqual(data["status_counts"]["completed"], 1)
        self.assertEqual(data["status_counts"]["pending"], 1)
        self.assertEqual(data["status_counts"]["error"], 1)

    def test_get_monitoring_data_post_method(self):
        """Test that POST method is not allowed for monitoring data."""
        response = self.client.post(reverse("inventory:get_monitoring_data"))

        self.assertEqual(response.status_code, 405)
        result = response.json()
        self.assertIn("error", result)


@pytest.mark.integration
class ViewIntegrationTest(TestCase):
    """Test integration between views and models."""

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name="Integration Category")
        self.product = Product.objects.create(
            name="Integration Product",
            category=self.category
        )
        self.inventory_item = InventoryItem.objects.create(
            product=self.product,
            purchase_date=timezone.now().date(),
            quantity_remaining=Decimal("10.0"),
            storage_location="fridge"
        )

    def test_dashboard_inventory_service_integration(self):
        """Test that dashboard integrates with inventory service."""
        with patch('inventory.views.get_inventory_service') as mock_service:
            mock_inventory_service = MagicMock()
            mock_service.return_value = mock_inventory_service

            # Mock the service methods
            mock_inventory_service.get_inventory_summary.return_value = {"total_items": 1}
            mock_inventory_service.get_expiring_items.return_value = [self.inventory_item]
            mock_inventory_service.get_low_stock_items.return_value = []

            response = self.client.get(reverse("inventory:dashboard"))

            self.assertEqual(response.status_code, 200)
            # Verify service methods were called
            mock_inventory_service.get_inventory_summary.assert_called_once()
            mock_inventory_service.get_expiring_items.assert_called_once()
            mock_inventory_service.get_low_stock_items.assert_called_once()

    def test_complete_inventory_workflow_view(self):
        """Test complete workflow through views."""
        # Create a product
        product = Product.objects.create(
            name="Workflow Product",
            category=self.category
        )

        # Add to inventory
        inventory_item = InventoryItem.objects.create(
            product=product,
            purchase_date=timezone.now().date(),
            quantity_remaining=Decimal("5.0"),
            storage_location="pantry"
        )

        # Test inventory list view shows the item
        response = self.client.get(reverse("inventory:inventory_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workflow Product")

        # Test product detail view
        response = self.client.get(
            reverse("inventory:product_detail", kwargs={"pk": product.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["product"], product)
