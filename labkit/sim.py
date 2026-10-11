from __future__ import annotations

import random
from typing import Any, Iterator, Sequence
from labkit.replay import LLMMessage, LLMResponse, LLMStreamChunk
from labkit.seed import derive_seed


class SimClient:
    """Stochastic simulated LLM client with strictly deterministic seeded randomness."""

    def __init__(
        self,
        seed: int | str,
        pass_rate: float = 1.0,
        success_content: str = "Task executed successfully.",
        failure_content: str = "Execution failed: simulated non-deterministic error.",
        model: str = "agentik-sim-v1",
    ) -> None:
        if not (0.0 <= pass_rate <= 1.0):
            raise ValueError(f"pass_rate must be between 0.0 and 1.0, got {pass_rate}")

        self.seed = seed
        self.pass_rate = pass_rate
        self.success_content = success_content
        self.failure_content = failure_content
        self.model = model

        # Internal deterministic pseudo-random generator
        self._rng = random.Random(self._resolve_seed(seed))
        self._call_count: int = 0

    @staticmethod
    def _resolve_seed(seed: int | str) -> int:
        if isinstance(seed, str):
            return derive_seed(seed, "sim-client")
        return int(seed)

    def reset(self) -> None:
        self._rng = random.Random(self._resolve_seed(self.seed))
        self._call_count = 0

    def complete(self, prompt: str | Sequence[LLMMessage], **kwargs: Any) -> LLMResponse:
        self._call_count += 1
        roll = self._rng.random()
        is_success = roll < self.pass_rate

        content = self.success_content if is_success else self.failure_content
        prompt_len = len(str(prompt).split())
        comp_len = len(content.split())

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_len,
            completion_tokens=comp_len,
            total_tokens=prompt_len + comp_len,
            model=self.model,
            finish_reason="stop" if is_success else "error",
            metadata={
                "roll": roll,
                "is_success": is_success,
                "call_count": self._call_count,
            },
        )

    def stream(self, prompt: str | Sequence[LLMMessage], **kwargs: Any) -> Iterator[LLMStreamChunk]:
        resp = self.complete(prompt, **kwargs)
        words = resp.content.split()
        if not words:
            yield LLMStreamChunk(delta="", is_final=True, finish_reason=resp.finish_reason)
            return

        for idx, word in enumerate(words):
            is_final = idx == len(words) - 1
            delta = word + (" " if not is_final else "")
            yield LLMStreamChunk(
                delta=delta,
                is_final=is_final,
                finish_reason=resp.finish_reason if is_final else None,
                metadata=resp.metadata,
            )

    @property
    def call_count(self) -> int:
        return self._call_count
