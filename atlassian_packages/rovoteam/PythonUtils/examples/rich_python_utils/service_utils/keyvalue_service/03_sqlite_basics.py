"""
KeyValue Service Tutorial 3: SQLite Backend

Demonstrates the SQLiteKeyValueService -- stores key-value pairs in a SQLite
database. Supports both persistent (file-based) and in-memory modes.

Topics covered:
    - Creating the service with a database path
    - CRUD operations
    - Optimized batch operations (put_many / get_many via SQL)
    - Persistence: close, reopen, data survives
    - In-memory mode with ":memory:"
    - Statistics and context-manager usage

Prerequisites:
    No external dependencies (sqlite3 is in the standard library).

Usage:
    python 03_sqlite_basics.py
"""

import os
import shutil
import tempfile

from resolve_path import resolve_path
resolve_path()

from python_utils.service_utils.keyvalue_service.sqlite_keyvalue_service import (
    SQLiteKeyValueService,
)


def main():
    tmpdir = tempfile.mkdtemp(prefix="kv_sqlite_example_")
    db_path = os.path.join(tmpdir, "research.db")

    try:
        # =============================================================
        # CORE CODE
        # =============================================================

        # 1. Create the service
        svc = SQLiteKeyValueService(db_path=db_path)
        svc_repr = repr(svc)
        ping_result = svc.ping()

        # 2. Store calibration data
        calibrations = {
            "nmr_600": {
                "instrument": "NMR Spectrometer",
                "model": "Bruker 600MHz",
                "last_calibrated": "2024-11-15",
                "parameters": {"field_strength": 14.1, "shim_quality": 0.98},
            },
            "xrd_d8": {
                "instrument": "X-Ray Diffractometer",
                "model": "Bruker D8",
                "last_calibrated": "2024-10-20",
                "parameters": {"tube_voltage_kV": 40, "tube_current_mA": 30},
            },
            "hplc_agilent": {
                "instrument": "HPLC System",
                "model": "Agilent 1260",
                "last_calibrated": "2024-12-01",
                "parameters": {"flow_rate_mL_min": 1.0, "column_temp_C": 25},
            },
        }
        for key, data in calibrations.items():
            svc.put(key, data)

        # 3. CRUD operations
        nmr = svc.get("nmr_600")
        exists_nmr = svc.exists("nmr_600")
        exists_mass_spec = svc.exists("mass_spec")

        nmr["last_calibrated"] = "2025-01-10"
        svc.put("nmr_600", nmr)
        updated_cal_date = svc.get("nmr_600")["last_calibrated"]

        svc.delete("hplc_agilent")
        size_after_delete = svc.size()

        # 4. Batch operations
        reagents = {
            f"reagent_{i}": {"name": f"Reagent {chr(65+i)}", "purity": 0.95 + i * 0.01, "lot": f"LOT-{i:04d}"}
            for i in range(10)
        }
        svc.put_many(reagents, namespace="chemistry_lab")
        retrieved = svc.get_many(["reagent_0", "reagent_5", "reagent_9", "missing"], namespace="chemistry_lab")
        batch_results = {}
        for k, v in retrieved.items():
            batch_results[k] = f"purity={v['purity']}" if v else "not found"

        # 5. Persistence: close and reopen
        svc.close()
        svc2 = SQLiteKeyValueService(db_path=db_path)
        xrd = svc2.get("xrd_d8")
        size_default = svc2.size()
        size_chem = svc2.size(namespace="chemistry_lab")
        svc2.close()

        # 6. In-memory mode
        with SQLiteKeyValueService(db_path=":memory:") as mem_svc:
            mem_svc.put("temp_key", {"data": "this lives only in RAM"})
            mem_value = mem_svc.get("temp_key")
            mem_size = mem_svc.size()

        # 7. Stats and final context manager
        with SQLiteKeyValueService(db_path=db_path) as ctx_svc:
            stats = ctx_svc.get_stats()
            ns = ctx_svc.namespaces()

        # =============================================================
        # OUTPUT
        # =============================================================

        print("=" * 70)
        print("KeyValue Service Tutorial 3: SQLite Backend")
        print("=" * 70)
        print(f"\n    (Using database: {db_path})")

        print("\n[1] Create the service")
        print("-" * 50)
        print(f"    Service created -> {svc_repr}")
        print(f"    Ping            -> {ping_result}")

        print("\n[2] Store instrument calibration data (put)")
        print("-" * 50)
        for key, data in calibrations.items():
            print(f"    Stored '{key}' -> {data['instrument']}")

        print("\n[3] CRUD operations")
        print("-" * 50)
        print(f"    get('nmr_600')      -> {nmr['model']}, calibrated {nmr['last_calibrated']}")
        print(f"    exists('nmr_600')   -> {exists_nmr}")
        print(f"    exists('mass_spec') -> {exists_mass_spec}")
        print(f"    Updated nmr_600 calibration date -> {updated_cal_date}")
        print(f"    Deleted 'hplc_agilent', size -> {size_after_delete}")

        print("\n[4] Batch operations (optimized SQL)")
        print("-" * 50)
        print(f"    put_many: stored {len(reagents)} reagents in 'chemistry_lab'")
        for k, status in batch_results.items():
            print(f"    get_many('{k}') -> {status}")

        print("\n[5] Persistence: close and reopen")
        print("-" * 50)
        print(f"    Service closed")
        print(f"    Reopened -> get('xrd_d8') -> {xrd['model']}")
        print(f"    Default namespace size   -> {size_default}")
        print(f"    chemistry_lab size       -> {size_chem}")

        print("\n[6] In-memory mode (db_path=':memory:')")
        print("-" * 50)
        print(f"    Stored in memory -> {mem_value}")
        print(f"    size()           -> {mem_size}")
        print(f"    In-memory data gone after close (no persistence)")

        print("\n[7] Stats and final context manager")
        print("-" * 50)
        print(f"    Stats      -> {stats}")
        print(f"    Namespaces -> {ns}")
        print(f"    Context manager exited cleanly")

        print("\n" + "=" * 70)
        print("Tutorial 3 complete -- SQLiteKeyValueService basics!")
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
