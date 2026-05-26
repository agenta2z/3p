"""
Tests for RedisKeyValueService.

Requires a running Redis server. Skipped automatically when redis is not
installed or the server is unreachable.

# Feature: knowledge-service-extraction
# Task 18.2: Write tests for Redis backend
"""

import uuid

import pytest

redis = pytest.importorskip("redis")

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from python_utils.service_utils.keyvalue_service.redis_keyvalue_service import (
    RedisKeyValueService,
)

from conftest import (
    json_value_strategy,
    key_strategy,
    namespace_strategy,
    kv_items_strategy,
)

# ── Availability fixture ──

_REDIS_AVAILABLE = None


def _check_redis():
    global _REDIS_AVAILABLE
    if _REDIS_AVAILABLE is None:
        try:
            c = redis.Redis(host="localhost", port=6379, decode_responses=True)
            c.ping()
            c.close()
            _REDIS_AVAILABLE = True
        except Exception:
            _REDIS_AVAILABLE = False
    return _REDIS_AVAILABLE


pytestmark = pytest.mark.requires_redis


@pytest.fixture()
def redis_svc():
    """Yield a RedisKeyValueService with a unique prefix to avoid collisions."""
    if not _check_redis():
        pytest.skip("Redis server not available")
    prefix = f"kv_test_{uuid.uuid4().hex[:8]}"
    svc = RedisKeyValueService(prefix=prefix)
    yield svc
    # Cleanup: remove all keys created by this test
    svc.clear()
    for ns in svc.namespaces():
        svc.clear(namespace=ns)
    svc.close()


# Shared Hypothesis settings
_fx_settings = settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


# ── Property 1: KV put/get round-trip ──


class TestRedisPutGetRoundTrip:
    """**Validates: Requirements 3.1**"""

    @given(key=key_strategy(), value=json_value_strategy(), namespace=namespace_strategy())
    @_fx_settings
    def test_put_get_round_trip(self, redis_svc, key, value, namespace):
        redis_svc.put(key, value, namespace=namespace)
        assert redis_svc.get(key, namespace=namespace) == value


# ── Property 2: KV upsert overwrites ──


class TestRedisUpsertOverwrites:
    """**Validates: Requirements 1.5**"""

    @given(
        key=key_strategy(),
        v1=json_value_strategy(),
        v2=json_value_strategy(),
        namespace=namespace_strategy(),
    )
    @_fx_settings
    def test_upsert_overwrites(self, redis_svc, key, v1, v2, namespace):
        assume(v1 != v2)
        redis_svc.put(key, v1, namespace=namespace)
        redis_svc.put(key, v2, namespace=namespace)
        assert redis_svc.get(key, namespace=namespace) == v2


# ── Property 3: KV batch equals individual ──


class TestRedisBatchEqualsIndividual:
    """**Validates: Requirements 1.2**"""

    @given(items=kv_items_strategy(min_size=1, max_size=10), namespace=namespace_strategy())
    @_fx_settings
    def test_batch_equals_individual(self, redis_svc, items, namespace):
        non_none_items = {k: v for k, v in items.items() if v is not None}
        redis_svc.put_many(items, namespace=namespace)
        batch_result = redis_svc.get_many(list(items.keys()), namespace=namespace)
        individual_result = {}
        for k in items:
            val = redis_svc.get(k, namespace=namespace)
            if val is not None:
                individual_result[k] = val
        assert batch_result == individual_result
        for k, v in non_none_items.items():
            assert k in batch_result
            assert batch_result[k] == v


# ── Unit tests ──


class TestRedisUnitOperations:
    """Unit tests for Redis-specific behaviour."""

    def test_get_nonexistent_returns_none(self, redis_svc):
        assert redis_svc.get("no_such_key") is None

    def test_delete_nonexistent_returns_false(self, redis_svc):
        assert redis_svc.delete("no_such_key") is False

    def test_exists(self, redis_svc):
        redis_svc.put("k", "v")
        assert redis_svc.exists("k") is True
        assert redis_svc.exists("nope") is False

    def test_keys_and_size(self, redis_svc):
        redis_svc.put("a", 1, namespace="ns1")
        redis_svc.put("b", 2, namespace="ns1")
        assert sorted(redis_svc.keys(namespace="ns1")) == ["a", "b"]
        assert redis_svc.size(namespace="ns1") == 2

    def test_clear(self, redis_svc):
        redis_svc.put("x", 1, namespace="ns")
        redis_svc.put("y", 2, namespace="ns")
        removed = redis_svc.clear(namespace="ns")
        assert removed == 2
        assert redis_svc.size(namespace="ns") == 0

    def test_namespaces(self, redis_svc):
        redis_svc.put("a", 1, namespace="alpha")
        redis_svc.put("b", 2, namespace="beta")
        ns = redis_svc.namespaces()
        assert "alpha" in ns
        assert "beta" in ns

    def test_ping(self, redis_svc):
        assert redis_svc.ping() is True

    def test_context_manager(self):
        if not _check_redis():
            pytest.skip("Redis server not available")
        prefix = f"kv_ctx_{uuid.uuid4().hex[:8]}"
        with RedisKeyValueService(prefix=prefix) as svc:
            svc.put("k", "v")
            assert svc.get("k") == "v"
            svc.clear()

    def test_get_stats(self, redis_svc):
        redis_svc.put("a", 1, namespace="ns")
        stats = redis_svc.get_stats(namespace="ns")
        assert stats["backend"] == "redis"
        assert stats["keys"] == 1
        all_stats = redis_svc.get_stats()
        assert "namespace_count" in all_stats

    def test_repr(self, redis_svc):
        r = repr(redis_svc)
        assert "RedisKeyValueService" in r
        assert "closed=False" in r
