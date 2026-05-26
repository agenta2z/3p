"""
KeyValue Service Tutorial 1: In-Memory Backend

Demonstrates all core operations of the KeyValue service using the
MemoryKeyValueService -- no external dependencies, no files on disk.

Topics covered:
    - Creating and pinging the service
    - Storing and retrieving values (put / get)
    - Checking existence and listing keys
    - Updating values
    - Namespace isolation
    - Batch operations (put_many / get_many)
    - Statistics, clearing, and context-manager usage

Usage:
    python 01_memory_basics.py
"""

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.keyvalue_service.memory_keyvalue_service import (
    MemoryKeyValueService,
)


def main():
    # =================================================================
    # CORE CODE
    # =================================================================

    # 1. Create the service
    svc = MemoryKeyValueService()
    svc_repr = repr(svc)
    ping_result = svc.ping()

    # 2. Store researcher profiles
    researchers = {
        "alice": {"name": "Alice Chen", "field": "quantum_physics", "h_index": 42, "institution": "MIT"},
        "bob":   {"name": "Bob Patel", "field": "bioinformatics", "h_index": 35, "institution": "Stanford"},
        "carol": {"name": "Carol Kim", "field": "quantum_physics", "h_index": 28, "institution": "MIT"},
    }
    for key, profile in researchers.items():
        svc.put(key, profile)

    # 3. Retrieve values
    alice = svc.get("alice")
    missing = svc.get("nobody")

    # 4. Check existence
    exists_bob = svc.exists("bob")
    exists_nobody = svc.exists("nobody")

    # 5. Update a value
    alice["h_index"] = 45
    svc.put("alice", alice)
    updated_alice = svc.get("alice")

    # 6. List keys and check size
    keys = svc.keys()
    size = svc.size()

    # 7. Namespace isolation
    svc.put("config", {"max_iterations": 1000, "tolerance": 1e-6}, namespace="project_alpha")
    svc.put("config", {"max_iterations": 500,  "tolerance": 1e-3}, namespace="project_beta")
    alpha_config = svc.get("config", namespace="project_alpha")
    beta_config  = svc.get("config", namespace="project_beta")

    # 8. Delete operations
    deleted = svc.delete("carol")
    exists_carol_after = svc.exists("carol")
    deleted_again = svc.delete("carol")

    # 9. Batch operations
    instruments = {
        "nmr_600":  {"instrument": "NMR Spectrometer", "model": "Bruker 600MHz"},
        "xrd_d8":   {"instrument": "X-Ray Diffractometer", "model": "Bruker D8"},
        "sem_zeiss": {"instrument": "SEM", "model": "Zeiss Sigma"},
    }
    svc.put_many(instruments, namespace="lab_equipment")
    retrieved = svc.get_many(["nmr_600", "xrd_d8", "missing_key"], namespace="lab_equipment")
    batch_results = {}
    for k, v in retrieved.items():
        batch_results[k] = v['model'] if v else "not found"

    # 10. Statistics
    stats = svc.get_stats()
    stats_alpha = svc.get_stats(namespace="project_alpha")

    # 11. Namespaces and clear
    ns_list = svc.namespaces()
    removed = svc.clear(namespace="lab_equipment")
    size_lab_after = svc.size(namespace="lab_equipment")

    # 12. Context manager
    with MemoryKeyValueService() as tmp_svc:
        tmp_svc.put("key", "value")
        ctx_value = tmp_svc.get("key")

    # 13. Close
    svc.close()
    ping_after_close = svc.ping()

    # =================================================================
    # OUTPUT
    # =================================================================

    print("=" * 70)
    print("KeyValue Service Tutorial 1: In-Memory Backend")
    print("=" * 70)

    print("\n[1] Create the service")
    print("-" * 50)
    print(f"    Service created -> {svc_repr}")
    print(f"    Ping            -> {ping_result}")

    print("\n[2] Store researcher profiles (put)")
    print("-" * 50)
    for key, profile in researchers.items():
        print(f"    Stored '{key}' -> {profile['name']}")

    print("\n[3] Retrieve values (get)")
    print("-" * 50)
    print(f"    get('alice')  -> {alice}")
    print(f"    get('nobody') -> {missing}  (None means not found)")

    print("\n[4] Check existence (exists)")
    print("-" * 50)
    print(f"    exists('bob')    -> {exists_bob}")
    print(f"    exists('nobody') -> {exists_nobody}")

    print("\n[5] Update a value (put with same key)")
    print("-" * 50)
    print(f"    Alice's updated h-index -> {updated_alice['h_index']}")

    print("\n[6] List keys and check size")
    print("-" * 50)
    print(f"    keys() -> {keys}")
    print(f"    size() -> {size}")

    print("\n[7] Namespace isolation")
    print("-" * 50)
    print(f"    project_alpha config -> tolerance={alpha_config['tolerance']}")
    print(f"    project_beta  config -> tolerance={beta_config['tolerance']}")
    print(f"    Same key, different namespaces, different values!")

    print("\n[8] Delete operations")
    print("-" * 50)
    print(f"    delete('carol')       -> {deleted}")
    print(f"    exists('carol')       -> {exists_carol_after}")
    print(f"    delete('carol') again -> {deleted_again}  (already gone)")

    print("\n[9] Batch operations (put_many / get_many)")
    print("-" * 50)
    print(f"    put_many: stored {len(instruments)} instruments")
    for k, status in batch_results.items():
        print(f"    get_many('{k}') -> {status}")

    print("\n[10] Statistics (get_stats)")
    print("-" * 50)
    print(f"    All namespaces -> {stats}")
    print(f"    project_alpha  -> {stats_alpha}")

    print("\n[11] Namespaces and clear")
    print("-" * 50)
    print(f"    namespaces()            -> {ns_list}")
    print(f"    clear('lab_equipment')  -> removed {removed} items")
    print(f"    size('lab_equipment')   -> {size_lab_after}")

    print("\n[12] Context manager usage")
    print("-" * 50)
    print(f"    Inside context: get('key') -> {ctx_value}")
    print(f"    After context: service is automatically closed")

    print("\n[13] Close service")
    print("-" * 50)
    print(f"    Service closed. Ping -> {ping_after_close}")

    print("\n" + "=" * 70)
    print("Tutorial 1 complete -- MemoryKeyValueService basics!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
