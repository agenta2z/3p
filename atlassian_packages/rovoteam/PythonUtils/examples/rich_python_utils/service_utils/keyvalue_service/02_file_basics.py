"""
KeyValue Service Tutorial 2: File-Based Backend

Demonstrates the FileKeyValueService -- stores key-value pairs as individual
JSON files on disk. Data persists across restarts.

Topics covered:
    - Creating the service with a directory path
    - CRUD operations
    - Persistence: close, reopen, data survives
    - Namespace isolation
    - Statistics and context-manager usage

Prerequisites:
    No external dependencies (uses standard library only).

Usage:
    python 02_file_basics.py
"""

import shutil
import tempfile

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.keyvalue_service.file_keyvalue_service import (
    FileKeyValueService,
)


def main():
    tmpdir = tempfile.mkdtemp(prefix="kv_file_example_")

    try:
        # =============================================================
        # CORE CODE
        # =============================================================

        # 1. Create the service
        svc = FileKeyValueService(base_dir=tmpdir)
        svc_repr = repr(svc)
        ping_result = svc.ping()

        # 2. Store experiment parameters
        experiments = {
            "exp:alpha_decay": {
                "type": "nuclear_physics",
                "energy_range_MeV": [4.0, 8.0],
                "detector": "HPGe",
                "duration_hours": 72,
            },
            "exp:protein_folding": {
                "type": "biophysics",
                "temperature_K": 310,
                "solvent": "water",
                "duration_hours": 48,
            },
            "exp:cosmic_ray": {
                "type": "astrophysics",
                "altitude_km": 5.2,
                "detector": "scintillator_array",
                "duration_hours": 168,
            },
        }
        for key, params in experiments.items():
            svc.put(key, params)

        # 3. Retrieve and verify
        alpha = svc.get("exp:alpha_decay")
        keys_after_store = svc.keys()
        size_after_store = svc.size()

        # 4. Persistence: close and reopen
        svc.close()
        svc2 = FileKeyValueService(base_dir=tmpdir)
        reopened = svc2.get("exp:protein_folding")

        # 5. Namespace isolation
        svc2.put("config", {"beam_energy": 13.6}, namespace="project_alpha")
        svc2.put("config", {"beam_energy": 7.0},  namespace="project_beta")
        config_a = svc2.get("config", namespace="project_alpha")
        config_b = svc2.get("config", namespace="project_beta")
        ns_list = svc2.namespaces()

        # 6. Update and delete
        alpha2 = svc2.get("exp:alpha_decay")
        alpha2["duration_hours"] = 96
        svc2.put("exp:alpha_decay", alpha2)
        updated_duration = svc2.get("exp:alpha_decay")["duration_hours"]
        svc2.delete("exp:cosmic_ray")
        cosmic_exists = svc2.exists("exp:cosmic_ray")

        # 7. Stats and context manager
        stats = svc2.get_stats()
        svc2.close()

        with FileKeyValueService(base_dir=tmpdir) as ctx_svc:
            ctx_size = ctx_svc.size()

        # =============================================================
        # OUTPUT
        # =============================================================

        print("=" * 70)
        print("KeyValue Service Tutorial 2: File-Based Backend")
        print("=" * 70)
        print(f"\n    (Using temp directory: {tmpdir})")

        print("\n[1] Create the service")
        print("-" * 50)
        print(f"    Service created -> {svc_repr}")
        print(f"    Ping            -> {ping_result}")

        print("\n[2] Store experiment parameters (put)")
        print("-" * 50)
        for key, params in experiments.items():
            print(f"    Stored '{key}' -> {params['type']}")

        print("\n[3] Retrieve and verify")
        print("-" * 50)
        print(f"    get('exp:alpha_decay') -> detector={alpha['detector']}, duration={alpha['duration_hours']}h")
        print(f"    keys() -> {keys_after_store}")
        print(f"    size() -> {size_after_store}")

        print("\n[4] Persistence: close and reopen")
        print("-" * 50)
        print(f"    Service closed")
        print(f"    Reopened -> get('exp:protein_folding') -> temp={reopened['temperature_K']}K")
        print(f"    Data survives across service restarts!")

        print("\n[5] Namespace isolation")
        print("-" * 50)
        print(f"    project_alpha -> beam_energy={config_a['beam_energy']} TeV")
        print(f"    project_beta  -> beam_energy={config_b['beam_energy']} TeV")
        print(f"    namespaces()  -> {ns_list}")

        print("\n[6] Update and delete")
        print("-" * 50)
        print(f"    Updated alpha_decay duration -> {updated_duration}h")
        print(f"    Deleted 'exp:cosmic_ray', exists -> {cosmic_exists}")

        print("\n[7] Stats and context manager")
        print("-" * 50)
        print(f"    Stats -> {stats}")
        print(f"    Context manager: size() -> {ctx_size}")
        print(f"    Context manager exited cleanly")

        print("\n" + "=" * 70)
        print("Tutorial 2 complete -- FileKeyValueService basics!")
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
