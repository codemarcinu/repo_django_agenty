import logging
from datetime import date, timedelta

from inventory.models import InventoryItem, Rule

logger = logging.getLogger(__name__)

class RuleEngineService:
    def __init__(self):
        # Cache'owanie reguł, aby nie odpytywać bazy za każdym razem
        self.rules = list(Rule.objects.filter(is_active=True).order_by('priority'))

    def apply_rules(self, inventory_item: InventoryItem):
        """Aplikuje wszystkie pasujące reguły do danego obiektu inwentarza."""
        logger.info(f"Applying rules to InventoryItem {inventory_item.id} ({inventory_item.product.name})")
        for rule in self.rules:
            try:
                if self._check_condition(rule.condition, inventory_item):
                    logger.debug(f"Rule '{rule.name}' condition met for item {inventory_item.id}. Executing action.")
                    self._execute_action(rule.action, inventory_item)
            except Exception as e:
                logger.error(f"Error applying rule '{rule.name}' to item {inventory_item.id}: {e}", exc_info=True)
        inventory_item.save() # Zapisz zmiany po wszystkich regułach
        logger.info(f"Finished applying rules to InventoryItem {inventory_item.id}.")

    def _check_condition(self, condition: dict, item: InventoryItem) -> bool:
        """
        Sprawdza, czy warunek reguły jest spełniony dla danego obiektu InventoryItem.
        Obsługuje proste warunki oparte na ścieżkach do pól.
        """
        if not condition:
            return True # Brak warunku oznacza, że reguła zawsze pasuje

        field_path = condition.get('field')
        operator = condition.get('operator')
        value = condition.get('value')

        if not all([field_path, operator, value is not None]):
            logger.warning(f"Invalid rule condition: {condition}")
            return False

        # Navigate through the object path to get the field value
        current_value = item
        try:
            for part in field_path.split('.'):
                if hasattr(current_value, part):
                    current_value = getattr(current_value, part)
                    if callable(current_value): # Handle properties that are methods
                        current_value = current_value()
                else:
                    logger.warning(f"Field path '{field_path}' not found on item {item.id}. Part: {part}")
                    return False # Path not found
        except Exception as e:
            logger.error(f"Error navigating field path '{field_path}' for item {item.id}: {e}")
            return False

        # Perform comparison based on operator
        if operator == "equals":
            return str(current_value) == str(value)
        elif operator == "contains":
            return str(value) in str(current_value)
        elif operator == "starts_with":
            return str(current_value).startswith(str(value))
        elif operator == "ends_with":
            return str(current_value).endswith(str(value))
        elif operator == "greater_than":
            return current_value > value
        elif operator == "less_than":
            return current_value < value
        elif operator == "in":
            return current_value in value # Value should be a list for 'in' operator
        else:
            logger.warning(f"Unsupported operator: {operator}")
            return False

    def _execute_action(self, action: dict, item: InventoryItem):
        """
        Wykonuje akcję reguły na danym obiekcie InventoryItem.
        """
        if not action:
            logger.warning("No action defined for rule.")
            return

        action_type = action.get('action_type')
        params = action.get('params', {})

        if action_type == "set_expiry":
            days = params.get('days')
            if isinstance(days, int):
                item.expiry_date = date.today() + timedelta(days=days)
                logger.debug(f"Set expiry date for {item.product.name} to {item.expiry_date}")
            else:
                logger.warning(f"Invalid 'days' parameter for set_expiry action: {days}")
        elif action_type == "set_location":
            location = params.get('location')
            if location and location in [choice[0] for choice in item.STORAGE_CHOICES]:
                item.storage_location = location
                logger.debug(f"Set storage location for {item.product.name} to {item.storage_location}")
            else:
                logger.warning(f"Invalid 'location' parameter for set_location action: {location}")
        elif action_type == "set_quantity_remaining":
            quantity = params.get('quantity')
            if isinstance(quantity, (int, float)):
                item.quantity_remaining = quantity
                logger.debug(f"Set quantity remaining for {item.product.name} to {item.quantity_remaining}")
            else:
                logger.warning(f"Invalid 'quantity' parameter for set_quantity_remaining action: {quantity}")
        # Add more action types as needed
        else:
            logger.warning(f"Unsupported action type: {action_type}")
