"""Real-CLI integration test for ``/create_role``.

Spawns ``python -m openteam.server.resources.tools.create_role`` as a real
subprocess to validate the FULL CLI module code path end-to-end. Mirrors
``task/test_task_real_cli.py``'s
``test_real_cli_subprocess_plan_mode`` pattern.

Exercises:
  * CLI argument parsing via ``cli.py``'s argparse
  * Underscore-canonical normalization (Option D fix)
  * YAML loading via ``load_config + instantiate``
  * RovoChat with TemplatedInferencerBase MI (template rendering)
  * RovoDevCli aggregator
  * LazyConfigFactory worker spawning
  * Workspace allocator (``_runtime/tasks/create_role/<TS>_<UUID>/``)
  * Real subprocess stdout/stderr capture
  * Exit code propagation
  * Canonical deliverable surfacing via ``outputs/final_deliverables/``

Cost gate: SKIPPED unless ``acli`` available on PATH AND RovoChat credentials
are set (``ROVOCHAT_EMAIL`` / ``ROVOCHAT_API_TOKEN``, or mappable from
``JIRA_EMAIL`` / ``JIRA_API_TOKEN``).

Runtime: ~10-20 min, ~$0.50-2.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from .preflight._common import (
    COREPROJECTS_ROOT,
    OPENSTARTUP_ROOT,
    skip_no_acli,
    skip_no_rovochat_creds,
)


@skip_no_acli
@skip_no_rovochat_creds
@pytest.mark.integration
def test_create_role_real_cli_subprocess(tmp_path):
    """Spawn real subprocess + validate role document is written."""
    # Build PYTHONPATH the way the production launcher does
    pythonpath_parts = [
        str(OPENSTARTUP_ROOT / "src"),
        str(COREPROJECTS_ROOT / "AgentFoundation" / "src"),
        str(COREPROJECTS_ROOT / "PythonUtils" / "src"),
        # OpenTeam (in rovoteam dir, sibling to CoreProjects)
        str(COREPROJECTS_ROOT.parent / "rovoteam" / "OpenTeam" / "src"),
    ]
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    pythonpath = ":".join(pythonpath_parts)

    # Map JIRA_* → ROVOCHAT_* (the way the production launcher does)
    rovochat_email = (
        os.environ.get("ROVOCHAT_EMAIL")
        or os.environ.get("JIRA_EMAIL", "")
    )
    rovochat_token = (
        os.environ.get("ROVOCHAT_API_TOKEN")
        or os.environ.get("JIRA_API_TOKEN", "")
    )

    env = {
        **os.environ,
        "PYTHONPATH": pythonpath,
        "ROVOCHAT_EMAIL": rovochat_email,
        "ROVOCHAT_API_TOKEN": rovochat_token,
    }

    # No --output-path: canonical deliverable surfaces inside the workspace's
    # outputs/final_deliverables/ folder (per 2026-05-18 surfacing fix).
    cmd = [
        sys.executable, "-m", "openteam.server.resources.tools.create_role",
        "--max-facets", "2",  # minimal facets to keep cost low
        "hire a machine learning engineer (MLE)",  # role_description
    ]

    print(f"\n[real-cli-subprocess] cwd: {OPENSTARTUP_ROOT}")
    print(f"[real-cli-subprocess] PYTHONPATH parts: {len(pythonpath_parts)}")
    print(
        f"[real-cli-subprocess] cmd: {' '.join(cmd[:5])} ... (request elided)"
    )

    log_path = tmp_path / "cli_subprocess.log"
    print(f"[real-cli-subprocess] log: {log_path}")

    result = subprocess.run(
        cmd,
        cwd=str(OPENSTARTUP_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60 * 25,  # 25 minutes max
    )

    # Persist logs for debugging on failure
    log_path.write_text(
        f"=== ARGV ===\n{cmd}\n\n"
        f"=== RETURNCODE ===\n{result.returncode}\n\n"
        f"=== STDOUT ===\n{result.stdout}\n\n"
        f"=== STDERR ===\n{result.stderr}\n"
    )

    # === ASSERTIONS ===

    # 1. Exit code should be 0 (success)
    assert result.returncode == 0, (
        f"create_role exited with code {result.returncode}. "
        f"Log: {log_path}\n"
        f"STDERR tail: {result.stderr[-2000:]}"
    )

    # 2. Workspace was created under _runtime/tasks/create_role/
    runtime_dir = OPENSTARTUP_ROOT / "_runtime" / "tasks" / "create_role"
    assert runtime_dir.is_dir(), (
        f"Runtime workspace root missing: {runtime_dir}"
    )
    workspaces = sorted(
        [d for d in runtime_dir.iterdir() if d.is_dir()
         and d.name.startswith("create_role_")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    assert workspaces, (
        f"No create_role_* workspace was created under {runtime_dir}"
    )
    latest = workspaces[0]
    print(f"[real-cli-subprocess] workspace: {latest}")

    # 3. Canonical deliverable: outputs/final_deliverables/role_document.md
    #    (auto-promoted by BTA when use_final_deliverables_folder=true
    #     and aggregator has output_is_deliverable=true)
    deliverable = latest / "outputs" / "final_deliverables" / "role_document.md"
    assert deliverable.is_file(), (
        f"Canonical role document was NOT promoted to {deliverable}. "
        f"This is a regression in the deliverable surfacing chain (BTA's "
        f"`use_final_deliverables_folder` or aggregator's "
        f"`output_is_deliverable`). Log: {log_path}"
    )

    # 4. Role document must have substantive content (real synthesis,
    #    not the ~2-3 KB summary blurb). The canonical aggregator output
    #    is typically 20-50 KB for max-facets=2.
    content = deliverable.read_text(encoding="utf-8")
    assert len(content) > 5000, (
        f"Role document too short ({len(content)} chars). Expected the "
        f"full aggregator synthesis (>5 KB, typically 20-50 KB), not "
        f"BTA's summary blurb. Got first 500 chars: {content[:500]}"
    )

    # 5. Role document should mention the role (MLE/Machine Learning)
    content_lower = content.lower()
    assert (
        "machine learning" in content_lower
        or "mle" in content_lower
        or "ml engineer" in content_lower
    ), (
        f"Role document doesn't reference the requested role (MLE). "
        f"Got first 500 chars: {content[:500]}"
    )

    # 6. BTA's summary blurb is a SEPARATE file (run_summary.md), not
    #    overwriting the canonical deliverable. This avoids the prior
    #    confusion of "two files both named role_document.md".
    summary_path = latest / "outputs" / "run_summary.md"
    if summary_path.is_file():
        summary = summary_path.read_text(encoding="utf-8")
        print(
            f"[real-cli-subprocess] run_summary.md: {len(summary)} chars "
            f"(expected ~2-5 KB blurb, distinct from canonical doc)"
        )

    print(
        f"[real-cli-subprocess] ✅ SUCCESS — canonical role doc: "
        f"{len(content)} chars at {deliverable}"
    )
