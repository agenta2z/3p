"""Mock task executor — drives a real BTA with mock inferencers.

Exercises the full graph event pipeline (topology, status, streaming)
without LLM calls. Used by the ``/mock_task`` developer slash command.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)
_PROFILES_DIR = Path(__file__).parent / "profiles"


def _apply_speed(cfg: dict, speed: float) -> dict:
    """Recursively multiply all ``delay_s`` / ``duration_s`` values by speed."""
    if isinstance(cfg, dict):
        out = {}
        for k, v in cfg.items():
            if k in ("delay_s", "duration_s") and isinstance(v, (int, float)):
                out[k] = v * speed
            else:
                out[k] = _apply_speed(v, speed)
        return out
    if isinstance(cfg, list):
        return [_apply_speed(item, speed) for item in cfg]
    return cfg


async def execute(arguments: dict, session_context: dict) -> Any:
    """Entry point called by ToolDispatcher for /mock_task."""
    profile = arguments.get("profile", "default")
    speed = float(arguments.get("speed", 1.0))
    seed = int(arguments.get("seed", 0))

    cfg_path = _PROFILES_DIR / f"{profile}.yaml"
    if not cfg_path.exists():
        available = [p.stem for p in _PROFILES_DIR.glob("*.yaml")]
        return {"success": False, "output": f"Unknown profile '{profile}'. Available: {available}"}

    _logger.info("[mock_task] profile=%s speed=%s seed=%s", profile, speed, seed)

    import agent_foundation.common.configs.registered_targets  # noqa: register aliases
    from python_utils.config_utils import load_config, instantiate

    cfg = load_config(str(cfg_path))
    if speed != 1.0:
        cfg = _apply_speed(cfg, speed)
    if seed:
        random.seed(seed)

    bta = instantiate(cfg)

    try:
        from agent_foundation.ui.graph_reporter_factory import make_graph_reporter
        task_id = session_context.get("task_id", "")
        bta.graph_reporter = make_graph_reporter(session_context, task_id)
        if bta.graph_reporter is not None:
            _logger.info("[mock_task] graph_reporter attached: %s",
                         type(bta.graph_reporter).__name__)
    except Exception as exc:
        _logger.warning("[mock_task] graph_reporter attach failed: %s", exc)

    result = await bta.ainfer("__mock_input__")
    result_text = str(result) if result else "[mock_task completed]"
    return {"success": True, "output": result_text[:2000]}
