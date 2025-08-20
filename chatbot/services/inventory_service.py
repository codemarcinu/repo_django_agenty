"""
Inventory service for managing stock updates from receipt processing.
Implements automatic inventory updates, expiry calculations, and duplicate handling.
"""

import logging
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from inventory.models import (
    Category,
    ConsumptionEvent,
    InventoryItem,
    Product,
    Receipt,
    ReceiptLineItem,
)
from inventory.services.rule_engine_service import RuleEngineService # Import RuleEngineService

logger = logging.getLogger(__name__)


class InventoryService:
    """Service for managing inventory updates from receipts."""

    def __init__(self):
        # Default expiry days by category
        self.default_expiry_days = {
            "dairy": 7,
            "meat": 3,
            "vegetables": 5,
            "fruits": 7,
            "bread": 3,
            "beverages": 365,
            "cleaning": 730,
            "household": 730,
        }

    def process_receipt_for_inventory(self, receipt_id: int) -> tuple[bool, str | None]:
        """
        Process completed receipt and update inventory.

        Args:
            receipt_id: ID of the completed Receipt

        Returns:
            Tuple of (success, error_message)
        """
        try:
            receipt = Receipt.objects.get(id=receipt_id)

            if receipt.status != "completed":
                return (
                    False,
                    f"Receipt {receipt_id} is not completed (status: {receipt.status})",
                )

            # Get all line items from receipt
            line_items = receipt.line_items.all()

            if not line_items.exists():
                return False, f"Receipt {receipt_id} has no line items"

            logger.info(
                f"Processing {line_items.count()} line items for inventory update"
            )

            updated_items = []
            created_items = []
            errors = []

            with transaction.atomic():
                for line_item in line_items:
                    try:
                        purchase_date = receipt.purchased_at.date() if receipt.purchased_at else receipt.uploaded_at.date()
                        result = self._process_line_item_for_inventory(
                            line_item, purchase_date
                        )

                        if result["created"]:
                            created_items.extend(result["created"])
                        if result["updated"]:
                            updated_items.extend(result["updated"])
                        if result["errors"]:
                            errors.extend(result["errors"])

                    except Exception as e:
                        error_msg = f"Error processing line item '{line_item.product_name}': {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue

            # Log summary
            summary = f"Inventory update completed for receipt {receipt_id}: "
            summary += f"{len(created_items)} items created, {len(updated_items)} items updated"
            if errors:
                summary += f", {len(errors)} errors"

            logger.info(summary)

            if errors:
                return (
                    True,
                    f"Partially completed: {summary}. Errors: {'; '.join(errors[:3])}",
                )
            else:
                return True, summary

        except Receipt.DoesNotExist:
            error_msg = f"Receipt {receipt_id} not found"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Error processing receipt {receipt_id} for inventory: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def _process_line_item_for_inventory(
        self, line_item: ReceiptLineItem, purchase_date: date
    ) -> dict[str, list]:
        """Process a single line item for inventory update."""
        result = {"created": [], "updated": [], "errors": []}

        if not line_item.matched_product:
            # Skip ghost products (not matched to catalog)
            logger.debug(
                f"Skipping line item '{line_item.product_name}' - no matched product"
            )
            return result

        product = line_item.matched_product
        quantity = line_item.quantity

        # Calculate expiry date
        expiry_date = self._calculate_expiry_date(product, purchase_date)

        # Check for existing inventory items with same product and similar expiry date
        existing_items = self._find_similar_inventory_items(
            product, purchase_date, expiry_date
        )

        if existing_items:
            # Update existing item(s)
            for item in existing_items:
                old_quantity = item.quantity_remaining
                item.quantity_remaining += quantity
                item.save(update_fields=["quantity_remaining", "updated_at"])

                result["updated"].append(
                    {
                        "item": item,
                        "old_quantity": old_quantity,
                        "added_quantity": quantity,
                        "new_quantity": item.quantity_remaining,
                    }
                )

                logger.info(
                    f"Updated inventory item {item.id}: {old_quantity} + {quantity} = {item.quantity_remaining}"
                )
                break  # Only update first matching item
        else:
            # Create new inventory item
            storage_location = self._guess_storage_location(product)
            unit = self._guess_unit_from_product(line_item)

            new_item = InventoryItem.objects.create(
                product=product,
                purchase_date=purchase_date,
                expiry_date=expiry_date,
                quantity_remaining=quantity,
                unit=unit,
                storage_location=storage_location,
                batch_id=f"R{line_item.receipt.id}-L{line_item.id}",
            )

            # --- INTEGRACJA SILNIKA REGUŁ ---
            rule_engine = RuleEngineService()
            rule_engine.apply_rules(new_item) # Apply rules to the newly created item

            result["created"].append(
                {"item": new_item, "quantity": quantity, "expiry_date": expiry_date}
            )

            logger.info(
                f"Created inventory item {new_item.id}: {product.name} x{quantity}"
            )

        return result

    def _calculate_expiry_date(
        self, product: Product, purchase_date: date
    ) -> date | None:
        """
        Calculate expiry date for a product.
        """
        try:
            # First, check if product category has expiry days metadata
            if product.category and product.category.meta.get("expiry_days"):
                days = product.category.meta["expiry_days"]
                return purchase_date + timedelta(days=days)

            # Second, check category name against defaults
            if product.category:
                category_name = product.category.name.lower()
                for category_key, days in self.default_expiry_days.items():
                    if category_key in category_name:
                        return purchase_date + timedelta(days=days)

            # Third, guess from product name
            product_name = product.name.lower()

            # Dairy products
            if any(
                word in product_name
                for word in ["mleko", "milk", "jogurt", "yogurt", "ser", "cheese"]
            ):
                return purchase_date + timedelta(days=7)

            # Meat products
            if any(
                word in product_name
                for word in ["mięso", "meat", "kiełbasa", "sausage", "ham"]
            ):
                return purchase_date + timedelta(days=3)

            # Bread products
            if any(
                word in product_name for word in ["chleb", "bread", "bułka", "roll"]
            ):
                return purchase_date + timedelta(days=3)

            # Vegetables
            if any(
                word in product_name
                for word in ["warzywa", "vegetables", "marchew", "carrot"]
            ):
                return purchase_date + timedelta(days=5)

            # Fruits
            if any(
                word in product_name
                for word in ["owoce", "fruits", "jabłko", "apple", "banan"]
            ):
                return purchase_date + timedelta(days=7)

            # Default: 30 days
            return purchase_date + timedelta(days=30)

        except Exception as e:
            logger.warning(f"Error calculating expiry date for {product.name}: {e}")
            return purchase_date + timedelta(days=30)  # Safe default

    def _find_similar_inventory_items(
        self, product: Product, purchase_date: date, expiry_date: date | None
    ) -> list[InventoryItem]:
        """Find existing inventory items that can be merged."""
        # Look for items with same product and similar dates
        date_range = timedelta(days=3)  # Allow 3-day difference

        queryset = InventoryItem.objects.filter(
            product=product,
            quantity_remaining__gt=0,  # Only items with remaining stock
            purchase_date__range=(
                purchase_date - date_range,
                purchase_date + date_range,
            ),
        )

        # If we have expiry date, filter by similar expiry dates
        if expiry_date:
            queryset = queryset.filter(
                expiry_date__range=(expiry_date - date_range, expiry_date + date_range)
            )

        return list(queryset[:1])  # Return at most one item for merging

    def _guess_storage_location(self, product: Product) -> str:
        """Guess storage location based on product category and name."""
        if not product.category:
            return "pantry"  # Default

        category_name = product.category.name.lower()
        product_name = product.name.lower()

        # Dairy products -> fridge
        if any(
            word in category_name or word in product_name
            for word in [
                "dairy",
                "mleko",
                "milk",
                "jogurt",
                "yogurt",
                "ser",
                "cheese",
                "masło",
                "butter",
            ]
        ):
            return "fridge"

        # Meat products -> fridge
        if any(
            word in category_name or word in product_name
            for word in ["meat", "mięso", "kiełbasa", "sausage", "wędlina", "ham"]
        ):
            return "fridge"

        # Frozen products -> freezer
        if any(
            word in product_name for word in ["mrożon", "frozen", "lody", "ice cream"]
        ):
            return "freezer"

        # Vegetables -> fridge
        if "vegetables" in category_name or any(
            word in product_name
            for word in ["warzywa", "marchew", "carrot", "sałata", "lettuce"]
        ):
            return "fridge"

        # Cleaning products -> cabinet
        if "cleaning" in category_name or any(
            word in product_name for word in ["detergent", "mydło", "soap", "proszek"]
        ):
            return "cabinet"

        # Default -> pantry
        return "pantry"

    def _guess_unit_from_product(self, line_item: ReceiptLineItem) -> str:
        """Guess unit from product name and context."""
        product_name = line_item.product_name.lower()

        # Weight indicators
        if any(unit in product_name for unit in ["kg", "kilogram"]):
            return "kg"
        if any(unit in product_name for unit in ["g", "gram"]):
            return "g"

        # Volume indicators
        if any(unit in product_name for unit in ["l", "litr", "liter"]):
            return "l"
        if any(unit in product_name for unit in ["ml", "millilitr"]):
            return "ml"

        # Package indicators
        if any(word in product_name for word in ["opak", "pack", "pudełko", "box"]):
            return "opak"

        # Default to pieces
        return "szt"

    def get_inventory_summary(self) -> dict[str, any]:
        """Get current inventory summary statistics."""
        try:
            total_items = InventoryItem.objects.count()
            active_items = InventoryItem.objects.filter(
                quantity_remaining__gt=0
            ).count()

            # Expiring items (within 2 days)
            soon_expiring = InventoryItem.objects.filter(
                quantity_remaining__gt=0,
                expiry_date__lte=timezone.now().date() + timedelta(days=2),
                expiry_date__gte=timezone.now().date(),
            ).count()

            # Expired items
            expired = InventoryItem.objects.filter(
                quantity_remaining__gt=0, expiry_date__lt=timezone.now().date()
            ).count()

            # Low stock items
            from django.db.models import F

            low_stock = InventoryItem.objects.filter(
                quantity_remaining__gt=0,
                quantity_remaining__lte=F("product__reorder_point"),
            ).count()

            # Storage location breakdown
            storage_counts = {}
            for location, _ in InventoryItem.STORAGE_CHOICES:
                count = InventoryItem.objects.filter(
                    storage_location=location, quantity_remaining__gt=0
                ).count()
                storage_counts[location] = count

            return {
                "total_items": total_items,
                "active_items": active_items,
                "soon_expiring": soon_expiring,
                "expired": expired,
                "low_stock": low_stock,
                "storage_breakdown": storage_counts,
                "last_updated": timezone.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting inventory summary: {e}")
            return {}

    def get_expiring_items(self, days: int = 7) -> list[InventoryItem]:
        """Get items expiring within specified days."""
        try:
            cutoff_date = timezone.now().date() + timedelta(days=days)

            return list(
                InventoryItem.objects.filter(
                    quantity_remaining__gt=0,
                    expiry_date__lte=cutoff_date,
                    expiry_date__gte=timezone.now().date(),
                )
                .select_related("product", "product__category")
                .order_by("expiry_date")
            )

        except Exception as e:
            logger.error(f"Error getting expiring items: {e}")
            return []

    def get_low_stock_items(self) -> list[InventoryItem]:
        """Get items with low stock (below reorder point)."""
        try:
            from django.db.models import F

            return list(
                InventoryItem.objects.filter(
                    quantity_remaining__gt=0,
                    quantity_remaining__lte=F("product__reorder_point"),
                )
                .select_related("product", "product__category")
                .order_by("quantity_remaining")
            )

        except Exception as e:
            logger.error(f"Error getting low stock items: {e}")
            return []

    def get_expired_items(self) -> list[InventoryItem]:
        """Get items that have already expired."""
        try:
            return list(
                InventoryItem.objects.filter(
                    quantity_remaining__gt=0, expiry_date__lt=timezone.now().date()
                )
                .select_related("product", "product__category")
                .order_by("expiry_date")
            )

        except Exception as e:
            logger.error(f"Error getting expired items: {e}")
            return []

    def cleanup_empty_items(self) -> int:
        """Remove inventory items with zero remaining quantity."""
        try:
            deleted_count, _ = InventoryItem.objects.filter(
                quantity_remaining__lte=0
            ).delete()

            logger.info(f"Cleaned up {deleted_count} empty inventory items")
            return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up empty items: {e}")
            return 0

    def bulk_update_expiry_dates(self) -> tuple[int, int]:
        """Bulk update missing expiry dates for inventory items."""
        try:
            items_without_expiry = InventoryItem.objects.filter(
                expiry_date__isnull=True, quantity_remaining__gt=0
            )

            updated_count = 0
            error_count = 0

            for item in items_without_expiry:
                try:
                    new_expiry = self._calculate_expiry_date(
                        item.product, item.purchase_date
                    )
                    if new_expiry:
                        item.expiry_date = new_expiry
                        item.save(update_fields=["expiry_date"])
                        updated_count += 1
                except Exception as e:
                    logger.error(f"Error updating expiry for item {item.id}: {e}")
                    error_count += 1

            logger.info(
                f"Bulk expiry update: {updated_count} updated, {error_count} errors"
            )
            return updated_count, error_count

        except Exception as e:
            logger.error(f"Error in bulk expiry update: {e}")
            return 0, 1

    def get_top_spending_categories(self, days: int = 30) -> list[dict]:
        """Get top 5 categories by spending in last N days."""
        try:
            from django.db.models import Count, Sum

            cutoff_date = date.today() - timedelta(days=days)

            category_spending = (
                Receipt.objects.filter(
                    purchased_at__gte=cutoff_date, status="completed"
                )
                .values("line_items__matched_product__category__name")
                .annotate(
                    total_spent=Sum("line_items__line_total"),
                    item_count=Count("line_items"),
                )
                .order_by("-total_spent")[:5]
            )

            result = []
            for item in category_spending:
                category_name = (
                    item["line_items__matched_product__category__name"]
                    or "Uncategorized"
                )
                result.append(
                    {
                        "category": category_name,
                        "total_spent": float(item["total_spent"] or 0),
                        "item_count": item["item_count"],
                        "avg_item_price": float(item["total_spent"] or 0)
                        / max(item["item_count"], 1),
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Error getting top spending categories: {e}")
            return []

    def get_consumption_heatmap_data(self, days: int = 30) -> dict:
        """Get consumption data for heatmap visualization."""
        try:
            cutoff_date = date.today() - timedelta(days=days)

            # Get all consumption events and process them in Python
            consumption_events = list(
                ConsumptionEvent.objects.filter(consumed_at__gte=cutoff_date)
                .select_related("inventory_item__product__category")
                .values(
                    "consumed_at",
                    "consumed_qty",
                    "inventory_item__product__category__name",
                )
            )

            # Process data to create heatmap
            consumption_data = {}

            # Initialize heatmap data structure
            weekdays = [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ]
            categories = list(Category.objects.values_list("name", flat=True))

            heatmap = {}
            for category in categories:
                heatmap[category] = dict.fromkeys(weekdays, 0)

            # Process events and fill heatmap
            for event in consumption_events:
                category = (
                    event["inventory_item__product__category__name"] or "Uncategorized"
                )
                consumed_at = event["consumed_at"]
                consumed_qty = float(event["consumed_qty"] or 0)

                # Get weekday (0=Monday, 6=Sunday in Python)
                weekday_num = consumed_at.weekday()
                # Convert to our format (0=Sunday, 6=Saturday)
                weekday_index = (weekday_num + 1) % 7
                weekday_name = weekdays[weekday_index]

                if category not in heatmap:
                    heatmap[category] = dict.fromkeys(weekdays, 0)
                    categories.append(category)

                heatmap[category][weekday_name] += consumed_qty

            return {
                "heatmap_data": heatmap,
                "weekdays": weekdays,
                "categories": list(heatmap.keys()),
                "period_days": days,
                "last_updated": timezone.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting consumption heatmap data: {e}")
            return {
                "heatmap_data": {},
                "weekdays": [],
                "categories": [],
                "period_days": days,
                "last_updated": timezone.now().isoformat(),
            }

    def get_recent_activity(self, days: int = 7) -> dict:
        """Get recent activity summary for dashboard."""
        try:
            cutoff_date = date.today() - timedelta(days=days)

            recent_receipts = Receipt.objects.filter(
                purchased_at__gte=cutoff_date, status="completed"
            ).count()

            # Recent consumption events
            recent_consumption = ConsumptionEvent.objects.filter(
                consumed_at__gte=cutoff_date
            ).count()

            # New products added
            new_products = Product.objects.filter(created_at__gte=cutoff_date).count()

            # Items that expired recently
            recently_expired = InventoryItem.objects.filter(
                expiry_date__gte=cutoff_date,
                expiry_date__lt=date.today(),
                quantity_remaining__gt=0,
            ).count()

            return {
                "recent_receipts": recent_receipts,
                "recent_consumption": recent_consumption,
                "new_products": new_products,
                "recently_expired": recently_expired,
                "period_days": days,
            }

        except Exception as e:
            logger.error(f"Error getting recent activity: {e}")
            return {
                "recent_receipts": 0,
                "recent_consumption": 0,
                "new_products": 0,
                "recently_expired": 0,
                "period_days": days,
            }


def get_inventory_service() -> InventoryService:
    """Get default inventory service instance."""
    return InventoryService()