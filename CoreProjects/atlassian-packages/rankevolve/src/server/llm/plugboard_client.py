# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

import contextlib
import platform
import uuid
from collections.abc import AsyncIterator
from typing import AsyncGenerator

from corp_crypto_auth_token_util import CryptoAuthTokenUtil
from facebook.ai_productivity.plugboard.plugboard.thrift_clients import (
    AiProductivity_Plugboard,
)
from facebook.ai_productivity.plugboard.plugboard.thrift_types import (
    ContentPart,
    Message,
    ModelParams,
    RunPipelineRequest,
)
from facebook.ai_productivity.stream_defs.thrift_types import (
    STREAM_ASSISTANT,
)
from py3_asyncio.infrasec.authorization.acl.thrift_types import Identity
from rankevolve.src.server.llm.base import BaseLLMClient

import py3_asyncio.infrasec.authorization.acl.thrift_types as acl_constants


_PLUGBOARD_TIER = "metamate_platform.plugboard"
_PLUGBOARD_IDENTITY = Identity(
    id_type=acl_constants.SERVICE_IDENTITY,
    id_data=_PLUGBOARD_TIER,
)
_CAT_TIMEOUT = 3600  # 1 hour


def _get_plugboard_cats() -> str:
    """Get CAT tokens for authenticating to Plugboard."""
    return CryptoAuthTokenUtil.serialize_crypto_auth_token_list(
        CryptoAuthTokenUtil.get_all_crypto_auth_tokens(
            _PLUGBOARD_IDENTITY,
            token_timeout_seconds=_CAT_TIMEOUT,
        )
    )


def _has_service_router() -> bool:
    """Check if ServiceRouter is available (prod Linux only)."""
    return platform.system() == "Linux" and _is_prod_network()


def _is_prod_network() -> bool:
    """Detect if running on prod network."""
    import os

    path = "/etc/fbwhoami"
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            for line in f:
                parts = line.strip().split("=", 1)
                if len(parts) == 2:
                    var, value = parts
                    if var == "DEVICE_HOSTNAME_SCHEME" and value.startswith("corp_"):
                        return False
                    if var == "CLOUD_PROVIDER" and len(value) > 0:
                        return False
        return True  # default to prod if file exists without corp indicators
    except Exception:
        return False


@contextlib.asynccontextmanager
async def _get_plugboard_client() -> AsyncGenerator[
    AiProductivity_Plugboard.Async, None
]:
    """Create a Thrift client to Plugboard with CAT auth."""
    cats = _get_plugboard_cats()
    headers = {CryptoAuthTokenUtil.CRYPTO_AUTH_TOKEN_HEADER: cats}

    if _has_service_router():
        from servicerouter.python.async_client import get_sr_client
        from servicerouter.python.client_params import ClientParams

        params = ClientParams()
        params.setClientId("rankevolve.chat_cli")
        async with get_sr_client(
            AiProductivity_Plugboard, _PLUGBOARD_TIER, params=params, headers=headers
        ) as client:
            yield client
    else:
        from x2p.secure_thrift.python.client import get_client

        async with get_client(
            AiProductivity_Plugboard, _PLUGBOARD_TIER, headers=headers
        ) as client:
            yield client


class PlugboardClient(BaseLLMClient):
    """Streaming LLM client via Meta's internal Plugboard gateway."""

    def __init__(
        self,
        pipeline: str = "usecase-dev-ai",
        model_pipeline_overrides: dict[str, str] | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.model_pipeline_overrides = model_pipeline_overrides or {}

    def _get_pipeline_for_model(self, model: str) -> str:
        """Resolve the pipeline for a given model, checking overrides first."""
        return self.model_pipeline_overrides.get(model, self.pipeline)

    async def stream_response(
        self,
        messages: list[dict[str, str]],
        system: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        # Build Plugboard Message list
        pb_messages: list[Message] = []

        # System prompt as system-role message
        pb_messages.append(
            Message(
                role="system",
                content_parts=[ContentPart(text=system)],
            )
        )

        # Conversation messages
        for msg in messages:
            pb_messages.append(
                Message(
                    role=msg["role"],
                    content_parts=[ContentPart(text=msg["content"])],
                )
            )

        model_params = ModelParams(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        request = RunPipelineRequest(
            history=pb_messages,
            pipeline=self._get_pipeline_for_model(model),
            model_params=model_params,
            request_correlator=f"rankevolve-chat-cli~{uuid.uuid4()}",
        )

        async with _get_plugboard_client() as ctx:
            (_init, stream) = await ctx.run_pipeline_streaming(request)
            async for chunk in stream:
                if chunk.stream_id == STREAM_ASSISTANT and chunk.message.content:
                    yield chunk.message.content

    async def close(self) -> None:
        pass
