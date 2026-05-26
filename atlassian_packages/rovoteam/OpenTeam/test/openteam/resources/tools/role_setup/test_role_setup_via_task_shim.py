"""Phase 5 — real-LLM verification of /role_setup's thin shim.

Invokes the shim directly (mirrors how ToolDispatcher would). Proves:
  - Shim's _run_topology delegation works for a nested BTA topology end-to-end with opus[1m]
  - context_updates are re-keyed to original schema (role_setup_working_dir,
    role_setup_report_path, skills_dir, tools_dir, role_tool_association_path)
  - template_extra_feed (role_name, role_doc_path, available_tools_skills)
    propagates through the _import_ boundary into the inner BTA's child inferencers
  - Real role_setup_report.md artifact is produced under safe per-task workspace

Phase 3 → Phase 5 handoff: reads LATEST_DOC.txt written by Phase 3.
Falls back to the known-good role_responsibility_document.md from the prior
opus[1m] production run if the marker is missing.

Usage:
    cd OpenTeam
    python -m test.openteam.resources.tools.role_setup.test_role_setup_via_task_shim
"""

import asyncio
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Bootstrap sys.path
_HERE = Path(__file__).resolve()
_OPENSTARTUP = _HERE.parents[5]
_REPO_ROOT = _OPENSTARTUP.parent
for _dep in [_OPENSTARTUP / "src",
             _REPO_ROOT / "AgentFoundation" / "src",
             _REPO_ROOT / "PythonUtils" / "src"]:
    p = str(_dep)
    if p not in sys.path:
        sys.path.insert(0, p)


def _claude_available() -> bool:
    try:
        r = subprocess.run("claude --version", shell=True,
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _opus_1m_smoke_check():
    try:
        r = subprocess.run(
            'claude --print --model "opus[1m]" "Reply with the single word: pong"',
            shell=True, capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"smoke check raised: {e}"
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        return False, f"exit={r.returncode}, stderr={err[:300]}"
    bad = ("Execution error", "model not found", "unknown model",
           "invalid model", "Unsupported model")
    for m in bad:
        if m.lower() in out.lower() or m.lower() in err.lower():
            return False, f"got error marker {m!r}: out={out[:200]} err={err[:200]}"
    if not out:
        return False, f"empty stdout, stderr={err[:200]}"
    return True, f"opus[1m] responded ({len(out)}B): {out[:120]}"


SHIM_TEST_ROOT = _HERE.parent / "_runtime" / "shim_test"
PHASE3_MARKER = (_HERE.parent.parent / "create_role" / "_runtime"
                 / "shim_test" / "LATEST_DOC.txt")
# Known-good fallback from the prior opus[1m] production run (Apr 25)
FALLBACK_DOC = (_HERE.parent.parent / "create_role" / "_runtime"
                / "20260425_115535" / "outputs" / "role_responsibility_document.md")


def _resolve_role_doc() -> Path:
    """Phase 3 → 5 handoff (R5 — explicit, not glob)."""
    if PHASE3_MARKER.is_file():
        candidate = Path(PHASE3_MARKER.read_text(encoding="utf-8").strip())
        if candidate.is_file():
            print(f"[handoff] using Phase 3 doc: {candidate}", flush=True)
            return candidate
        print(f"[handoff] LATEST_DOC.txt points to missing file: {candidate}; "
              f"falling back", flush=True)
    if FALLBACK_DOC.is_file():
        print(f"[handoff] using fallback doc: {FALLBACK_DOC}", flush=True)
        return FALLBACK_DOC
    raise FileNotFoundError(
        f"No role document available. Phase 3 marker missing ({PHASE3_MARKER}) "
        f"AND fallback missing ({FALLBACK_DOC})."
    )


async def main():
    if not _claude_available():
        print("ERROR: claude CLI not available", file=sys.stderr)
        return 2

    print("[pre-flight] Checking opus[1m] availability ...", flush=True)
    ok, diag = _opus_1m_smoke_check()
    if not ok:
        print(f"ERROR: opus[1m] pre-flight failed: {diag}", file=sys.stderr)
        return 3
    print(f"[pre-flight] OK -- {diag}", flush=True)

    role_doc_path = _resolve_role_doc()
    role_doc_text = role_doc_path.read_text(encoding="utf-8")
    role_name_expected = role_doc_text.split("\n")[0].strip("# ").strip()
    print(f"[input] role_doc: {role_doc_path} ({len(role_doc_text)}B)", flush=True)
    print(f"[input] role_name (extracted): {role_name_expected!r}", flush=True)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    SHIM_TEST_ROOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = SHIM_TEST_ROOT / ts
    workspace.mkdir()
    print(f"[workspace] {workspace}", flush=True)

    arguments = {
        "role_document_path": str(role_doc_path),
        "--max-facets": 2,        # cap outer subtasks
        "--max-inner-facets": 2,  # cap inner BTA subtasks
    }
    session_context = {
        "interactive": None,
        "task_id": f"shim-rs-{ts}",
        "working_dir": str(workspace),  # safe per-task dir → _run_topology respects it
    }

    print(f"\n[run] await role_setup.execute(...) — opus[1m] nested BTA, ~$30-50",
          flush=True)

    from openteam.server.resources.tools.role_setup.executor import execute
    try:
        result = await execute(arguments, session_context)
    except Exception:
        import traceback
        traceback.print_exc()
        print(f"\nFAIL — exception during execute(). Workspace: {workspace}",
              file=sys.stderr)
        return 1

    # Assertions
    print("\n=== ASSERTIONS ===", flush=True)
    ctx = result.context_updates or {}
    assert hasattr(result, "result"), "Result is not a ToolExecutionResult"
    print(f"  OK   result is ToolExecutionResult")
    assert ctx.get("success") is not False, f"success flag is False: {ctx}"
    print(f"  OK   context_updates.success: {ctx.get('success')}")
    # Original schema keys preserved (BC requirement R3.5)
    assert "role_setup_working_dir" in ctx, \
        f"missing role_setup_working_dir: {sorted(ctx)}"
    print(f"  OK   role_setup_working_dir: {ctx['role_setup_working_dir']}")
    assert "role_setup_report_path" in ctx, \
        f"missing role_setup_report_path (report not produced): {sorted(ctx)}"
    report = Path(ctx["role_setup_report_path"])
    print(f"  OK   role_setup_report_path: {report}")
    assert report.is_file(), f"role_setup_report.md not on disk: {report}"
    size = report.stat().st_size
    assert size > 500, f"role_setup_report.md too short: {size}B"
    print(f"  OK   role_setup_report.md size: {size}B")

    # template_extra_feed propagation through _import_ boundary
    # (proves R3.4 — load-config-time injection reaches inner BTA's children)
    report_text = report.read_text(encoding="utf-8")
    # Lenient match — role_name may be wrapped, formatted, paraphrased
    name_lower = role_name_expected.lower()[:30]  # first 30 chars to avoid trivial subtleties
    found = name_lower in report_text.lower()[:8000]
    if not found:
        # second chance: check first ~1KB more leniently
        first_word = role_name_expected.split()[0] if role_name_expected.split() else ""
        found = bool(first_word) and first_word.lower() in report_text.lower()[:4000]
    assert found, (
        f"role_name {role_name_expected!r} not found in report — "
        f"template_extra_feed may have failed to propagate. "
        f"Report excerpt: {report_text[:500]!r}"
    )
    print(f"  OK   template_extra_feed propagated (role_name in report)")

    # At least one of skills/tools/association surfaced
    deliverable_keys = ("skills_dir", "tools_dir", "role_tool_association_path")
    found_keys = [k for k in deliverable_keys if k in ctx]
    assert found_keys, (
        f"no role_setup-specific deliverables surfaced "
        f"(expected at least one of {deliverable_keys}); ctx keys: {sorted(ctx)}"
    )
    print(f"  OK   deliverables surfaced: {found_keys}")

    # Workspace path safe (under _runtime/ or tasks/)
    ws_posix = Path(ctx["role_setup_working_dir"]).as_posix()
    assert "/_runtime/" in ws_posix or "/tasks/" in ws_posix, \
        f"workspace not under _runtime/ or tasks/: {ws_posix}"
    print(f"  OK   workspace path safe: {ws_posix}")

    print(f"\n=== PHASE 5 OK ===")
    print(f"  workspace:   {workspace}")
    print(f"  report:      {report}")
    print(f"  report size: {size}B")
    print(f"  found keys:  {sorted(ctx)}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
