# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

import json
from pathlib import Path

import yaml


def get_shared_dir() -> Path:
    """Locate the cli_shared/ directory.

    Primary: relative path from __file__ (works in Buck2 link-tree).
    Fallback: importlib.resources for stricter environments.
    """
    # Primary: relative path (works in Buck2 link-tree where cli_shared is mounted)
    candidate = Path(__file__).parent.parent / "cli" / "cli_shared"
    if candidate.is_dir():
        return candidate
    # Fallback: importlib.resources
    try:
        import importlib.resources as pkg_resources

        ref = pkg_resources.files("rankevolve.src.cli.cli_shared")
        # ref may be a MultiplexedPath — check if it has a real filesystem path
        ref_path = Path(str(ref))
        if ref_path.is_dir():
            return ref_path
        # For MultiplexedPath, try _paths attribute
        if hasattr(ref, "_paths"):
            for p in ref._paths:
                p = Path(str(p))
                if p.is_dir():
                    return p
    except (ImportError, ModuleNotFoundError, TypeError):
        pass
    return candidate


def load_system_prompt(filename: str) -> str:
    path = get_shared_dir() / "prompts" / filename
    return path.read_text()


def load_welcome_message() -> str:
    path = get_shared_dir() / "prompts" / "welcome.md"
    return path.read_text()


def load_theme(theme_name: str) -> dict[str, object]:
    path = get_shared_dir() / "themes" / f"{theme_name}.json"
    return json.loads(path.read_text())  # pyre-ignore[7]


def load_default_config() -> dict[str, object]:
    path = get_shared_dir() / "config" / "default-config.yaml"
    return yaml.safe_load(path.read_text())  # pyre-ignore[7]
