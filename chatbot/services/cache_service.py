"""
Redis-based caching service for receipt processing optimization.
"""

import hashlib
import json
import logging
from typing import Optional, Any, Dict
import asyncio
from functools import wraps

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
    
    async def get_cached_ocr_result(self, file_path: str) -> Optional[str]:
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
    
    async def get_cached_llm_result(self, text_hash: str) -> Optional[Dict[str, Any]]:
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
    
    async def cache_llm_result(self, text_hash: str, products: Dict[str, Any]) -> bool:
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


# Global cache service instance
cache_service = CacheService()