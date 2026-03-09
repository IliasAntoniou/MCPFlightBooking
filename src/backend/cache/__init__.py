"""
Cache module providing Redis and in-memory cache implementations.
Automatically falls back to in-memory cache if Redis is unavailable.
"""
import os
import logging
from typing import Optional

from .base import CacheInterface
from .redis_cache import RedisCache, REDIS_AVAILABLE
from .memory_cache import MemoryCache

logger = logging.getLogger(__name__)

_cache_instance: Optional[CacheInterface] = None


async def get_cache() -> CacheInterface:
    """
    Get cache instance (singleton pattern).
    Returns Redis if available, otherwise in-memory cache.
    
    Returns:
        CacheInterface implementation (Redis or Memory)
    """
    global _cache_instance
    
    # Return existing instance if already created
    if _cache_instance is not None:
        return _cache_instance
    
    # Try Redis first if enabled and available
    if REDIS_AVAILABLE and os.getenv("REDIS_ENABLED", "false").lower() == "true":
        redis_cache = RedisCache(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD") or None,
            key_prefix=os.getenv("REDIS_KEY_PREFIX", "flight_cache:"),
            default_ttl=int(os.getenv("REDIS_TTL", "3600"))
        )
        
        # Try to connect
        if await redis_cache.connect():
            logger.info("✅ Using Redis distributed cache")
            _cache_instance = redis_cache
            return _cache_instance
        else:
            logger.warning("⚠️ Redis connection failed, falling back to memory cache")
    elif not REDIS_AVAILABLE and os.getenv("REDIS_ENABLED", "false").lower() == "true":
        logger.warning("⚠️ Redis package not installed, using memory cache. Install with: pip install redis")
    
    # Fallback to in-memory cache
    logger.info("ℹ️ Using in-memory cache")
    _cache_instance = MemoryCache(
        max_size=int(os.getenv("CACHE_MAX_SIZE", "100")),
        default_ttl=int(os.getenv("CACHE_TTL", "3600"))
    )
    
    return _cache_instance


# Export public API
__all__ = ["CacheInterface", "get_cache", "RedisCache", "MemoryCache"]