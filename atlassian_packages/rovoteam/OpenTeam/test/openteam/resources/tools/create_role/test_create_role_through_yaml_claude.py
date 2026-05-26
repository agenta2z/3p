"""Run create_role_bta.yaml end-to-end with ClaudeCodeCli substituted for
RovoChat/RovoDevCLI via runtime overrides. Proves the YAML pipeline works on
machines without Rovo* CLIs.

Artifacts persist under `_runtime/<TIMESTAMP>/` (matching the existing
test_create_role_through_yaml.py convention) for inspection — NOT a temp
directory that auto-deletes.

Usage:
    cd OpenTeam
    python -m test.openteam.resources.tools.create_role.test_create_role_through_yaml_claude
"""

import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Bootstrap sys.path so `python -m ...` works without conftest.py
# (conftest only runs under pytest, but this is a click script)
_HERE = Path(__file__).resolve()
_OPENSTARTUP = _HERE.parent.parent.parent.parent.parent.parent  # OpenTeam/
_REPO_ROOT = _OPENSTARTUP.parent  # CoreProjects/
for _dep in [
    _OPENSTARTUP / "src",
    _REPO_ROOT / "AgentFoundation" / "src",
    _REPO_ROOT / "PythonUtils" / "src",
]:
    _path = str(_dep)
    if _path not in sys.path:
        sys.path.insert(0, _path)

# Trigger registered_targets registration
import agent_foundation.common.configs.registered_targets  # noqa: F401, E402
from python_utils.config_utils import load_config, instantiate  # noqa: E402

# File is at: OpenTeam/test/openteam/resources/tools/create_role/<this>.py
# OpenTeam root is 6 levels up
_OPENSTARTUP_ROOT = Path(__file__).resolve().parents[5]
YAML_PATH = _OPENSTARTUP_ROOT / "src/openteam/server/resources/tools/create_role/create_role_bta.yaml"
TEMPLATES_PATH = _OPENSTARTUP_ROOT / "src/openteam/server/resources/prompt_templates"
# Artifacts persist here for inspection (matches existing test convention)
RUNTIME_BASE = Path(__file__).resolve().parent / "_runtime"


def _claude_available() -> bool:
    try:
        r = subprocess.run("claude --version", shell=True,
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _opus_1m_smoke_check():
    """Pre-flight: verify `opus[1m]` alias actually responds before sinking
    cost into a full BTA run. Returns (ok, diagnostic_message).

    Sends a trivial 1-token prompt with --model "opus[1m]" --print. If the
    alias is unrecognized or the model is unavailable on this account, the
    CLI returns an error string we can detect.
    """
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
    bad_markers = (
        "Execution error",
        "model not found",
        "unknown model",
        "invalid model",
        "Unsupported model",
    )
    for m in bad_markers:
        if m.lower() in out.lower() or m.lower() in err.lower():
            return False, f"got error marker {m!r}: out={out[:200]} err={err[:200]}"
    if not out:
        return False, f"empty stdout, stderr={err[:200]}"
    return True, f"opus[1m] responded ({len(out)}B): {out[:120]}"


async def run(role_description: str, workspace: Path):
    # Claude Code CLI alias `opus[1m]` = Opus 4.7 + 1M context window
    OPUS_1M_MODEL = "opus[1m]"

    overrides = {
        # _target_ swaps
        "breakdown_inferencer._target_": "ClaudeCodeCLI",
        "worker_factory._target_": "ClaudeCodeCLI",
        "aggregator_inferencer._target_": "ClaudeCodeCLI",
        # ClaudeCodeCli config (per slot — Opus 4.7 with 1M context)
        "breakdown_inferencer.target_path": str(workspace),
        "breakdown_inferencer.model_name": OPUS_1M_MODEL,
        "breakdown_inferencer.idle_timeout_seconds": 300,
        "breakdown_inferencer.permission_mode": "bypassPermissions",
        "worker_factory.target_path": str(workspace),
        "worker_factory.model_name": OPUS_1M_MODEL,
        "worker_factory.idle_timeout_seconds": 300,
        "worker_factory.permission_mode": "bypassPermissions",
        "aggregator_inferencer.target_path": str(workspace),
        "aggregator_inferencer.model_name": OPUS_1M_MODEL,
        "aggregator_inferencer.idle_timeout_seconds": 300,
        "aggregator_inferencer.permission_mode": "bypassPermissions",
        # BTA-level
        "workspace_root": str(workspace),
        "_template_manager.templates": str(TEMPLATES_PATH),
        "max_breakdown": 2,
    }
    cfg = load_config(str(YAML_PATH), overrides=overrides)
    bta = instantiate(cfg)

    # Sanity: confirm all three slots are ClaudeCodeCli
    from agent_foundation.common.inferencers.agentic_inferencers.external.claude_code.claude_code_cli_inferencer import (
        ClaudeCodeCliInferencer,
    )
    assert isinstance(bta.breakdown_inferencer, ClaudeCodeCliInferencer), (
        f"breakdown_inferencer is {type(bta.breakdown_inferencer).__name__}"
    )
    assert isinstance(bta.aggregator_inferencer, ClaudeCodeCliInferencer), (
        f"aggregator_inferencer is {type(bta.aggregator_inferencer).__name__}"
    )
    # BTA detects functools.partial and calls factory() with no args
    # (see breakdown_then_aggregate_inferencer.py:1169-1175). For raw
    # callables it would pass sub_query=, index= as kwargs.
    import functools as _ft
    if isinstance(bta.worker_factory, _ft.partial):
        sample_worker = bta.worker_factory()
    else:
        sample_worker = bta.worker_factory(sub_query="probe", index=0)
    assert isinstance(sample_worker, ClaudeCodeCliInferencer), (
        f"worker_factory produced {type(sample_worker).__name__}"
    )
    print("[sanity] all 3 slots are ClaudeCodeCliInferencer OK", flush=True)

    return await bta.ainfer(role_description)


def main():
    if not _claude_available():
        print("ERROR: claude CLI not available", file=sys.stderr)
        sys.exit(2)

    print("[pre-flight] Checking opus[1m] availability ...", flush=True)
    ok, diag = _opus_1m_smoke_check()
    if not ok:
        print(f"ERROR: opus[1m] pre-flight failed: {diag}", file=sys.stderr)
        print("Hint: try `claude --print --model 'opus[1m]' 'hi'` manually "
              "to debug. If unavailable, fall back to model_name='opus' "
              "(no 1M context) or 'sonnet'.", file=sys.stderr)
        sys.exit(3)
    print(f"[pre-flight] OK — {diag}", flush=True)

    logging.basicConfig(level=logging.INFO)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = RUNTIME_BASE / timestamp
    workspace.mkdir(parents=True, exist_ok=True)
    print(f"[workspace] Artifacts -> {workspace}", flush=True)

    role_description = "Senior Backend Engineer focused on microservices."
    (workspace / "request.txt").write_text(role_description, encoding="utf-8")
    (workspace / "config.json").write_text(json.dumps({
        "model": "opus[1m]",
        "max_breakdown": 2,
        "timestamp": timestamp,
    }, indent=2), encoding="utf-8")

    try:
        result = asyncio.run(run(role_description, workspace))
        print("=== RESULT ===")
        print(str(result)[:2000])
        print("=== WORKSPACE FILES ===")
        for p in sorted(workspace.rglob("*")):
            if p.is_file():
                print(f"  {p.relative_to(workspace)}  ({p.stat().st_size}B)")
        print(f"\nArtifacts saved at: {workspace}")
        return 0
    except Exception:
        import traceback
        traceback.print_exc()
        print(f"\nPartial artifacts (if any) at: {workspace}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
