"""
Pantry management service implementing business logic for pantry operations.
Part of the fat model, thin view pattern implementation.
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import date, timedelta

from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from ..models import PantryItem

logger = logging.getLogger(__name__)


class PantryService:
    """Service class for pantry management operations"""
    
    def add_or_update_item(
        self, 
        name: str, 
        quantity: float, 
        unit: str = 'szt.',
        expiry_date: Optional[date] = None
    ) -> PantryItem:
        """
        Add new item or update existing item quantity.
        
        Args:
            name: Product name
            quantity: Quantity to add
            unit: Unit of measurement
            expiry_date: Optional expiry date
            
        Returns:
            PantryItem instance
        """
        try:
            with transaction.atomic():
                item, created = PantryItem.objects.get_or_create(
                    name=name,
                    defaults={
                        'quantity': quantity,
                        'unit': unit,
                        'expiry_date': expiry_date
                    }
                )
                
                if not created:
                    # If item exists, add to existing quantity
                    item.add_quantity(quantity)
                    # Update expiry date if provided and current is None or later
                    if expiry_date and (not item.expiry_date or expiry_date < item.expiry_date):
                        item.expiry_date = expiry_date
                        item.save()
                
                logger.info(f"{'Added' if created else 'Updated'} pantry item: {name}")
                return item
                
        except Exception as e:
            logger.error(f"Error adding/updating pantry item {name}: {e}")
            raise
    
    def remove_item(self, item_id: int) -> bool:
        """
        Remove item from pantry.
        
        Args:
            item_id: ID of item to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        try:
            item = PantryItem.objects.get(id=item_id)
            item_name = item.name
            item.delete()
            logger.info(f"Removed pantry item: {item_name}")
            return True
            
        except PantryItem.DoesNotExist:
            logger.warning(f"Pantry item {item_id} not found for removal")
            return False
        except Exception as e:
            logger.error(f"Error removing pantry item {item_id}: {e}")
            return False
    
    def update_item_quantity(self, item_id: int, new_quantity: float) -> bool:
        """
        Update item quantity.
        
        Args:
            item_id: ID of item to update
            new_quantity: New quantity value
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            item = PantryItem.objects.get(id=item_id)
            old_quantity = item.quantity
            item.update_quantity(new_quantity)
            logger.info(f"Updated {item.name} quantity from {old_quantity} to {new_quantity}")
            return True
            
        except PantryItem.DoesNotExist:
            logger.warning(f"Pantry item {item_id} not found for update")
            return False
        except Exception as e:
            logger.error(f"Error updating pantry item {item_id}: {e}")
            return False
    
    def consume_item(self, item_id: int, consumed_quantity: float) -> bool:
        """
        Consume/use item from pantry.
        
        Args:
            item_id: ID of item to consume
            consumed_quantity: Amount consumed
            
        Returns:
            True if consumed successfully, False otherwise
        """
        try:
            item = PantryItem.objects.get(id=item_id)
            old_quantity = item.quantity
            item.subtract_quantity(consumed_quantity)
            
            logger.info(f"Consumed {consumed_quantity} {item.unit} of {item.name}")
            
            # Remove item if quantity reaches zero
            if item.quantity <= 0:
                item_name = item.name
                item.delete()
                logger.info(f"Removed {item_name} from pantry (quantity reached zero)")
            
            return True
            
        except PantryItem.DoesNotExist:
            logger.warning(f"Pantry item {item_id} not found for consumption")
            return False
        except Exception as e:
            logger.error(f"Error consuming pantry item {item_id}: {e}")
            return False
    
    def search_items(self, query: str) -> List[PantryItem]:
        """
        Search pantry items by name.
        
        Args:
            query: Search query
            
        Returns:
            List of matching PantryItem instances
        """
        return PantryItem.objects.filter(
            name__icontains=query
        ).order_by('name')
    
    def get_expiring_items(self, days: int = 7) -> List[PantryItem]:
        """
        Get items expiring within specified days.
        
        Args:
            days: Number of days to check ahead
            
        Returns:
            List of expiring PantryItem instances
        """
        return PantryItem.get_expiring_soon(days)
    
    def get_expired_items(self) -> List[PantryItem]:
        """
        Get all expired items.
        
        Returns:
            List of expired PantryItem instances
        """
        return PantryItem.get_expired_items()
    
    def get_low_stock_items(self, threshold: float = 1.0) -> List[PantryItem]:
        """
        Get items with low stock.
        
        Args:
            threshold: Quantity threshold for low stock
            
        Returns:
            List of low stock PantryItem instances
        """
        return PantryItem.get_low_stock_items(threshold)
    
    def get_pantry_summary(self) -> Dict:
        """
        Get comprehensive pantry summary with statistics and alerts.
        
        Returns:
            Dictionary with pantry summary data
        """
        stats = PantryItem.get_statistics()
        
        return {
            'statistics': stats,
            'expired_items': list(self.get_expired_items()),
            'expiring_soon': list(self.get_expiring_items()),
            'low_stock': list(self.get_low_stock_items()),
            'total_items': stats['total_items'],
            'alerts': {
                'expired_count': stats['expired_count'],
                'expiring_soon_count': stats['expiring_soon_count'],
                'low_stock_count': stats['low_stock_count'],
            }
        }
    
    def cleanup_expired_items(self, days_past_expiry: int = 30) -> Tuple[int, List[str]]:
        """
        Remove items that have been expired for too long.
        
        Args:
            days_past_expiry: Days past expiry date to keep items
            
        Returns:
            Tuple of (count_removed, list_of_removed_names)
        """
        cutoff_date = timezone.now().date() - timedelta(days=days_past_expiry)
        expired_items = PantryItem.objects.filter(
            expiry_date__lt=cutoff_date
        )
        
        removed_names = list(expired_items.values_list('name', flat=True))
        count = expired_items.count()
        
        if count > 0:
            expired_items.delete()
            logger.info(f"Cleaned up {count} expired items: {', '.join(removed_names)}")
        
        return count, removed_names
    
    def bulk_update_from_receipt(self, products_data: List[Dict]) -> Tuple[int, int, List[str]]:
        """
        Bulk update pantry from receipt data.
        
        Args:
            products_data: List of product dictionaries with name, quantity, unit
            
        Returns:
            Tuple of (items_added, items_updated, error_messages)
        """
        added_count = 0
        updated_count = 0
        errors = []
        
        for product in products_data:
            try:
                name = product.get('name', '').strip()
                quantity = float(product.get('quantity', 1.0))
                unit = product.get('unit', 'szt.').strip()
                
                if not name:
                    errors.append("Empty product name skipped")
                    continue
                
                item, created = PantryItem.objects.get_or_create(
                    name=name,
                    defaults={
                        'quantity': quantity,
                        'unit': unit,
                    }
                )
                
                if created:
                    added_count += 1
                    logger.info(f"Added new pantry item: {name}")
                else:
                    item.add_quantity(quantity)
                    updated_count += 1
                    logger.info(f"Updated pantry item: {name} (+{quantity} {unit})")
                    
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid data for product {product}: {e}"
                errors.append(error_msg)
                logger.warning(error_msg)
            except Exception as e:
                error_msg = f"Error processing product {product}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        logger.info(f"Bulk update completed: {added_count} added, {updated_count} updated")
        return added_count, updated_count, errors
    
    def get_shopping_suggestions(self, threshold: float = 2.0) -> List[Dict]:
        """
        Get shopping suggestions based on low stock and expired items.
        
        Args:
            threshold: Quantity threshold for suggestions
            
        Returns:
            List of shopping suggestion dictionaries
        """
        suggestions = []
        
        # Low stock items
        low_stock = self.get_low_stock_items(threshold)
        for item in low_stock:
            suggestions.append({
                'name': item.name,
                'current_quantity': item.quantity,
                'unit': item.unit,
                'reason': 'low_stock',
                'urgency': 'medium',
                'suggested_quantity': threshold * 2
            })
        
        # Expired items that need replacement
        expired = self.get_expired_items()
        for item in expired:
            suggestions.append({
                'name': item.name,
                'current_quantity': item.quantity,
                'unit': item.unit,
                'reason': 'expired',
                'urgency': 'high',
                'suggested_quantity': item.quantity,
                'expiry_date': item.expiry_date.isoformat() if item.expiry_date else None
            })
        
        return suggestions