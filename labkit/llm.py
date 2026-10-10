from __future__ import annotations

from typing import Any, Iterator, Protocol, Sequence, runtime_checkable
from labkit.replay import (
    LLMMessage,
    LLMResponse,
    LLMStreamChunk,
    ReplayClient,
    CassetteMismatchError,
)
from labkit.sim import SimClient


@runtime_checkable
class LLMClient(Protocol):
    """Hexagonal port defining the interface for all language model clients."""

    def complete(self, prompt: str | Sequence[LLMMessage], **kwargs: Any) -> LLMResponse:
        """Executes a single blocking completion."""
        ...

    def stream(self, prompt: str | Sequence[LLMMessage], **kwargs: Any) -> Iterator[LLMStreamChunk]:
        """Yields streaming deltas for the prompt."""
        ...


__all__ = [
    "LLMClient",
    "LLMMessage",
    "LLMResponse",
    "LLMStreamChunk",
    "ReplayClient",
    "SimClient",
    "CassetteMismatchError",
]
