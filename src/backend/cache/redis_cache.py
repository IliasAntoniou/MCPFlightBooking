"""
Redis-based distributed cache implementation.
Provides shared caching across multiple server instances.
"""
import json
import logging
from typing import Optional, Any, Dict

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .base import CacheInterface

logger = logging.getLogger(__name__)


class RedisCache(CacheInterface):
    """Redis-based cache with automatic JSON serialization."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 3600,
        key_prefix: str = "flight_cache:"
    ):
        """
        Initialize Redis cache configuration.
        
        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number (0-15)
            password: Redis password (if required)
            default_ttl: Default time-to-live in seconds
            key_prefix: Prefix for all cache keys
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis package not installed. Run: pip install redis")
        
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.client: Optional[aioredis.Redis] = None
        self._stats = {"hits": 0, "misses": 0, "errors": 0}
    
    async def connect(self) -> bool:
        """
        Establish connection to Redis server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = await aioredis.from_url(
                f"redis://{self.host}:{self.port}/{self.db}",
                password=self.password,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            await self.client.ping()
            logger.info(f"✅ Redis cache connected to {self.host}:{self.port} (db={self.db})")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.client = None
            return False
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Redis cache connection closed")
    
    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key."""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value (deserialized from JSON) or None if not found
        """
        if not self.client:
            return None
        
        try:
            full_key = self._make_key(key)
            value = await self.client.get(full_key)
            
            if value is None:
                self._stats["misses"] += 1
                return None
            
            self._stats["hits"] += 1
            return json.loads(value)
        except Exception as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
            self._stats["errors"] += 1
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with automatic expiration.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (uses default if not specified)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False
        
        try:
            full_key = self._make_key(key)
            serialized = json.dumps(value)
            ttl = ttl or self.default_ttl
            
            await self.client.setex(full_key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis SET error for key '{key}': {e}")
            self._stats["errors"] += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False otherwise
        """
        if not self.client:
            return False
        
        try:
            full_key = self._make_key(key)
            result = await self.client.delete(full_key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis DELETE error for key '{key}': {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists, False otherwise
        """
        if not self.client:
            return False
        
        try:
            full_key = self._make_key(key)
            result = await self.client.exists(full_key)
            return result > 0
        except Exception:
            return False
    
    async def clear(self) -> bool:
        """
        Clear all keys with our prefix.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False
        
        try:
            pattern = f"{self.key_prefix}*"
            keys = await self.client.keys(pattern)
            if keys:
                await self.client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis CLEAR error: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache performance metrics
        """
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            "type": "redis",
            "connected": self.client is not None,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "errors": self._stats["errors"],
            "hit_rate": f"{hit_rate:.1f}%",
            "total_requests": total
        }