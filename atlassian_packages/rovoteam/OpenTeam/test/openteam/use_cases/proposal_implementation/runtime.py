"""Per-run inferencer logging workspace for debuggability.

For each orchestrator run, we create a timestamped directory under
`prompts/_runtime/run_<ts>_<shortuuid>/` and, for every inferencer invocation,
a sub-directory like `epic_monitor_AI-236_round_01/` containing:
  - prompt.md              the exact prompt text sent to the inferencer
  - stream.log             every streaming chunk, line-buffered (real-time tail-able)
  - clean_output.md        the final clean output captured by RovoDevCLI's --output-file
  - parsed_sentinels.json  what the orchestrator parsed from the output
  - _meta.json             timings, exit metadata, prompt vars

Folder convention (human-friendly):
  run_<YYYY-MM-DDTHH-MM-SS>_<shortuuid>/
    _run.json
    epic_monitor_<EPIC>_round_<NN>/
    pr_creation_<ISSUE>/                   (one-shot per issue per run)
    pr_monitor_<ISSUE>_round_<NN>/
    rescue_<ISSUE>/                        (one-shot per issue per run)

Privacy note: prompts may contain local filesystem paths. Logs are gitignored;
sanitize before sharing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import socket
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_dir_segment(name: str) -> str:
    """Make a string safe for use as a directory segment."""
    cleaned = _SAFE_NAME_RE.sub("-", name).strip("-_.")
    return cleaned or "x"


@dataclass
class CallContext:
    """One inferencer invocation's logging context."""

    call_dir: Path
    task_type: str
    primary_key: str
    round_num: Optional[int]
    started_at: float = field(default_factory=time.monotonic)
    started_at_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def prompt_path(self) -> Path:
        return self.call_dir / "prompt.md"

    @property
    def stream_log_path(self) -> Path:
        return self.call_dir / "stream.log"

    @property
    def clean_output_path(self) -> Path:
        return self.call_dir / "clean_output.md"

    @property
    def sentinels_path(self) -> Path:
        return self.call_dir / "parsed_sentinels.json"

    @property
    def meta_path(self) -> Path:
        return self.call_dir / "_meta.json"


@dataclass
class RunWorkspace:
    """A timestamped per-run workspace under prompts/_runtime/.

    Thread-safe round numbering via asyncio.Lock — same workspace can be
    shared across N parallel workers.
    """

    base_dir: Path  # e.g. /Users/.../_runtime
    run_id: str
    run_dir: Path
    _round_counts: Dict[Tuple[str, str], int] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Defense G-3 — hard cap on call-dirs created per run. The 2026-05-20
    # incident saw 896,692 dirs created in 28 minutes due to a crash loop;
    # any number above this threshold is treated as a runaway and triggers
    # a hard refusal + log error. Configurable via constructor; sensible
    # default is 1,000 (10 issues × 100 polls each = generous).
    max_call_dirs: int = 1000
    _call_dirs_created: int = 0
    _runaway_warned: bool = False

    @classmethod
    def create(
        cls,
        base_dir: Path,
        *,
        cli_args: Optional[list] = None,
        max_call_dirs: int = 1000,
    ) -> "RunWorkspace":
        """Create a new timestamped run workspace.

        Args:
            base_dir: directory under which `run_<ts>_<uuid>/` is created.
            cli_args: optional CLI args to record in `_run.json` for postmortem.
            max_call_dirs: G-3 hard cap on number of per-call dirs created.
                Above this, `begin_call()` returns a sentinel that disables
                logging (orchestrator continues; no fs growth).
        """
        base_dir = Path(base_dir)
        base_dir.mkdir(parents=True, exist_ok=True)

        # Add a .gitignore at the base to be safe (idempotent)
        gitignore = base_dir / ".gitignore"
        if not gitignore.exists():
            try:
                gitignore.write_text("# Per-run inferencer logs; never commit.\n*\n!.gitignore\n!README.md\n")
            except Exception as e:
                logger.warning("Could not write .gitignore at %s: %s", gitignore, e)

        readme = base_dir / "README.md"
        if not readme.exists():
            try:
                readme.write_text(_RUNTIME_README)
            except Exception as e:
                logger.warning("Could not write README at %s: %s", readme, e)

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        short = uuid.uuid4().hex[:8]
        run_id = f"run_{ts}_{short}"
        run_dir = base_dir / run_id
        run_dir.mkdir(exist_ok=True)

        ws = cls(base_dir=base_dir, run_id=run_id, run_dir=run_dir,
                 max_call_dirs=max_call_dirs)
        ws._write_run_metadata(cli_args=cli_args)
        logger.info("Runtime workspace created: %s (max_call_dirs=%d)",
                    run_dir, max_call_dirs)
        return ws

    def _write_run_metadata(self, *, cli_args: Optional[list] = None) -> None:
        meta = {
            "run_id": self.run_id,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
            "cli_args": cli_args or list(sys.argv),
            "python": sys.version,
        }
        try:
            (self.run_dir / "_run.json").write_text(json.dumps(meta, indent=2))
        except Exception as e:
            logger.warning("Could not write _run.json: %s", e)

    async def begin_call(
        self,
        *,
        task_type: str,
        primary_key: str,
        is_round_based: bool = False,
    ) -> CallContext:
        """Allocate a new call directory and return its context.

        Round-based tasks (Epic/PR monitor) get an incrementing round suffix.
        One-shot tasks (CreatePR, Rescue) get no round suffix.

        Defense G-3: if `max_call_dirs` is exceeded, return a no-op
        CallContext whose `call_dir` points to /dev/null-equivalent
        (a single shared `_runaway_quarantine/` dir, never used for real
        I/O). The orchestrator continues — only filesystem growth stops.
        """
        # Defense G-3 — hard cap. Check under lock for thread-safety.
        async with self._lock:
            if self._call_dirs_created >= self.max_call_dirs:
                if not self._runaway_warned:
                    logger.error(
                        "🛑 RUNAWAY DETECTED: %d call dirs created in this run "
                        "(limit %d). Disabling per-call logging to protect disk. "
                        "Investigate the orchestrator immediately.",
                        self._call_dirs_created, self.max_call_dirs,
                    )
                    self._runaway_warned = True
                # Return a no-op context — orchestrator can still parse output,
                # just no per-call logs. call_dir is the run's quarantine dir
                # which is overwritten on each call (single dir, not per-call).
                quarantine = self.run_dir / "_runaway_quarantine"
                quarantine.mkdir(exist_ok=True)
                return CallContext(
                    call_dir=quarantine,
                    task_type=task_type,
                    primary_key=primary_key,
                    round_num=None,
                )
            self._call_dirs_created += 1

        round_num: Optional[int] = None
        if is_round_based:
            async with self._lock:
                key = (task_type, primary_key)
                self._round_counts[key] = self._round_counts.get(key, 0) + 1
                round_num = self._round_counts[key]

        # Build human-friendly directory name
        type_segment = {
            "MonitorEpic": "epic_monitor",
            "CreatePR": "pr_creation",
            "MonitorPR": "pr_monitor",
            "RescueIssue": "rescue",
        }.get(task_type, _safe_dir_segment(task_type).lower())

        # For MonitorPR, primary_key is "<issue>#<pr_url>" — keep only the issue
        # for the dir name (PR URL is too long & noisy); save the full key in meta.
        key_for_dir = primary_key.split("#", 1)[0]
        key_segment = _safe_dir_segment(key_for_dir)

        name = f"{type_segment}_{key_segment}"
        if round_num is not None:
            name = f"{name}_round_{round_num:02d}"

        call_dir = self.run_dir / name
        # Collision guard — extremely unlikely but cheap to handle
        if call_dir.exists():
            call_dir = self.run_dir / f"{name}_{uuid.uuid4().hex[:4]}"
        call_dir.mkdir(parents=True, exist_ok=True)

        ctx = CallContext(
            call_dir=call_dir,
            task_type=task_type,
            primary_key=primary_key,
            round_num=round_num,
        )
        logger.info("[%s] call dir: %s", task_type, call_dir)
        return ctx

    @staticmethod
    def write_prompt(ctx: CallContext, prompt_text: str) -> None:
        try:
            ctx.prompt_path.write_text(prompt_text)
        except Exception as e:
            logger.warning("Could not write prompt.md: %s", e)

    @staticmethod
    def append_stream_chunk(ctx: CallContext, chunk: str) -> None:
        """Append a streaming chunk; tail-able in real time."""
        try:
            with ctx.stream_log_path.open("a") as f:
                f.write(chunk)
                if not chunk.endswith("\n"):
                    f.write("\n")
        except Exception as e:
            logger.warning("Could not append stream chunk: %s", e)

    @staticmethod
    def write_clean_output(ctx: CallContext, clean_output: str) -> None:
        try:
            ctx.clean_output_path.write_text(clean_output)
        except Exception as e:
            logger.warning("Could not write clean_output.md: %s", e)

    @staticmethod
    def write_sentinels(ctx: CallContext, sentinels: dict) -> None:
        try:
            ctx.sentinels_path.write_text(json.dumps(sentinels, indent=2))
        except Exception as e:
            logger.warning("Could not write parsed_sentinels.json: %s", e)

    @staticmethod
    def finalize_call(
        ctx: CallContext,
        *,
        success: bool,
        prompt_vars: Optional[dict] = None,
        extra_meta: Optional[dict] = None,
    ) -> None:
        elapsed = time.monotonic() - ctx.started_at
        meta = {
            "task_type": ctx.task_type,
            "primary_key": ctx.primary_key,
            "round": ctx.round_num,
            "started_at_utc": ctx.started_at_iso,
            "ended_at_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 2),
            "success": success,
            "prompt_vars_keys": sorted((prompt_vars or {}).keys()),
        }
        if extra_meta:
            meta.update(extra_meta)
        try:
            ctx.meta_path.write_text(json.dumps(meta, indent=2))
        except Exception as e:
            logger.warning("Could not write _meta.json: %s", e)


_RUNTIME_README = """# `_runtime/` — Per-Run Inferencer Debug Logs

This directory is auto-populated by the orchestrator. Each subdirectory
`run_<timestamp>_<id>/` corresponds to one orchestrator invocation.

## Layout

```
run_<YYYY-MM-DDTHH-MM-SS>_<shortuuid>/
├── _run.json                              # CLI args, hostname, start time
├── epic_monitor_<EPIC>_round_<NN>/        # one dir per MonitorEpic call
│   ├── prompt.md                          # the rendered prompt sent in
│   ├── stream.log                         # streaming chunks (real-time tail-able)
│   ├── clean_output.md                    # final clean output from rovodev
│   ├── parsed_sentinels.json              # what the orchestrator parsed
│   └── _meta.json                         # timing + success flag
├── pr_creation_<ISSUE>/                   # one-shot per issue
│   └── ...same 5 files...
├── pr_monitor_<ISSUE>_round_<NN>/         # one dir per MonitorPR call
│   └── ...same 5 files...
└── rescue_<ISSUE>/                        # one-shot per issue
    └── ...same 5 files...
```

## Privacy

Prompts embed local filesystem paths (intentional, for the LLM's reading
context). This directory is `.gitignore`d. Sanitize before sharing publicly.

## Common debug recipes

- **What is the inferencer doing right now?**
  `tail -f run_*/<latest-call-dir>/stream.log`
- **What did the orchestrator parse from the last call?**
  `cat run_*/<call-dir>/parsed_sentinels.json`
- **How long did each call take?**
  `grep -h elapsed_seconds run_*/*/_meta.json | sort -t: -k2 -n`
- **Compare two consecutive PR-monitor rounds:**
  `diff -u run_*/pr_monitor_AI-243_round_01/clean_output.md run_*/pr_monitor_AI-243_round_02/clean_output.md`

## Cleanup

These logs accumulate. Periodically:
```bash
find _runtime -name "run_*" -mtime +30 -exec rm -rf {} +
```
"""
