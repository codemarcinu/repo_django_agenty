import hashlib
import logging
from functools import wraps

from django.core.cache import cache, caches
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from inventory.models import Category, Receipt

from ..models import Agent, Document

logger = logging.getLogger(__name__)


def cache_model_method(timeout=300):
    """
    Decorator for caching model methods
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Create cache key based on model, method, and arguments
            cache_key = f"{self.__class__.__name__}_{self.pk}_{func.__name__}"
            if args or kwargs:
                args_str = str(args) + str(sorted(kwargs.items()))
                cache_key += "_" + hashlib.md5(args_str.encode()).hexdigest()[:8]

            # Try to get from cache
            result = cache.get(cache_key)
            if result is None:
                result = func(self, *args, **kwargs)
                cache.set(cache_key, result, timeout)

            return result

        return wrapper

    return decorator


def cache_function(timeout=300, key_prefix=""):
    """
    Decorator for caching function results
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key
            cache_key = f"{key_prefix}{func.__name__}"
            if args or kwargs:
                args_str = str(args) + str(sorted(kwargs.items()))
                cache_key += "_" + hashlib.md5(args_str.encode()).hexdigest()[:8]

            # Try to get from cache
            result = cache.get(cache_key)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(cache_key, result, timeout)

            return result

        return wrapper

    return decorator


def invalidate_model_cache(model_instance, method_name=None):
    """
    Invalidate cache for a specific model instance
    """
    if method_name:
        cache_key_pattern = (
            f"{model_instance.__class__.__name__}_{model_instance.pk}_{method_name}*"
        )
    else:
        cache_key_pattern = f"{model_instance.__class__.__name__}_{model_instance.pk}_*"

    # Note: This is a simplified version. For production, consider using
    # django-cache-tree or similar for more efficient pattern-based invalidation
    cache.delete_many([cache_key_pattern])


class CachedViewMixin:
    """
    Mixin to add caching to class-based views
    """

    cache_timeout = 300

    @method_decorator(cache_page(cache_timeout))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


def get_agent_statistics():
    """
    Get cached agent statistics for dashboard
    """


    cache_key = "dashboard_stats"
    stats = cache.get(cache_key)

    if stats is None:
        # Use inventory items count instead of removed PantryItem
        from inventory.models import InventoryItem

        stats = {
            "agents_count": Agent.objects.filter(is_active=True).count(),
            "documents_count": Document.objects.count(),
            "pantry_items_count": InventoryItem.objects.filter(
                storage_location='pantry', quantity_remaining__gt=0
            ).count(),
            "recent_receipts_count": Receipt.objects.filter(
                status__in=["uploaded", "processing", "ready_for_review"]
            ).count(),
        }
        cache.set(cache_key, stats, 300)  # Cache for 5 minutes

    return stats


def invalidate_dashboard_cache():
    """
    Invalidate dashboard statistics cache
    """
    cache.delete("dashboard_stats")


def cache_result(timeout=300):
    """
    Enhanced decorator for caching function results with Redis/database fallback.
    This is the main decorator requested in Prompt 5.
    
    Args:
        timeout: Cache timeout in seconds (default: 5 minutes)
        
    Usage:
        @cache_result(timeout=600)
        def get_categories_list():
            return Category.objects.all()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key based on function name and arguments
            cache_key = f"cached_result_{func.__name__}"
            if args or kwargs:
                args_str = str(args) + str(sorted(kwargs.items()))
                cache_key += "_" + hashlib.md5(args_str.encode()).hexdigest()[:12]

            try:
                # Try Redis cache first (primary cache)
                primary_cache = caches['default']
                result = primary_cache.get(cache_key)

                if result is not None:
                    logger.debug(f"Cache hit (Redis) for {func.__name__}")
                    return result

                # Execute function if not in cache
                result = func(*args, **kwargs)

                # Store in Redis cache
                primary_cache.set(cache_key, result, timeout)
                logger.debug(f"Cached result (Redis) for {func.__name__}")

                return result

            except Exception as redis_error:
                logger.warning(f"Redis cache error for {func.__name__}: {redis_error}")

                try:
                    # Fallback to database cache
                    db_cache = caches.get('database_fallback', cache)
                    result = db_cache.get(cache_key)

                    if result is not None:
                        logger.debug(f"Cache hit (Database) for {func.__name__}")
                        return result

                    # Execute function
                    result = func(*args, **kwargs)

                    # Store in database cache
                    db_cache.set(cache_key, result, timeout)
                    logger.debug(f"Cached result (Database) for {func.__name__}")

                    return result

                except Exception as db_error:
                    logger.error(f"Database cache error for {func.__name__}: {db_error}")
                    # If both caches fail, just execute the function
                    return func(*args, **kwargs)

        return wrapper
    return decorator


@cache_result(timeout=1800)  # Cache for 30 minutes
def get_all_categories():
    """
    Get all categories with caching.
    This is an example of using the @cache_result decorator for "heavy" queries.
    """
    return list(Category.objects.select_related().order_by('name'))


@cache_result(timeout=600)  # Cache for 10 minutes
def get_receipt_processing_stats():
    """
    Get receipt processing statistics with caching.
    """
    from django.db.models import Count, Q

    from inventory.models import Receipt

    return Receipt.objects.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        processing=Count('id', filter=Q(status__in=['processing', 'processing_ocr', 'processing_parsing'])),
        errors=Count('id', filter=Q(status='error'))
    )
