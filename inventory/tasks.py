import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Product

logger = logging.getLogger(__name__)

@shared_task
def manage_alias_reputation():
    """
    Celery task to manage product alias reputation:
    - Promotes aliases to 'confirmed' status based on count.
    - Prunes 'unverified' aliases with count 1 that are too old.
    """
    logger.info("Starting alias reputation management task...")

    # Define thresholds (can be moved to settings.py)
    ALIAS_CONFIRMATION_THRESHOLD = getattr(settings, 'ALIAS_CONFIRMATION_THRESHOLD', 10)
    ALIAS_EXPIRATION_DAYS = getattr(settings, 'ALIAS_EXPIRATION_DAYS', 90)

    products_updated = 0
    aliases_promoted = 0
    aliases_pruned = 0

    for product in Product.objects.all():
        original_aliases = list(product.aliases) # Create a copy to iterate
        updated_aliases = []
        product_changed = False

        for alias_entry in original_aliases:
            alias_name = alias_entry.get("name")
            alias_count = alias_entry.get("count", 0)
            alias_status = alias_entry.get("status", "unverified")
            first_seen = alias_entry.get("first_seen")
            last_seen = alias_entry.get("last_seen")

            if not alias_name:
                continue

            # Promotion logic
            if alias_status == "unverified" and alias_count >= ALIAS_CONFIRMATION_THRESHOLD:
                alias_entry["status"] = "confirmed"
                aliases_promoted += 1
                product_changed = True
                logger.debug(f"Promoted alias '{alias_name}' for product '{product.name}' to 'confirmed'")

            # Pruning logic
            if alias_status == "unverified" and alias_count == 1:
                try:
                    last_seen_dt = timezone.datetime.fromisoformat(last_seen)
                    if timezone.now() - last_seen_dt > timedelta(days=ALIAS_EXPIRATION_DAYS):
                        aliases_pruned += 1
                        product_changed = True
                        logger.debug(f"Pruned alias '{alias_name}' for product '{product.name}' (unverified, count 1, expired)")
                        continue # Skip adding this alias to updated_aliases
                except (ValueError, TypeError):
                    logger.warning(f"Invalid date format for alias '{alias_name}' in product '{product.name}'. Skipping pruning.")
            
            updated_aliases.append(alias_entry) # Keep alias if not pruned

        if product_changed:
            product.aliases = updated_aliases
            product.save(update_fields=['aliases'])
            products_updated += 1

    logger.info(f"Alias reputation management task completed. Products updated: {products_updated}, Aliases promoted: {aliases_promoted}, Aliases pruned: {aliases_pruned}")