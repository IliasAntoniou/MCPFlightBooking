"""
In-memory LRU cache implementation with TTL support.
Used as fallback when Redis is unavailable.
"""
from collections import OrderedDict
from typing import Optional, Any, Dict
import time

from .base import CacheInterface


class MemoryCache(CacheInterface):
    """In-memory LRU cache with TTL support."""
    
    def __init__(self, max_size: int = 100, default_ttl: int = 3600):
        """
        Initialize in-memory cache.
        
        Args:
            max_size: Maximum number of items to cache
            default_ttl: Default time to live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict = OrderedDict()
        self._expiry: Dict[str, float] = {}
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def _is_expired(self, key: str) -> bool:
        """Check if key is expired."""
        if key not in self._expiry:
            return False
        return time.time() > self._expiry[key]
    
    def _evict_expired(self):
        """Remove expired entries."""
        expired = [k for k in self._cache if self._is_expired(k)]
        for key in expired:
            del self._cache[key]
            del self._expiry[key]
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        self._evict_expired()
        
        if key in self._cache and not self._is_expired(key):
            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return self._cache[key]
        
        self._stats["misses"] += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if not specified)
            
        Returns:
            True (always successful for in-memory cache)
        """
        self._evict_expired()
        
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._cache.popitem(last=False)
            self._stats["evictions"] += 1
        
        self._cache[key] = value
        self._cache.move_to_end(key)
        
        ttl = ttl or self.default_ttl
        self._expiry[key] = time.time() + ttl
        
        return True
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            if key in self._expiry:
                del self._expiry[key]
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and not expired, False otherwise
        """
        self._evict_expired()
        return key in self._cache and not self._is_expired(key)
    
    async def clear(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True (always successful)
        """
        self._cache.clear()
        self._expiry.clear()
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache performance metrics
        """
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            "type": "memory",
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "hit_rate": f"{hit_rate:.1f}%",
            "size": len(self._cache),
            "max_size": self.max_size,
            "total_requests": total
        }