"""
KeyValue Service Tutorial 4: Redis Backend

Demonstrates the RedisKeyValueService -- stores key-value pairs in a Redis
server. Provides the same API as all other backends but with networked
persistence and pipeline-optimized batch operations.

Topics covered:
    - Connecting to Redis
    - CRUD operations
    - Namespace isolation
    - Pipeline-optimized batch operations
    - Statistics
    - Cleanup

Prerequisites:
    pip install redis

    You also need a running Redis server:
        docker run -d --name redis-test -p 6379:6379 redis:latest
    or install Redis locally.

Usage:
    python 04_redis_basics.py
"""

import sys

try:
    import redis
except ImportError:
    print("This example requires the 'redis' package.")
    print("Install it with:  pip install redis")
    print("\nYou also need a running Redis server:")
    print("  docker run -d --name redis-test -p 6379:6379 redis:latest")
    sys.exit(0)

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.keyvalue_service.redis_keyvalue_service import (
    RedisKeyValueService,
)


def main():
    # Early exit: check Redis connectivity
    svc = RedisKeyValueService(host="localhost", port=6379, prefix="sci_example")

    if not svc.ping():
        print("Cannot connect to Redis. Is the server running?")
        print("Start it with: docker run -d --name redis-test -p 6379:6379 redis:latest")
        svc.close()
        return

    try:
        # =============================================================
        # CORE CODE
        # =============================================================

        # 1. Service info
        svc_repr = repr(svc)
        ping_result = svc.ping()

        # 2. Store sensor readings
        sensors = {
            "sensor:temp_lab1":     {"location": "Lab 1", "type": "temperature", "value": 22.5, "unit": "C"},
            "sensor:humidity_lab1": {"location": "Lab 1", "type": "humidity", "value": 45.2, "unit": "%"},
            "sensor:temp_lab2":     {"location": "Lab 2", "type": "temperature", "value": 20.1, "unit": "C"},
        }
        for key, reading in sensors.items():
            svc.put(key, reading)

        # 3. Retrieve values
        temp = svc.get("sensor:temp_lab1")
        missing = svc.get("no_such_key")

        # 4. Namespace isolation
        svc.put("alert_threshold", {"temp_max": 25.0}, namespace="safety")
        svc.put("alert_threshold", {"temp_max": 30.0}, namespace="industrial")
        safety = svc.get("alert_threshold", namespace="safety")
        indust = svc.get("alert_threshold", namespace="industrial")
        ns_list = svc.namespaces()

        # 5. Batch operations
        batch = {f"sample_{i}": {"mass_g": 1.5 + i * 0.1, "label": f"Sample {chr(65+i)}"} for i in range(5)}
        svc.put_many(batch, namespace="analysis")
        retrieved = svc.get_many(["sample_0", "sample_2", "sample_4"], namespace="analysis")
        batch_results = {}
        for k, v in retrieved.items():
            batch_results[k] = f"{v['label']}, {v['mass_g']}g"

        # 6. Statistics
        stats = svc.get_stats()

        # 7. Cleanup
        cleanup_results = {}
        for ns in svc.namespaces():
            count = svc.clear(namespace=ns)
            cleanup_results[ns] = count

        # =============================================================
        # OUTPUT
        # =============================================================

        print("=" * 70)
        print("KeyValue Service Tutorial 4: Redis Backend")
        print("=" * 70)

        print("\n[1] Connect to Redis")
        print("-" * 50)
        print(f"    Service created -> {svc_repr}")
        print(f"    Ping            -> {ping_result}")

        print("\n[2] Store lab sensor readings (put)")
        print("-" * 50)
        for key, reading in sensors.items():
            print(f"    Stored '{key}' -> {reading['type']}={reading['value']}{reading['unit']}")

        print("\n[3] Retrieve values (get)")
        print("-" * 50)
        print(f"    get('sensor:temp_lab1') -> {temp}")
        print(f"    get('no_such_key')      -> {missing}")

        print("\n[4] Namespace isolation")
        print("-" * 50)
        print(f"    safety     -> temp_max={safety['temp_max']}C")
        print(f"    industrial -> temp_max={indust['temp_max']}C")
        print(f"    namespaces() -> {ns_list}")

        print("\n[5] Pipeline-optimized batch operations")
        print("-" * 50)
        print(f"    put_many: stored {len(batch)} samples")
        for k, status in batch_results.items():
            print(f"    get_many('{k}') -> {status}")

        print("\n[6] Statistics")
        print("-" * 50)
        print(f"    All stats -> {stats}")

        print("\n[7] Cleanup")
        print("-" * 50)
        for ns, count in cleanup_results.items():
            print(f"    Cleared namespace '{ns}' -> {count} items removed")
        print(f"    Service closed")

    finally:
        svc.close()

    print("\n" + "=" * 70)
    print("Tutorial 4 complete -- RedisKeyValueService basics!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
