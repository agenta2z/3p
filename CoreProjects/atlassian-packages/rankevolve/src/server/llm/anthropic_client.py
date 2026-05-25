# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

from collections.abc import AsyncIterator

import anthropic

from rankevolve.src.server.llm.base import BaseLLMClient


class AnthropicClient(BaseLLMClient):
    """Streaming client for the Anthropic Messages API."""

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        kwargs: dict[str, str] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.AsyncAnthropic(**kwargs)

    async def stream_response(
        self,
        messages: list[dict[str, str]],
        system: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,  # pyre-ignore[6]
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def close(self) -> None:
        await self.client.close()
