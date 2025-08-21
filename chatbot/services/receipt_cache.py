"""
Advanced caching system for receipt processing.
Implements multi-level caching strategy from FAZA 5 of the plan.
"""

import hashlib
import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReceiptCacheManager:
    """
    Multi-level caching manager for receipt processing system.
    Implements the caching strategy from FAZA 5 of the plan.
    """

    def __init__(self):
        self.l1_cache = cache  # Redis/Memory cache
        self.default_timeout = getattr(settings, 'RECEIPT_CACHE_TIMEOUT', 86400)  # 24 hours
        self.ocr_cache_timeout = getattr(settings, 'OCR_CACHE_TIMEOUT', 604800)  # 7 days

    def _generate_cache_key(self, prefix: str, *args) -> str:
        """Generate consistent cache key."""
        key_parts = [str(arg) for arg in args]
        key_string = f"{prefix}:{'_'.join(key_parts)}"
        return key_string.replace(' ', '_').lower()

    def _generate_file_hash(self, file_content: bytes) -> str:
        """Generate hash for file content."""
        return hashlib.sha256(file_content).hexdigest()

    def cache_ocr_result(self, file_hash: str, ocr_result: dict[str, Any]) -> bool:
        """
        Cache OCR results to avoid reprocessing identical files.
        
        Args:
            file_hash: Hash of the original file
            ocr_result: OCR processing result
            
        Returns:
            True if cached successfully
        """
        try:
            cache_key = self._generate_cache_key("ocr_result", file_hash)

            # Add metadata
            cached_data = {
                'result': ocr_result,
                'cached_at': timezone.now().isoformat(),
                'file_hash': file_hash
            }

            success = self.l1_cache.set(
                cache_key,
                cached_data,
                timeout=self.ocr_cache_timeout
            )

            if success:
                logger.info(f"Cached OCR result for file hash: {file_hash[:8]}...")
            else:
                logger.warning(f"Failed to cache OCR result for file hash: {file_hash[:8]}...")

            return success

        except Exception as e:
            logger.error(f"Error caching OCR result: {e}")
            return False

    def get_cached_ocr_result(self, file_hash: str) -> dict[str, Any] | None:
        """
        Retrieve cached OCR result.
        
        Args:
            file_hash: Hash of the file
            
        Returns:
            Cached OCR result or None if not found
        """
        try:
            cache_key = self._generate_cache_key("ocr_result", file_hash)
            cached_data = self.l1_cache.get(cache_key)

            if cached_data:
                logger.info(f"Cache hit for OCR result: {file_hash[:8]}...")
                return cached_data['result']
            else:
                logger.debug(f"Cache miss for OCR result: {file_hash[:8]}...")
                return None

        except Exception as e:
            logger.error(f"Error retrieving cached OCR result: {e}")
            return None

    def cache_parsed_receipt(self, receipt_id: int, parsed_data: dict[str, Any]) -> bool:
        """
        Cache parsed receipt data.
        
        Args:
            receipt_id: Receipt ID
            parsed_data: Parsed receipt data
            
        Returns:
            True if cached successfully
        """
        try:
            cache_key = self._generate_cache_key("parsed_receipt", receipt_id)

            cached_data = {
                'data': parsed_data,
                'cached_at': timezone.now().isoformat(),
                'receipt_id': receipt_id
            }

            success = self.l1_cache.set(
                cache_key,
                cached_data,
                timeout=self.default_timeout
            )

            if success:
                logger.debug(f"Cached parsed data for receipt: {receipt_id}")

            return success

        except Exception as e:
            logger.error(f"Error caching parsed receipt data: {e}")
            return False

    def get_cached_parsed_receipt(self, receipt_id: int) -> dict[str, Any] | None:
        """
        Retrieve cached parsed receipt data.
        
        Args:
            receipt_id: Receipt ID
            
        Returns:
            Cached parsed data or None
        """
        try:
            cache_key = self._generate_cache_key("parsed_receipt", receipt_id)
            cached_data = self.l1_cache.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for parsed receipt: {receipt_id}")
                return cached_data['data']

            return None

        except Exception as e:
            logger.error(f"Error retrieving cached parsed receipt: {e}")
            return None

    def cache_product_matches(self, product_text: str, matches: list[dict[str, Any]]) -> bool:
        """
        Cache product matching results.
        
        Args:
            product_text: Original product text from receipt
            matches: List of matched products
            
        Returns:
            True if cached successfully
        """
        try:
            # Create hash of product text for consistent key
            text_hash = hashlib.md5(product_text.encode()).hexdigest()
            cache_key = self._generate_cache_key("product_matches", text_hash)

            cached_data = {
                'matches': matches,
                'original_text': product_text,
                'cached_at': timezone.now().isoformat()
            }

            # Shorter timeout for product matches (they may change more frequently)
            timeout = self.default_timeout // 2  # 12 hours

            success = self.l1_cache.set(cache_key, cached_data, timeout=timeout)

            if success:
                logger.debug(f"Cached product matches for text: {product_text[:30]}...")

            return success

        except Exception as e:
            logger.error(f"Error caching product matches: {e}")
            return False

    def get_cached_product_matches(self, product_text: str) -> list[dict[str, Any]] | None:
        """
        Retrieve cached product matches.
        
        Args:
            product_text: Product text to match
            
        Returns:
            Cached matches or None
        """
        try:
            text_hash = hashlib.md5(product_text.encode()).hexdigest()
            cache_key = self._generate_cache_key("product_matches", text_hash)
            cached_data = self.l1_cache.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for product matches: {product_text[:30]}...")
                return cached_data['matches']

            return None

        except Exception as e:
            logger.error(f"Error retrieving cached product matches: {e}")
            return None

    def cache_receipt_analytics(self, analytics_key: str, data: dict[str, Any], timeout: int = None) -> bool:
        """
        Cache analytics and dashboard data.
        
        Args:
            analytics_key: Unique key for analytics data
            data: Analytics data to cache
            timeout: Cache timeout (default: 1 hour)
            
        Returns:
            True if cached successfully
        """
        try:
            cache_key = self._generate_cache_key("analytics", analytics_key)
            timeout = timeout or 3600  # 1 hour default for analytics

            cached_data = {
                'data': data,
                'generated_at': timezone.now().isoformat(),
                'key': analytics_key
            }

            success = self.l1_cache.set(cache_key, cached_data, timeout=timeout)

            if success:
                logger.debug(f"Cached analytics data: {analytics_key}")

            return success

        except Exception as e:
            logger.error(f"Error caching analytics data: {e}")
            return False

    def get_cached_analytics(self, analytics_key: str) -> dict[str, Any] | None:
        """
        Retrieve cached analytics data.
        
        Args:
            analytics_key: Analytics data key
            
        Returns:
            Cached analytics data or None
        """
        try:
            cache_key = self._generate_cache_key("analytics", analytics_key)
            cached_data = self.l1_cache.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for analytics: {analytics_key}")
                return cached_data['data']

            return None

        except Exception as e:
            logger.error(f"Error retrieving cached analytics: {e}")
            return None

    def invalidate_receipt_cache(self, receipt_id: int) -> bool:
        """
        Invalidate all cache entries related to a receipt.
        
        Args:
            receipt_id: Receipt ID to invalidate
            
        Returns:
            True if invalidation successful
        """
        try:
            cache_keys = [
                self._generate_cache_key("parsed_receipt", receipt_id),
                self._generate_cache_key("receipt_status", receipt_id),
                self._generate_cache_key("receipt_summary", receipt_id)
            ]

            for cache_key in cache_keys:
                self.l1_cache.delete(cache_key)

            logger.debug(f"Invalidated cache for receipt: {receipt_id}")
            return True

        except Exception as e:
            logger.error(f"Error invalidating receipt cache: {e}")
            return False

    def invalidate_analytics_cache(self) -> bool:
        """
        Invalidate analytics cache when data changes.
        
        Returns:
            True if invalidation successful
        """
        try:
            # Delete common analytics cache keys
            analytics_keys = [
                "dashboard_summary",
                "processing_stats_7d",
                "processing_stats_30d",
                "category_stats",
                "inventory_summary"
            ]

            for key in analytics_keys:
                cache_key = self._generate_cache_key("analytics", key)
                self.l1_cache.delete(cache_key)

            logger.debug("Invalidated analytics cache")
            return True

        except Exception as e:
            logger.error(f"Error invalidating analytics cache: {e}")
            return False

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get caching statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            # Note: This implementation depends on the cache backend
            # Redis backend may provide more detailed stats

            # Basic stats that work with most backends
            stats = {
                'backend': str(type(self.l1_cache)),
                'default_timeout': self.default_timeout,
                'ocr_cache_timeout': self.ocr_cache_timeout,
                'cache_available': True
            }

            # Try to get Redis-specific stats if available
            try:
                if hasattr(self.l1_cache, '_cache') and hasattr(self.l1_cache._cache, 'info'):
                    redis_info = self.l1_cache._cache.info()
                    stats.update({
                        'redis_memory_used': redis_info.get('used_memory_human'),
                        'redis_hits': redis_info.get('keyspace_hits'),
                        'redis_misses': redis_info.get('keyspace_misses'),
                        'redis_keys': redis_info.get('db0', {}).get('keys', 0)
                    })
            except Exception:
                pass  # Redis-specific stats not available

            return stats

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'cache_available': False, 'error': str(e)}

    def cleanup_expired_cache(self) -> bool:
        """
        Clean up expired cache entries.
        This is mainly for backends that don't auto-expire.
        
        Returns:
            True if cleanup successful
        """
        try:
            # Most cache backends handle expiration automatically
            # This method can be extended for custom cleanup logic

            logger.debug("Cache cleanup completed")
            return True

        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
            return False


# Global cache manager instance
_cache_manager = None


def get_cache_manager() -> ReceiptCacheManager:
    """Get global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = ReceiptCacheManager()
    return _cache_manager


# Convenience functions
def cache_ocr_result(file_content: bytes, ocr_result: dict[str, Any]) -> bool:
    """Cache OCR result for file content."""
    cache_manager = get_cache_manager()
    file_hash = cache_manager._generate_file_hash(file_content)
    return cache_manager.cache_ocr_result(file_hash, ocr_result)


def get_cached_ocr_result(file_content: bytes) -> dict[str, Any] | None:
    """Get cached OCR result for file content."""
    cache_manager = get_cache_manager()
    file_hash = cache_manager._generate_file_hash(file_content)
    return cache_manager.get_cached_ocr_result(file_hash)


def cache_receipt_data(receipt_id: int, data: dict[str, Any]) -> bool:
    """Cache receipt data."""
    cache_manager = get_cache_manager()
    return cache_manager.cache_parsed_receipt(receipt_id, data)


def get_cached_receipt_data(receipt_id: int) -> dict[str, Any] | None:
    """Get cached receipt data."""
    cache_manager = get_cache_manager()
    return cache_manager.get_cached_parsed_receipt(receipt_id)


def invalidate_receipt_cache(receipt_id: int) -> bool:
    """Invalidate cache for receipt."""
    cache_manager = get_cache_manager()
    return cache_manager.invalidate_receipt_cache(receipt_id)


# Decorator for caching function results
def cache_result(timeout: int = 3600, key_prefix: str = "func_cache"):
    """
    Decorator to cache function results.
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for cache key
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache_manager = get_cache_manager()

            # Generate cache key from function name and arguments
            key_parts = [func.__name__] + [str(arg) for arg in args]
            key_parts.extend([f"{k}_{v}" for k, v in sorted(kwargs.items())])
            cache_key = cache_manager._generate_cache_key(key_prefix, *key_parts)

            # Try to get from cache
            cached_result = cache_manager.l1_cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for function: {func.__name__}")
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.l1_cache.set(cache_key, result, timeout=timeout)
            logger.debug(f"Cached result for function: {func.__name__}")

            return result
        return wrapper
    return decorator
