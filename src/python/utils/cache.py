"""Redis caching layer for Python services."""

import json
import os
from typing import Any, Optional
import redis


class RedisCache:
    """Redis-based caching layer."""
    
    def __init__(self, host: str = None, port: int = None):
        """
        Initialize Redis cache.
        
        Args:
            host: Redis host (default: from REDIS_HOST env)
            port: Redis port (default: from REDIS_PORT env)
        """
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        
        self.client = redis.Redis(
            host=self.host,
            port=self.port,
            decode_responses=True,
        )
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        value = self.client.get(key)
        if value:
            return json.loads(value)
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (default: 1 hour)
            
        Returns:
            True if successful
        """
        return self.client.setex(
            key,
            ttl,
            json.dumps(value)
        )
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        return self.client.delete(key) > 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return self.client.exists(key) > 0
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        keys = self.client.keys(pattern)
        if keys:
            return self.client.delete(*keys)
        return 0


# Example usage:
#
# from src.python.utils.cache import RedisCache
#
# cache = RedisCache()
#
# # Set value with 1 hour TTL
# cache.set("repos:stats", {"total": 1000, "quality": 85}, ttl=3600)
#
# # Get value
# stats = cache.get("repos:stats")
#
# # Delete value
# cache.delete("repos:stats")
