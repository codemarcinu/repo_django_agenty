from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from functools import wraps
import hashlib
import json


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


def cache_function(timeout=300, key_prefix=''):
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
        cache_key_pattern = f"{model_instance.__class__.__name__}_{model_instance.pk}_{method_name}*"
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
    from chatbot.models import Agent, Document, PantryItem, ReceiptProcessing
    
    cache_key = 'dashboard_stats'
    stats = cache.get(cache_key)
    
    if stats is None:
        stats = {
            'agents_count': Agent.objects.filter(is_active=True).count(),
            'documents_count': Document.objects.count(),
            'pantry_items_count': PantryItem.objects.count(),
            'recent_receipts_count': ReceiptProcessing.objects.filter(
                status__in=['uploaded', 'processing', 'ready_for_review']
            ).count()
        }
        cache.set(cache_key, stats, 300)  # Cache for 5 minutes
    
    return stats


def invalidate_dashboard_cache():
    """
    Invalidate dashboard statistics cache
    """
    cache.delete('dashboard_stats')