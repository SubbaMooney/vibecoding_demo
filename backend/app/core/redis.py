"""
Redis configuration and connection management
Supports caching, sessions, and pub/sub functionality
"""

import json
import pickle
from typing import Any, Dict, List, Optional, Union
from datetime import timedelta
import structlog
import redis.asyncio as redis
from redis.asyncio import ConnectionPool
from redis.exceptions import RedisError, ConnectionError

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class RedisManager:
    """Redis connection and operation manager"""
    
    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._pubsub_client: Optional[redis.Redis] = None
    
    async def initialize(self):
        """Initialize Redis connection pool"""
        try:
            # Create connection pool
            self._pool = ConnectionPool.from_url(
                str(settings.redis_url),
                password=settings.redis_password,
                max_connections=20,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
            
            # Create Redis client
            self._client = redis.Redis(
                connection_pool=self._pool,
                decode_responses=False  # We'll handle encoding manually for flexibility
            )
            
            # Create separate client for pub/sub
            self._pubsub_client = redis.Redis(
                connection_pool=self._pool,
                decode_responses=True
            )
            
            # Test connection
            await self._client.ping()
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error("Redis initialization failed", error=str(e))
            raise
    
    async def close(self):
        """Close Redis connections"""
        if self._client:
            await self._client.close()
        if self._pubsub_client:
            await self._pubsub_client.close()
        if self._pool:
            await self._pool.disconnect()
        logger.info("Redis connections closed")
    
    async def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            if not self._client:
                return False
            await self._client.ping()
            return True
        except Exception as e:
            logger.error("Redis health check failed", error=str(e))
            return False
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client"""
        if not self._client:
            raise RuntimeError("Redis client not initialized")
        return self._client
    
    @property
    def pubsub_client(self) -> redis.Redis:
        """Get Redis pub/sub client"""
        if not self._pubsub_client:
            raise RuntimeError("Redis pub/sub client not initialized")
        return self._pubsub_client


class RedisCache:
    """Redis-based caching with serialization support"""
    
    def __init__(self, redis_client: redis.Redis, prefix: str = "cache"):
        self.client = redis_client
        self.prefix = prefix
    
    def _make_key(self, key: str) -> str:
        """Create prefixed cache key"""
        return f"{self.prefix}:{key}"
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache with automatic deserialization"""
        try:
            redis_key = self._make_key(key)
            value = await self.client.get(redis_key)
            
            if value is None:
                return default
            
            # Try to deserialize
            try:
                return pickle.loads(value)
            except (pickle.UnpicklingError, TypeError):
                # Fallback to string
                return value.decode('utf-8') if isinstance(value, bytes) else value
                
        except RedisError as e:
            logger.error("Cache get error", key=key, error=str(e))
            return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set value in cache with automatic serialization"""
        try:
            redis_key = self._make_key(key)
            
            # Serialize value
            if isinstance(value, (str, int, float, bool, type(None))):
                serialized_value = str(value).encode('utf-8')
            else:
                serialized_value = pickle.dumps(value)
            
            # Set with TTL
            if ttl is None:
                ttl = settings.cache_ttl
            
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            
            result = await self.client.setex(redis_key, ttl, serialized_value)
            return bool(result)
            
        except RedisError as e:
            logger.error("Cache set error", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            redis_key = self._make_key(key)
            result = await self.client.delete(redis_key)
            return result > 0
        except RedisError as e:
            logger.error("Cache delete error", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            redis_key = self._make_key(key)
            result = await self.client.exists(redis_key)
            return result > 0
        except RedisError as e:
            logger.error("Cache exists error", key=key, error=str(e))
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            redis_pattern = self._make_key(pattern)
            keys = await self.client.keys(redis_pattern)
            if keys:
                result = await self.client.delete(*keys)
                return result
            return 0
        except RedisError as e:
            logger.error("Cache clear pattern error", pattern=pattern, error=str(e))
            return 0
    
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Increment counter in cache"""
        try:
            redis_key = self._make_key(key)
            result = await self.client.incrby(redis_key, amount)
            
            if ttl:
                await self.client.expire(redis_key, ttl)
            
            return result
        except RedisError as e:
            logger.error("Cache increment error", key=key, error=str(e))
            return 0


class RedisPubSub:
    """Redis pub/sub messaging"""
    
    def __init__(self, redis_client: redis.Redis):
        self.client = redis_client
        self._pubsub = None
    
    async def subscribe(self, *channels: str):
        """Subscribe to channels"""
        if not self._pubsub:
            self._pubsub = self.client.pubsub()
        
        await self._pubsub.subscribe(*channels)
        logger.info("Subscribed to channels", channels=channels)
    
    async def unsubscribe(self, *channels: str):
        """Unsubscribe from channels"""
        if self._pubsub:
            await self._pubsub.unsubscribe(*channels)
            logger.info("Unsubscribed from channels", channels=channels)
    
    async def publish(self, channel: str, message: Union[str, Dict[str, Any]]) -> int:
        """Publish message to channel"""
        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            
            result = await self.client.publish(channel, message)
            return result
        except RedisError as e:
            logger.error("Publish error", channel=channel, error=str(e))
            return 0
    
    async def listen(self):
        """Listen for messages"""
        if not self._pubsub:
            raise RuntimeError("Not subscribed to any channels")
        
        async for message in self._pubsub.listen():
            if message['type'] == 'message':
                try:
                    # Try to parse as JSON
                    data = json.loads(message['data'])
                    yield {
                        'channel': message['channel'],
                        'data': data,
                        'type': message['type']
                    }
                except json.JSONDecodeError:
                    # Return as string
                    yield {
                        'channel': message['channel'],
                        'data': message['data'],
                        'type': message['type']
                    }
    
    async def close(self):
        """Close pub/sub connection"""
        if self._pubsub:
            await self._pubsub.close()


class RedisSessionStore:
    """Redis-based session storage"""
    
    def __init__(self, redis_client: redis.Redis, prefix: str = "session"):
        self.client = redis_client
        self.prefix = prefix
    
    def _make_key(self, session_id: str) -> str:
        """Create session key"""
        return f"{self.prefix}:{session_id}"
    
    async def create_session(self, session_id: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Create new session"""
        try:
            redis_key = self._make_key(session_id)
            serialized_data = json.dumps(data)
            
            if ttl is None:
                ttl = settings.session_ttl
            
            result = await self.client.setex(redis_key, ttl, serialized_data)
            return bool(result)
        except RedisError as e:
            logger.error("Session create error", session_id=session_id, error=str(e))
            return False
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        try:
            redis_key = self._make_key(session_id)
            data = await self.client.get(redis_key)
            
            if data:
                return json.loads(data.decode('utf-8'))
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.error("Session get error", session_id=session_id, error=str(e))
            return None
    
    async def update_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Update session data"""
        try:
            redis_key = self._make_key(session_id)
            
            # Get current TTL
            ttl = await self.client.ttl(redis_key)
            if ttl <= 0:
                ttl = settings.session_ttl
            
            serialized_data = json.dumps(data)
            result = await self.client.setex(redis_key, ttl, serialized_data)
            return bool(result)
        except RedisError as e:
            logger.error("Session update error", session_id=session_id, error=str(e))
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        try:
            redis_key = self._make_key(session_id)
            result = await self.client.delete(redis_key)
            return result > 0
        except RedisError as e:
            logger.error("Session delete error", session_id=session_id, error=str(e))
            return False
    
    async def extend_session(self, session_id: str, ttl: Optional[int] = None) -> bool:
        """Extend session TTL"""
        try:
            redis_key = self._make_key(session_id)
            if ttl is None:
                ttl = settings.session_ttl
            
            result = await self.client.expire(redis_key, ttl)
            return bool(result)
        except RedisError as e:
            logger.error("Session extend error", session_id=session_id, error=str(e))
            return False


# Global Redis manager
redis_manager = RedisManager()

# Convenience functions
async def get_cache() -> RedisCache:
    """Get Redis cache instance"""
    return RedisCache(redis_manager.client)

async def get_pubsub() -> RedisPubSub:
    """Get Redis pub/sub instance"""
    return RedisPubSub(redis_manager.pubsub_client)

async def get_session_store() -> RedisSessionStore:
    """Get Redis session store instance"""
    return RedisSessionStore(redis_manager.client)

# Initialize and cleanup functions
async def init_redis():
    """Initialize Redis connections"""
    await redis_manager.initialize()

async def close_redis():
    """Close Redis connections"""
    await redis_manager.close()


__all__ = [
    "RedisManager",
    "RedisCache", 
    "RedisPubSub",
    "RedisSessionStore",
    "redis_manager",
    "get_cache",
    "get_pubsub", 
    "get_session_store",
    "init_redis",
    "close_redis",
]