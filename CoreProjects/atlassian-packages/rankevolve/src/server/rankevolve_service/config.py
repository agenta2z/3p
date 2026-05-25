# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

"""RankEvolve-specific service configuration."""

from __future__ import annotations

from dataclasses import dataclass

from rankevolve.src.utils.service_utils.server.base_config import BaseServiceConfig


@dataclass
class RankEvolveServiceConfig(BaseServiceConfig):
    """Extends BaseServiceConfig with RankEvolve-specific fields."""

    provider: str = "plugboard"
    model: str = "claude-3.5-sonnet"
    pipeline: str = ""
    max_tokens: int = 8192
    temperature: float = 0.7
    system_prompt_file: str = "system.md"
    session_root_path: str = ""
    enable_knowledge: bool = False
    enable_conversational_inferencer: bool = False
