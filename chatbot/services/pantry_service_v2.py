"""
Pantry management service using InventoryItem model.
Replacement for the old PantryService that used PantryItem.
Part of the fat model, thin view pattern implementation.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from inventory.models import Category, InventoryItem, Product

from .exceptions import (
    DatabaseError,
    InsufficientStockError,
    InventoryError,
    InventoryNotFoundError,
    InventoryValidationError,
)

logger = logging.getLogger(__name__)


class PantryServiceV2:
    """Service class for pantry management operations using InventoryItem"""

    def add_or_update_item(
        self,
        name: str,
        quantity: float,
        unit: str = "szt",
        expiry_date: date | None = None,
    ) -> InventoryItem:
        """
        Add new item or update existing item quantity.

        Args:
            name: Product name
            quantity: Quantity to add
            unit: Unit of measurement  
            expiry_date: Optional expiry date

        Returns:
            InventoryItem: Created or updated inventory item
            
        Raises:
            InventoryValidationError: If input validation fails
            DatabaseError: If database operation fails
            InventoryError: For other inventory-related errors
        """
        # Input validation
        if not name or not isinstance(name, str) or not name.strip():
            raise InventoryValidationError("Product name is required and must be non-empty")

        if not isinstance(quantity, (int, float)) or quantity <= 0:
            raise InventoryValidationError("Quantity must be a positive number")

        if not unit or not isinstance(unit, str) or not unit.strip():
            raise InventoryValidationError("Unit is required and must be non-empty")

        if expiry_date and not isinstance(expiry_date, date):
            raise InventoryValidationError("Expiry date must be a valid date object")

        try:
            quantity_decimal = Decimal(str(quantity))
        except (InvalidOperation, ValueError) as e:
            raise InventoryValidationError(f"Invalid quantity format: {quantity}") from e

        try:
            with transaction.atomic():
                # Find or create product
                try:
                    product, created = Product.objects.get_or_create(
                        name__iexact=name.strip(),
                        defaults={
                            'name': name.strip(),
                            'category': self._get_default_category(),
                            'is_active': True,
                            'reorder_point': Decimal('1.000')
                        }
                    )
                except IntegrityError as e:
                    raise DatabaseError(f"Failed to create product '{name}': Database constraint violation") from e

                if created:
                    logger.info(f"Created new product: {product.name}")

                # Find existing inventory item in pantry storage
                existing_item = InventoryItem.objects.filter(
                    product=product,
                    storage_location='pantry',
                    quantity_remaining__gt=0
                ).first()

                if existing_item:
                    # Update existing item
                    try:
                        existing_item.add_quantity(quantity)

                        # Update expiry date if provided and item doesn't have one
                        if expiry_date and not existing_item.expiry_date:
                            existing_item.expiry_date = expiry_date
                            existing_item.save(update_fields=['expiry_date', 'updated_at'])

                        logger.info(f"Updated item {existing_item.id}: +{quantity} {unit}")
                        return existing_item
                    except (DjangoValidationError, IntegrityError) as e:
                        raise DatabaseError(f"Failed to update inventory item: {e}") from e
                else:
                    # Create new inventory item
                    try:
                        new_item = InventoryItem.objects.create(
                            product=product,
                            purchase_date=timezone.now().date(),
                            expiry_date=expiry_date,
                            quantity_remaining=quantity_decimal,
                            unit=unit.strip(),
                            storage_location='pantry',
                            batch_id=f"MANUAL-{timezone.now().strftime('%Y%m%d-%H%M%S')}"
                        )

                        logger.info(f"Created new inventory item {new_item.id}: {quantity} {unit}")
                        return new_item
                    except (DjangoValidationError, IntegrityError) as e:
                        raise DatabaseError(f"Failed to create inventory item: {e}") from e

        except (InventoryValidationError, DatabaseError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            error_msg = f"Unexpected error adding/updating pantry item '{name}': {e}"
            logger.error(error_msg, exc_info=True)
            raise InventoryError(error_msg) from e

    def remove_item(self, item_id: int, quantity: float = None) -> bool:
        """
        Remove item or reduce quantity.

        Args:
            item_id: InventoryItem ID
            quantity: Quantity to remove (None = remove completely)

        Returns:
            bool: Success status
            
        Raises:
            InventoryNotFoundError: If item is not found
            InventoryValidationError: If validation fails
            InsufficientStockError: If insufficient stock for removal
            DatabaseError: If database operation fails
        """
        if not isinstance(item_id, int) or item_id <= 0:
            raise InventoryValidationError("Item ID must be a positive integer")

        if quantity is not None and (not isinstance(quantity, (int, float)) or quantity <= 0):
            raise InventoryValidationError("Quantity must be a positive number")

        try:
            item = InventoryItem.objects.get(id=item_id, storage_location='pantry')
        except InventoryItem.DoesNotExist:
            raise InventoryNotFoundError(f"Pantry item {item_id} not found")

        try:
            with transaction.atomic():
                if quantity is None:
                    # Remove completely
                    item.quantity_remaining = Decimal('0')
                    item.save(update_fields=['quantity_remaining', 'updated_at'])
                    logger.info(f"Removed item {item_id} completely")
                else:
                    # Check sufficient stock
                    current_quantity = float(item.quantity_remaining)
                    if quantity > current_quantity:
                        raise InsufficientStockError(
                            f"Insufficient stock: requested {quantity}, available {current_quantity}"
                        )

                    # Reduce quantity
                    if quantity >= current_quantity:
                        item.quantity_remaining = Decimal('0')
                    else:
                        item.subtract_quantity(quantity)
                    logger.info(f"Reduced item {item_id} by {quantity}")

                return True

        except (InventoryNotFoundError, InventoryValidationError, InsufficientStockError):
            # Re-raise our custom exceptions
            raise
        except (DjangoValidationError, IntegrityError) as e:
            raise DatabaseError(f"Failed to update inventory item {item_id}: {e}") from e
        except Exception as e:
            error_msg = f"Unexpected error removing pantry item {item_id}: {e}"
            logger.error(error_msg, exc_info=True)
            raise InventoryError(error_msg) from e

    def get_all_items(self) -> list[InventoryItem]:
        """Get all active pantry items"""
        return list(
            InventoryItem.objects.filter(
                storage_location='pantry',
                quantity_remaining__gt=0
            )
            .select_related('product', 'product__category')
            .order_by('product__name')
        )

    def get_expired_items(self) -> list[InventoryItem]:
        """Get expired pantry items"""
        return list(
            InventoryItem.objects.filter(
                storage_location='pantry',
                quantity_remaining__gt=0,
                expiry_date__lt=timezone.now().date()
            )
            .select_related('product', 'product__category')
            .order_by('expiry_date')
        )

    def get_expiring_soon(self, days: int = 7) -> list[InventoryItem]:
        """Get items expiring within specified days"""
        cutoff_date = timezone.now().date() + timedelta(days=days)

        return list(
            InventoryItem.objects.filter(
                storage_location='pantry',
                quantity_remaining__gt=0,
                expiry_date__gte=timezone.now().date(),
                expiry_date__lte=cutoff_date
            )
            .select_related('product', 'product__category')
            .order_by('expiry_date')
        )

    def get_low_stock_items(self, threshold: float = 1.0) -> list[InventoryItem]:
        """Get items with low stock"""
        return list(
            InventoryItem.objects.filter(
                storage_location='pantry',
                quantity_remaining__gt=0,
                quantity_remaining__lte=Decimal(str(threshold))
            )
            .select_related('product', 'product__category')
            .order_by('quantity_remaining')
        )

    def get_statistics(self) -> dict:
        """Get pantry statistics"""
        pantry_items = InventoryItem.objects.filter(
            storage_location='pantry',
            quantity_remaining__gt=0
        )

        today = timezone.now().date()

        expired_count = pantry_items.filter(expiry_date__lt=today).count()
        expiring_soon_count = pantry_items.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=7)
        ).count()
        low_stock_count = pantry_items.filter(
            quantity_remaining__lte=Decimal('1.0')
        ).count()

        from django.db import models

        return {
            "total_items": pantry_items.count(),
            "expired_count": expired_count,
            "expiring_soon_count": expiring_soon_count,
            "low_stock_count": low_stock_count,
            "average_quantity": float(
                pantry_items.aggregate(
                    avg=models.Avg("quantity_remaining")
                )["avg"] or 0
            ),
        }

    def search_items(self, query: str) -> list[InventoryItem]:
        """Search pantry items by product name"""
        return list(
            InventoryItem.objects.filter(
                storage_location='pantry',
                quantity_remaining__gt=0,
                product__name__icontains=query
            )
            .select_related('product', 'product__category')
            .order_by('product__name')
        )

    def _get_default_category(self) -> Category:
        """Get or create default category for manual pantry items"""
        category, created = Category.objects.get_or_create(
            name="Manual Pantry Items",
            defaults={"meta": {"expiry_days": 30}}
        )
        return category


# Service instance
def get_pantry_service() -> PantryServiceV2:
    """Get pantry service instance"""
    return PantryServiceV2()
