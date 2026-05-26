"""
KeyValue Service Tutorial 5: Batch Operations Across Backends

Compares batch operations (put_many / get_many) across Memory and SQLite
backends. Both return identical data -- the only difference is the underlying
storage engine.

Topics covered:
    - Generating bulk experiment data
    - Timing put_many / get_many on MemoryKeyValueService
    - Timing put_many / get_many on SQLiteKeyValueService
    - Verifying identical results across backends

Prerequisites:
    No external dependencies.

Usage:
    python 05_batch_operations.py
"""

import os
import shutil
import tempfile
import time

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.keyvalue_service.memory_keyvalue_service import (
    MemoryKeyValueService,
)
from python_utils.service_utils.keyvalue_service.sqlite_keyvalue_service import (
    SQLiteKeyValueService,
)


def main():
    tmpdir = tempfile.mkdtemp(prefix="kv_batch_example_")

    try:
        # =============================================================
        # CORE CODE
        # =============================================================

        # 1. Generate test data
        entries = {}
        for i in range(50):
            entries[f"exp_{i:04d}"] = {
                "title": f"Experiment {i}",
                "temperature_K": 273.15 + i * 2,
                "pressure_atm": 1.0 + i * 0.05,
                "duration_min": 30 + i,
                "researcher": ["Alice", "Bob", "Carol"][i % 3],
                "successful": i % 5 != 0,
            }
        num_entries = len(entries)
        sample_keys = list(entries.keys())[:10]

        # 2. Memory backend
        with MemoryKeyValueService() as mem_svc:
            t0 = time.perf_counter()
            mem_svc.put_many(entries)
            mem_put_ms = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            mem_results = mem_svc.get_many(sample_keys)
            mem_get_ms = (time.perf_counter() - t0) * 1000

            mem_size = mem_svc.size()

        # 3. SQLite backend
        db_path = os.path.join(tmpdir, "batch_test.db")
        with SQLiteKeyValueService(db_path=db_path) as sql_svc:
            t0 = time.perf_counter()
            sql_svc.put_many(entries)
            sql_put_ms = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            sql_results = sql_svc.get_many(sample_keys)
            sql_get_ms = (time.perf_counter() - t0) * 1000

            sql_size = sql_svc.size()

        # 4. Verify identical results
        all_match = True
        for key in sample_keys:
            if mem_results[key] != sql_results[key]:
                all_match = False
                break

        sample_key = sample_keys[0]
        sample = mem_results[sample_key]

        # =============================================================
        # OUTPUT
        # =============================================================

        print("=" * 70)
        print("KeyValue Service Tutorial 5: Batch Operations")
        print("=" * 70)

        print("\n[1] Generate test data")
        print("-" * 50)
        print(f"    Generated {num_entries} experiment entries")

        print("\n[2] MemoryKeyValueService -- batch operations")
        print("-" * 50)
        print(f"    put_many({num_entries} items) -> {mem_put_ms:.2f} ms")
        print(f"    get_many({len(sample_keys)} keys)  -> {mem_get_ms:.2f} ms")
        print(f"    size() -> {mem_size}")

        print("\n[3] SQLiteKeyValueService -- batch operations")
        print("-" * 50)
        print(f"    put_many({num_entries} items) -> {sql_put_ms:.2f} ms")
        print(f"    get_many({len(sample_keys)} keys)  -> {sql_get_ms:.2f} ms")
        print(f"    size() -> {sql_size}")

        print("\n[4] Verify identical results across backends")
        print("-" * 50)
        if all_match:
            print(f"    All {len(sample_keys)} retrieved values match across backends!")
        else:
            print(f"    Mismatch detected in retrieved values")
        print(f"    Sample -- '{sample_key}': researcher={sample['researcher']}, "
              f"temp={sample['temperature_K']}K")

        print("\n" + "=" * 70)
        print("Tutorial 5 complete -- batch operations across backends!")
        print("=" * 70)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
