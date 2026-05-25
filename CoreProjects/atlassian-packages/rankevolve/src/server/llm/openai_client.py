# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from rankevolve.src.server.llm.base import BaseLLMClient


class OpenAIClient(BaseLLMClient):
    """Streaming client for OpenAI-compatible APIs."""

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        kwargs: dict[str, str | None] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**kwargs)  # pyre-ignore[6]

    async def stream_response(
        self,
        messages: list[dict[str, str]],
        system: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        full_messages = [{"role": "system", "content": system}] + messages
        stream = await self.client.chat.completions.create(
            model=model,
            messages=full_messages,  # pyre-ignore[6]
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def close(self) -> None:
        await self.client.close()
