"""
Redis KeyValue Service

Redis-backed key-value storage service using redis-py.

Keys are stored as ``{prefix}:{namespace}:{key}`` where prefix defaults
to ``"kv"``.  Values are JSON-serialized strings stored via GET/SET.

Batch operations (get_many / put_many) override the base-class defaults
with Redis pipeline-based implementations for reduced round-trips.

Best suited for:
- Multi-process / distributed applications
- High-throughput key-value workloads
- Scenarios requiring TTL or pub/sub alongside KV storage

Limitations:
- Requires a running Redis server
- Values must be JSON-serializable (binary blobs need base64 encoding)

Usage:
    from python_utils.service_utils.keyvalue_service.redis_keyvalue_service import (
        RedisKeyValueService,
    )

    service = RedisKeyValueService(host="localhost", port=6379)
    service.put("my_key", {"name": "Alice"}, namespace="users")
    value = service.get("my_key", namespace="users")

    # Context manager
    with RedisKeyValueService() as svc:
        svc.put("key", "value")
        result = svc.get("key")
"""

import json
from typing import Any, Optional, List, Dict

from attr import attrs, attrib

from .keyvalue_service_base import KeyValueServiceBase

_DEFAULT_NAMESPACE = "_default"


@attrs(slots=False, repr=False)
class RedisKeyValueService(KeyValueServiceBase):
    """
    Redis-backed key-value storage service.

    Keys are stored as ``{prefix}:{namespace}:{key}``.  Values are
    JSON-serialized strings.

    Overrides ``get_many`` and ``put_many`` with Redis pipeline-based
    batch operations for reduced round-trips.

    Attributes:
        host: Redis server hostname (default ``"localhost"``).
        port: Redis server port (default ``6379``).
        db: Redis database index (default ``0``).
        prefix: Key prefix for all keys managed by this service
                (default ``"kv"``).
        password: Optional Redis password.
        _client: The underlying ``redis.Redis`` client instance.
        _closed: Flag indicating if the service has been closed.
    """

    host: str = attrib(default="localhost")
    port: int = attrib(default=6379)
    db: int = attrib(default=0)
    prefix: str = attrib(default="kv")
    password: Optional[str] = attrib(default=None, repr=False)
    _client: Any = attrib(init=False, default=None)
    _closed: bool = attrib(init=False, default=False)

    def __attrs_post_init__(self):
        """Initialize the Redis client connection."""
        import redis as _redis

        self._client = _redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=True,
        )

    # ── Internal helpers ──

    def _resolve_namespace(self, namespace: Optional[str]) -> str:
        """Resolve namespace, mapping None to '_default'."""
        return namespace if namespace is not None else _DEFAULT_NAMESPACE

    def _make_redis_key(self, key: str, namespace: str) -> str:
        """Build the full Redis key: ``{prefix}:{namespace}:{key}``."""
        return f"{self.prefix}:{namespace}:{key}"

    def _parse_redis_key(self, redis_key: str) -> tuple:
        """Parse a Redis key back into (namespace, key).

        The key format is ``{prefix}:{namespace}:{key}`` where *key*
        itself may contain colons, so we split on the first two colons
        only.
        """
        # prefix:namespace:key  — split at most 2 times
        parts = redis_key.split(":", 2)
        if len(parts) < 3:
            return None, None
        return parts[1], parts[2]

    # ── Core operations ──

    def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        ns = self._resolve_namespace(namespace)
        raw = self._client.get(self._make_redis_key(key, ns))
        if raw is None:
            return None
        return json.loads(raw)

    def put(self, key: str, value: Any, namespace: Optional[str] = None) -> None:
        ns = self._resolve_namespace(namespace)
        self._client.set(self._make_redis_key(key, ns), json.dumps(value))

    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        ns = self._resolve_namespace(namespace)
        return self._client.delete(self._make_redis_key(key, ns)) > 0

    def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        ns = self._resolve_namespace(namespace)
        return self._client.exists(self._make_redis_key(key, ns)) > 0

    def keys(self, namespace: Optional[str] = None) -> List[str]:
        """List all keys in a namespace using SCAN (non-blocking)."""
        ns = self._resolve_namespace(namespace)
        pattern = f"{self.prefix}:{ns}:*"
        result = []
        cursor = 0
        while True:
            cursor, batch = self._client.scan(cursor=cursor, match=pattern, count=100)
            for redis_key in batch:
                _, k = self._parse_redis_key(redis_key)
                if k is not None:
                    result.append(k)
            if cursor == 0:
                break
        return result

    def size(self, namespace: Optional[str] = None) -> int:
        return len(self.keys(namespace=namespace))

    def clear(self, namespace: Optional[str] = None) -> int:
        ns = self._resolve_namespace(namespace)
        pattern = f"{self.prefix}:{ns}:*"
        count = 0
        cursor = 0
        while True:
            cursor, batch = self._client.scan(cursor=cursor, match=pattern, count=100)
            if batch:
                count += self._client.delete(*batch)
            if cursor == 0:
                break
        return count

    def namespaces(self) -> List[str]:
        """Derive namespaces from key prefix scanning."""
        pattern = f"{self.prefix}:*"
        ns_set: set = set()
        cursor = 0
        while True:
            cursor, batch = self._client.scan(cursor=cursor, match=pattern, count=100)
            for redis_key in batch:
                ns, _ = self._parse_redis_key(redis_key)
                if ns is not None:
                    ns_set.add(ns)
            if cursor == 0:
                break
        return list(ns_set)

    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        if namespace is not None:
            return {
                "backend": "redis",
                "host": self.host,
                "port": self.port,
                "prefix": self.prefix,
                "namespace": namespace,
                "keys": self.size(namespace=namespace),
            }
        all_ns = self.namespaces()
        total = sum(self.size(namespace=ns) for ns in all_ns)
        return {
            "backend": "redis",
            "host": self.host,
            "port": self.port,
            "prefix": self.prefix,
            "namespace_count": len(all_ns),
            "total_keys": total,
            "namespaces": {ns: self.size(namespace=ns) for ns in all_ns},
        }

    def ping(self) -> bool:
        if self._closed or self._client is None:
            return False
        try:
            return self._client.ping()
        except Exception:
            return False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            if self._client is not None:
                self._client.close()
                self._client = None

    # ── Optimized batch methods using Redis pipelines ──

    def get_many(self, keys: List[str], namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get multiple values using a single Redis pipeline round-trip."""
        if not keys:
            return {}
        ns = self._resolve_namespace(namespace)
        pipe = self._client.pipeline(transaction=False)
        for key in keys:
            pipe.get(self._make_redis_key(key, ns))
        raw_values = pipe.execute()
        result = {}
        for key, raw in zip(keys, raw_values):
            if raw is not None:
                value = json.loads(raw)
                if value is not None:
                    result[key] = value
        return result

    def put_many(self, items: Dict[str, Any], namespace: Optional[str] = None) -> None:
        """Store multiple key-value pairs using a single Redis pipeline round-trip."""
        if not items:
            return
        ns = self._resolve_namespace(namespace)
        pipe = self._client.pipeline(transaction=False)
        for key, value in items.items():
            pipe.set(self._make_redis_key(key, ns), json.dumps(value))
        pipe.execute()

    # ── Context manager protocol ──

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        if self._closed:
            return (
                f"RedisKeyValueService("
                f"host='{self.host}', port={self.port}, "
                f"prefix='{self.prefix}', closed=True)"
            )
        return (
            f"RedisKeyValueService("
            f"host='{self.host}', port={self.port}, "
            f"db={self.db}, prefix='{self.prefix}', "
            f"closed={self._closed})"
        )
