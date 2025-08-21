"""
Redis-based caching service for receipt processing optimization.
"""

import hashlib
import json
import logging
from functools import wraps
from typing import Any

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from django.conf import settings
from django.core.cache import cache

from .exceptions_receipt import CacheError

logger = logging.getLogger(__name__)


def get_file_hash(file_path: str) -> str:
    """Generate SHA-256 hash for a file."""
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error generating hash for file {file_path}: {e}")
        raise CacheError(f"Failed to generate file hash: {str(e)}", file_path=file_path)


class CacheService:
    """Async Redis cache service for receipt processing."""

    def __init__(self):
        self.redis_client = None
        self.use_redis = REDIS_AVAILABLE and getattr(settings, 'USE_REDIS_CACHE', True)
        self.cache_timeout = getattr(settings, 'RECEIPT_CACHE_TIMEOUT', 3600)  # 1 hour default

        if self.use_redis:
            self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}. Falling back to Django cache.")
            self.use_redis = False

    async def get_cached_ocr_result(self, file_path: str) -> str | None:
        """Get cached OCR result for a file."""
        try:
            file_hash = get_file_hash(file_path)
            cache_key = f"ocr:{file_hash}"

            if self.use_redis and self.redis_client:
                result = await self.redis_client.get(cache_key)
                if result:
                    logger.debug(f"Cache hit for OCR: {file_path}")
                    return json.loads(result)
            else:
                # Fallback to Django cache
                result = cache.get(cache_key)
                if result:
                    logger.debug(f"Django cache hit for OCR: {file_path}")
                    return result

            logger.debug(f"Cache miss for OCR: {file_path}")
            return None

        except Exception as e:
            logger.warning(f"Cache retrieval error for OCR {file_path}: {e}")
            return None

    async def cache_ocr_result(self, file_path: str, text: str) -> bool:
        """Cache OCR result for a file."""
        try:
            file_hash = get_file_hash(file_path)
            cache_key = f"ocr:{file_hash}"

            if self.use_redis and self.redis_client:
                await self.redis_client.setex(
                    cache_key,
                    self.cache_timeout,
                    json.dumps(text)
                )
                logger.debug(f"Cached OCR result in Redis: {file_path}")
            else:
                # Fallback to Django cache
                cache.set(cache_key, text, self.cache_timeout)
                logger.debug(f"Cached OCR result in Django cache: {file_path}")

            return True

        except Exception as e:
            logger.warning(f"Cache storage error for OCR {file_path}: {e}")
            return False

    async def get_cached_llm_result(self, text_hash: str) -> dict[str, Any] | None:
        """Get cached LLM result for processed text."""
        try:
            cache_key = f"llm:{text_hash}"

            if self.use_redis and self.redis_client:
                result = await self.redis_client.get(cache_key)
                if result:
                    logger.debug(f"Cache hit for LLM: {text_hash[:8]}...")
                    return json.loads(result)
            else:
                # Fallback to Django cache
                result = cache.get(cache_key)
                if result:
                    logger.debug(f"Django cache hit for LLM: {text_hash[:8]}...")
                    return result

            logger.debug(f"Cache miss for LLM: {text_hash[:8]}...")
            return None

        except Exception as e:
            logger.warning(f"Cache retrieval error for LLM {text_hash[:8]}...: {e}")
            return None

    async def cache_llm_result(self, text_hash: str, products: dict[str, Any]) -> bool:
        """Cache LLM result for processed text."""
        try:
            cache_key = f"llm:{text_hash}"

            if self.use_redis and self.redis_client:
                await self.redis_client.setex(
                    cache_key,
                    self.cache_timeout,
                    json.dumps(products)
                )
                logger.debug(f"Cached LLM result in Redis: {text_hash[:8]}...")
            else:
                # Fallback to Django cache
                cache.set(cache_key, products, self.cache_timeout)
                logger.debug(f"Cached LLM result in Django cache: {text_hash[:8]}...")

            return True

        except Exception as e:
            logger.warning(f"Cache storage error for LLM {text_hash[:8]}...: {e}")
            return False

    def get_text_hash(self, text: str) -> str:
        """Generate hash for text content."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    async def invalidate_cache(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern."""
        try:
            if self.use_redis and self.redis_client:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    return await self.redis_client.delete(*keys)
                return 0
            else:
                # Django cache doesn't support pattern deletion easily
                logger.warning("Pattern-based cache invalidation not supported with Django cache")
                return 0

        except Exception as e:
            logger.error(f"Cache invalidation error for pattern {pattern}: {e}")
            raise CacheError(f"Failed to invalidate cache: {str(e)}", cache_key=pattern)

    async def close(self):
        """Close Redis connection."""
        if self.use_redis and self.redis_client:
            await self.redis_client.close()


def cache_result(cache_key_prefix: str, timeout: int = 3600):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_service = CacheService()

            # Generate cache key from function arguments
            key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = f"{cache_key_prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"

            try:
                # Try to get cached result
                if cache_service.use_redis and cache_service.redis_client:
                    cached = await cache_service.redis_client.get(cache_key)
                    if cached:
                        return json.loads(cached)
                else:
                    cached = cache.get(cache_key)
                    if cached:
                        return cached

                # Execute function and cache result
                result = await func(*args, **kwargs)

                if cache_service.use_redis and cache_service.redis_client:
                    await cache_service.redis_client.setex(
                        cache_key, timeout, json.dumps(result, default=str)
                    )
                else:
                    cache.set(cache_key, result, timeout)

                return result

            except Exception as e:
                logger.warning(f"Cache operation failed for {func.__name__}: {e}")
                # Execute function without caching
                return await func(*args, **kwargs)
            finally:
                await cache_service.close()

        return wrapper
    return decorator


# Enhanced cache service with database fallback
class IntelligentCacheService:
    """
    Intelligent cache service with Redis primary and database fallback.
    Implements the caching strategy from FAZA 5 of the plan.
    """

    def __init__(self):
        self.redis_available = REDIS_AVAILABLE
        self.redis_client = None
        self.use_redis = REDIS_AVAILABLE and getattr(settings, 'USE_REDIS_CACHE', True)
        self.default_timeout = getattr(settings, 'CACHE_DEFAULT_TIMEOUT', 300)

        if self.use_redis:
            self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            # For sync operations, we'll use the sync redis client
            import redis as sync_redis
            self.redis_client = sync_redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {e}. Falling back to Django cache.")
            self.use_redis = False
            self.redis_client = None

    def get(self, key: str):
        """
        Get value from cache with intelligent fallback.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        try:
            # Try Redis cache first
            if self.use_redis and self.redis_client:
                result = self.redis_client.get(key)
                if result is not None:
                    logger.debug(f"Cache hit (Redis): {key}")
                    try:
                        return json.loads(result)
                    except (json.JSONDecodeError, TypeError):
                        return result

        except Exception as e:
            logger.warning(f"Redis cache error for key '{key}': {e}")
            # Redis failed, mark as unavailable for this request
            self.use_redis = False

        try:
            # Fallback to Django database cache
            result = cache.get(key)
            if result is not None:
                logger.debug(f"Cache hit (Database): {key}")
                return result

        except Exception as e:
            logger.error(f"Database cache error for key '{key}': {e}")

        logger.debug(f"Cache miss: {key}")
        return None

    def set(self, key: str, value, timeout: int | None = None):
        """
        Set value in cache with intelligent fallback.
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds
            
        Returns:
            True if successfully cached in at least one backend
        """
        timeout = timeout or self.default_timeout
        success = False

        try:
            # Try Redis cache first
            if self.use_redis and self.redis_client:
                if isinstance(value, (dict, list)):
                    self.redis_client.setex(key, timeout, json.dumps(value, default=str))
                else:
                    self.redis_client.setex(key, timeout, str(value))
                success = True
                logger.debug(f"Cached (Redis): {key}")

        except Exception as e:
            logger.warning(f"Redis cache set error for key '{key}': {e}")
            self.use_redis = False

        try:
            # Always try to set in Django database cache as well
            cache.set(key, value, timeout)
            success = True
            logger.debug(f"Cached (Database): {key}")

        except Exception as e:
            logger.error(f"Database cache set error for key '{key}': {e}")

        return success

    def delete(self, key: str):
        """Delete key from both cache backends."""
        success = False

        try:
            if self.use_redis and self.redis_client:
                self.redis_client.delete(key)
                success = True
                logger.debug(f"Deleted from Redis: {key}")
        except Exception as e:
            logger.warning(f"Redis cache delete error for key '{key}': {e}")

        try:
            cache.delete(key)
            success = True
            logger.debug(f"Deleted from Database: {key}")
        except Exception as e:
            logger.error(f"Database cache delete error for key '{key}': {e}")

        return success

    def get_or_set(self, key: str, default_func, timeout: int | None = None):
        """Get from cache or set using default function."""
        result = self.get(key)
        if result is None:
            result = default_func()
            self.set(key, result, timeout)
        return result

    def check_status(self) -> dict:
        """Check status of both cache backends."""
        status = {
            'redis': {'available': False, 'error': None},
            'database': {'available': False, 'error': None}
        }

        # Test Redis
        try:
            if self.redis_client:
                self.redis_client.ping()
                status['redis']['available'] = True
        except Exception as e:
            status['redis']['error'] = str(e)

        # Test Django cache (database)
        try:
            test_key = '_test_db_cache'
            cache.set(test_key, 'test', 1)
            cache.get(test_key)
            cache.delete(test_key)
            status['database']['available'] = True
        except Exception as e:
            status['database']['error'] = str(e)

        return status


# Global cache service instances
cache_service = CacheService()  # Original OCR/LLM cache service
intelligent_cache = IntelligentCacheService()  # New intelligent cache with fallback


def get_intelligent_cache():
    """Get the intelligent cache service instance."""
    return intelligent_cache
