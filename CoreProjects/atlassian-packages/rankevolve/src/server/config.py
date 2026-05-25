# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field

from rankevolve.src.server.shared_loader import load_default_config


@dataclass
class UIConfig:
    panel_width: int | None = None
    show_tokens: bool = False
    show_timing: bool = True
    streaming_refresh_hz: int = 15

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UIConfig":
        """Deserialize from a dictionary."""
        return cls(
            panel_width=data.get("panel_width"),
            show_tokens=data.get("show_tokens", False),
            show_timing=data.get("show_timing", True),
            streaming_refresh_hz=data.get("streaming_refresh_hz", 15),
        )


@dataclass
class AppConfig:
    provider: str = "plugboard"
    model: str = "claude-sonnet-4.5"
    api_key_env: str | None = None
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    system_prompt_file: str = "system-prompt.md"
    theme: str = "default"
    pipeline: str = "usecase-dev-ai"
    model_pipeline_overrides: dict[str, str] = field(default_factory=dict)
    ui: UIConfig = field(default_factory=UIConfig)

    def get_pipeline_for_model(self, model: str) -> str:
        """Return the pipeline for the given model, checking overrides first."""
        return self.model_pipeline_overrides.get(model, self.pipeline)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary.

        Note: The ``api_key`` property is NOT serialized — it reads from
        environment variables at runtime. Only ``api_key_env`` (the env var
        name) is persisted.
        """
        d = dataclasses.asdict(self)
        # asdict() recurses into UIConfig, which is already correct.
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """Deserialize from a dictionary."""
        ui_data = data.get("ui", {})
        ui = UIConfig.from_dict(ui_data) if isinstance(ui_data, dict) else UIConfig()
        return cls(
            provider=data.get("provider", "plugboard"),
            model=data.get("model", "claude-sonnet-4.5"),
            api_key_env=data.get("api_key_env"),
            base_url=data.get("base_url"),
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 0.7),
            system_prompt_file=data.get("system_prompt_file", "system-prompt.md"),
            theme=data.get("theme", "default"),
            pipeline=data.get("pipeline", "usecase-dev-ai"),
            model_pipeline_overrides=data.get("model_pipeline_overrides", {}),
            ui=ui,
        )

    @property
    def api_key(self) -> str:
        if self.provider == "plugboard":
            return ""  # Plugboard uses CAT auth, no API key needed
        env_var = self.api_key_env or (
            "OPENAI_API_KEY" if self.provider == "openai" else "ANTHROPIC_API_KEY"
        )
        key = os.environ.get(env_var)
        if not key:
            raise ValueError(
                f"API key not found. Set the {env_var} environment variable."
            )
        return key


def load_config(
    model_override: str | None = None,
    provider_override: str | None = None,
) -> AppConfig:
    """Load config from shared defaults, then apply CLI overrides."""
    raw = load_default_config()

    ui_raw = raw.get("ui", {})
    ui_config = UIConfig(
        panel_width=ui_raw.get("panel_width"),  # pyre-ignore[6]
        show_tokens=ui_raw.get("show_tokens", False),  # pyre-ignore[6]
        show_timing=ui_raw.get("show_timing", True),  # pyre-ignore[6]
        streaming_refresh_hz=ui_raw.get("streaming_refresh_hz", 15),  # pyre-ignore[6]
    )

    config = AppConfig(
        provider=raw.get("provider", "plugboard"),  # pyre-ignore[6]
        model=raw.get("model", "claude-sonnet-4.5"),  # pyre-ignore[6]
        api_key_env=raw.get("api_key_env"),  # pyre-ignore[6]
        base_url=raw.get("base_url"),  # pyre-ignore[6]
        max_tokens=raw.get("max_tokens", 4096),  # pyre-ignore[6]
        temperature=raw.get("temperature", 0.7),  # pyre-ignore[6]
        system_prompt_file=raw.get("system_prompt_file", "system-prompt.md"),  # pyre-ignore[6]
        theme=raw.get("theme", "default"),  # pyre-ignore[6]
        pipeline=raw.get("pipeline", "usecase-dev-ai"),  # pyre-ignore[6]
        model_pipeline_overrides=raw.get("model_pipeline_overrides", {}),  # pyre-ignore[6]
        ui=ui_config,
    )

    if model_override:
        config.model = model_override
    if provider_override:
        config.provider = provider_override

    return config
