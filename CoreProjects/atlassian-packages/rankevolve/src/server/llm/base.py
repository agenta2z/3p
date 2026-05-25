# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseLLMClient(ABC):
    """Abstract interface for streaming LLM clients."""

    @abstractmethod
    async def stream_response(
        self,
        messages: list[dict[str, str]],
        system: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they arrive from the API."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up client resources."""
        ...
