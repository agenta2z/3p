"""TIER-2 smoke tests: each wrapper calls its executor and returns rendered output."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from openteam.mcp_server.server import (
    openteam_create_role,
    openteam_project_onboarding,
    openteam_role_setup,
    openteam_task,
)

_FAKE_RESULT = SimpleNamespace(result="ok", context_updates={})

# Minimal valid kwargs for each wrapper.
_MINIMAL_KWARGS: dict[str, dict] = {
    "openteam_task": {"request": "hello"},
    "openteam_create_role": {"role_description": "test role"},
    "openteam_role_setup": {"role_document_path": "/tmp/role.md"},
    "openteam_project_onboarding": {"project_document_path": "/tmp/project.md"},
}

# Import path of the executor.execute that each wrapper lazy-imports.
_EXECUTOR_MODULES: dict[str, str] = {
    "openteam_task": "openteam.server.resources.tools.task.executor",
    "openteam_create_role": "openteam.server.resources.tools.create_role.executor",
    "openteam_role_setup": "openteam.server.resources.tools.role_setup.executor",
    "openteam_project_onboarding": "openteam.server.resources.tools.project_onboarding.executor",
}

_WRAPPER_FUNCS = {
    "openteam_task": openteam_task,
    "openteam_create_role": openteam_create_role,
    "openteam_role_setup": openteam_role_setup,
    "openteam_project_onboarding": openteam_project_onboarding,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper_name", list(_WRAPPER_FUNCS.keys()))
async def test_wrapper_smoke(monkeypatch, wrapper_name: str):
    """Monkeypatch the executor and verify the wrapper returns rendered 'ok'."""
    mock_execute = AsyncMock(return_value=_FAKE_RESULT)
    executor_module = _EXECUTOR_MODULES[wrapper_name]

    # The wrappers use lazy imports inside the function body:
    #   from openteam.server.resources.tools.<tool>.executor import execute as _exec
    # We patch the module's execute attribute so the lazy import picks it up.
    # To handle the lazy import, we pre-import the module and patch it.
    import importlib

    try:
        mod = importlib.import_module(executor_module)
    except ImportError:
        # If the executor module can't be imported (missing dependencies), we
        # create a fake module with the execute function in sys.modules.
        import sys
        import types

        mod = types.ModuleType(executor_module)
        mod.execute = mock_execute  # type: ignore[attr-defined]
        sys.modules[executor_module] = mod
    else:
        monkeypatch.setattr(mod, "execute", mock_execute)

    wrapper_fn = _WRAPPER_FUNCS[wrapper_name]
    kwargs = _MINIMAL_KWARGS[wrapper_name]
    result = await wrapper_fn(**kwargs)

    assert result == "ok"
    mock_execute.assert_awaited_once()
