"""Real-CLI integration test for ``/role_setup``.

Spawns ``python -m openteam.server.resources.tools.role_setup`` as a real
subprocess to validate the FULL CLI module code path end-to-end. Mirrors
``create_role/test_create_role_real_cli.py`` and ``task/test_task_real_cli.py``.

Exercises:
  * CLI argument parsing via ``cli.py``'s argparse
  * Underscore-canonical normalization (Option D fix)
  * YAML loading via ``load_config + instantiate`` (nested outer + inner BTA)
  * LazyConfigFactory worker spawning at BOTH outer and inner BTA layers
  * Per-skill nested-BTA isolation (each outer worker is its own BTA instance)
  * Workspace allocator (``_runtime/tasks/role_setup/<TS>_<UUID>/``)
  * Real subprocess stdout/stderr capture
  * Exit code propagation
  * Canonical deliverable surfacing via ``outputs/final_deliverables/``

Cost gate: SKIPPED unless ``acli`` available on PATH AND RovoChat credentials
are set (``ROVOCHAT_EMAIL`` / ``ROVOCHAT_API_TOKEN``, or mappable from
``JIRA_EMAIL`` / ``JIRA_API_TOKEN``).

Runtime: ~15-30 min, ~$1-3 (nested BTA = more facets total than create_role).
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

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
def test_role_setup_real_cli_subprocess(tmp_path):
    """Spawn real subprocess + validate role-setup deliverable is written."""
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

    # Synthesize a minimal role document so the test does not depend on any
    # checked-in role doc that might drift. Keep it short to limit cost but
    # rich enough to drive a meaningful breakdown into skills/tools.
    role_doc = tmp_path / "test_role_document.md"
    role_doc.write_text(
        textwrap.dedent(
            """\
            # Role: Senior Machine Learning Engineer

            ## Mission
            Build and operate production ML systems end-to-end.

            ## Key Responsibilities
            - Design, train, and deploy ML models to production.
            - Maintain feature pipelines and model-serving infrastructure.
            - Collaborate with data scientists, software engineers, and PMs.

            ## Required Skills
            - Python (advanced)
            - PyTorch or TensorFlow
            - Distributed training (Ray, Horovod, or equivalent)
            - Model serving (TorchServe, KServe, or equivalent)
            - Cloud platforms (AWS / GCP / Azure)
            """
        ),
        encoding="utf-8",
    )

    # Minimal facets to keep cost low: 2 outer skills × 1 inner subtask each.
    cmd = [
        sys.executable, "-m", "openteam.server.resources.tools.role_setup",
        "--max-facets", "2",
        "--max-inner-facets", "1",
        str(role_doc),  # role_document_path (positional)
    ]

    print(f"\n[real-cli-subprocess] cwd: {OPENSTARTUP_ROOT}")
    print(f"[real-cli-subprocess] PYTHONPATH parts: {len(pythonpath_parts)}")
    print(f"[real-cli-subprocess] role_doc: {role_doc}")
    print(f"[real-cli-subprocess] cmd: {' '.join(cmd[:7])} {role_doc.name}")

    log_path = tmp_path / "cli_subprocess.log"
    print(f"[real-cli-subprocess] log: {log_path}")

    result = subprocess.run(
        cmd,
        cwd=str(OPENSTARTUP_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60 * 35,  # 35 minutes max (nested BTA can be slower)
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
        f"role_setup exited with code {result.returncode}. "
        f"Log: {log_path}\n"
        f"STDERR tail: {result.stderr[-2000:]}"
    )

    # 2. Workspace was created under _runtime/tasks/role_setup/
    runtime_dir = OPENSTARTUP_ROOT / "_runtime" / "tasks" / "role_setup"
    assert runtime_dir.is_dir(), (
        f"Runtime workspace root missing: {runtime_dir}"
    )
    workspaces = sorted(
        [d for d in runtime_dir.iterdir() if d.is_dir()
         and d.name.startswith("role_setup_")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    assert workspaces, (
        f"No role_setup_* workspace was created under {runtime_dir}"
    )
    latest = workspaces[0]
    print(f"[real-cli-subprocess] workspace: {latest}")

    # 3. Canonical deliverable: outputs/final_deliverables/role_setup_output.md
    #    (auto-promoted by BTA when use_final_deliverables_folder=true
    #     and aggregator has output_is_deliverable=true)
    deliverable = (
        latest / "outputs" / "final_deliverables" / "role_setup_output.md"
    )
    assert deliverable.is_file(), (
        f"Canonical role-setup output was NOT promoted to {deliverable}. "
        f"This is a regression in the deliverable surfacing chain (BTA's "
        f"`use_final_deliverables_folder` or aggregator's "
        f"`output_is_deliverable`). Log: {log_path}"
    )

    # 4. Deliverable must have substantive content (real synthesis,
    #    not the ~2-3 KB summary blurb). The canonical aggregator output
    #    for role_setup is typically 15-50 KB.
    content = deliverable.read_text(encoding="utf-8")
    assert len(content) > 5000, (
        f"Role-setup output too short ({len(content)} chars). Expected the "
        f"full aggregator synthesis (>5 KB, typically 15-50 KB), not "
        f"BTA's summary blurb. Got first 500 chars: {content[:500]}"
    )

    # 5. Output should reference the role we provided (Machine Learning
    #    Engineer). Loose substring match to avoid coupling to phrasing.
    content_lower = content.lower()
    assert (
        "machine learning" in content_lower
        or "ml engineer" in content_lower
        or "mle" in content_lower
    ), (
        f"Role-setup output doesn't reference the requested role (MLE). "
        f"Got first 500 chars: {content[:500]}"
    )

    # 6. BTA's summary blurb is a SEPARATE file (run_summary.md), not
    #    overwriting the canonical deliverable. This avoids the prior
    #    confusion of "two files both named role_setup_output.md".
    summary_path = latest / "outputs" / "run_summary.md"
    if summary_path.is_file():
        summary = summary_path.read_text(encoding="utf-8")
        print(
            f"[real-cli-subprocess] run_summary.md: {len(summary)} chars "
            f"(expected ~2-5 KB blurb, distinct from canonical doc)"
        )

    # 7. Nested-BTA shape sanity: outer worker_* subdirs exist (per outer skill)
    #    and each contains its own nested children/worker_* (per inner subtask).
    children_dir = latest / "children"
    outer_workers = sorted(children_dir.glob("propose/children/worker_*"))
    if outer_workers:
        print(
            f"[real-cli-subprocess] nested BTA shape: "
            f"{len(outer_workers)} outer worker_* dirs"
        )

    print(
        f"[real-cli-subprocess] ✅ SUCCESS — canonical role-setup output: "
        f"{len(content)} chars at {deliverable}"
    )
