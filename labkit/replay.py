from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any, Iterator, Sequence


class CassetteMismatchError(Exception):
    """Raised when a prompt does not match any entry in the loaded cassette."""
    pass


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = "agentik-replay-v1"
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMStreamChunk:
    delta: str
    is_final: bool = False
    finish_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ReplayClient:
    """Deterministic LLM adapter that replays pre-recorded responses without network."""

    def __init__(self, cassettes: Sequence[dict[str, Any]] | Path | str | None = None) -> None:
        self._cassettes: list[dict[str, Any]] = []
        if cassettes is not None:
            if isinstance(cassettes, (str, Path)):
                self.load_from_file(Path(cassettes))
            else:
                self._cassettes = list(cassettes)
        self._call_history: list[str] = []

    def load_from_file(self, file_path: Path) -> None:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
        if isinstance(data, list):
            self._cassettes = data
        elif isinstance(data, dict):
            self._cassettes = [data]
        else:
            raise ValueError(f"Invalid cassette format in {file_path}")

    def add_recording(
        self,
        prompt: str,
        response_content: str,
        prompt_tokens: int = 10,
        completion_tokens: int = 20,
        chunks: list[str] | None = None,
        model: str = "agentik-replay-v1",
    ) -> None:
        self._cassettes.append({
            "prompt": prompt,
            "response_content": response_content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "chunks": chunks or [response_content],
            "model": model,
        })

    def _normalize_prompt(self, prompt: str | Sequence[LLMMessage] | Sequence[dict[str, Any]]) -> str:
        if isinstance(prompt, str):
            return prompt.strip()
        if isinstance(prompt, Sequence):
            parts: list[str] = []
            for item in prompt:
                if isinstance(item, LLMMessage):
                    parts.append(f"{item.role}: {item.content}")
                elif isinstance(item, dict):
                    parts.append(f"{item.get('role', 'user')}: {item.get('content', '')}")
                else:
                    parts.append(str(item))
            return "\n".join(parts).strip()
        return str(prompt).strip()

    def _find_matching_cassette(self, normalized_prompt: str) -> dict[str, Any]:
        for entry in self._cassettes:
            expected = self._normalize_prompt(entry.get("prompt", ""))
            if expected == normalized_prompt:
                return entry
            # Also allow prefix match or containment if specified in metadata
            if entry.get("match_type") == "prefix" and normalized_prompt.startswith(expected):
                return entry
            if entry.get("match_type") == "contains" and expected in normalized_prompt:
                return entry
        raise CassetteMismatchError(
            f"No cassette match found for prompt: {normalized_prompt[:100]}...\n"
            f"Available prompts in cassette: {[e.get('prompt') for e in self._cassettes]}"
        )

    def complete(self, prompt: str | Sequence[LLMMessage], **kwargs: Any) -> LLMResponse:
        norm = self._normalize_prompt(prompt)
        self._call_history.append(norm)
        entry = self._find_matching_cassette(norm)

        content = entry.get("response_content", "")
        p_tok = entry.get("prompt_tokens", len(norm.split()))
        c_tok = entry.get("completion_tokens", len(content.split()))
        total_tok = entry.get("total_tokens", p_tok + c_tok)
        model = entry.get("model", "agentik-replay-v1")

        return LLMResponse(
            content=content,
            prompt_tokens=p_tok,
            completion_tokens=c_tok,
            total_tokens=total_tok,
            model=model,
            finish_reason="stop",
            metadata={"matched_prompt": entry.get("prompt")},
        )

    def stream(self, prompt: str | Sequence[LLMMessage], **kwargs: Any) -> Iterator[LLMStreamChunk]:
        norm = self._normalize_prompt(prompt)
        self._call_history.append(norm)
        entry = self._find_matching_cassette(norm)

        chunks = entry.get("chunks")
        if not chunks:
            full_text = entry.get("response_content", "")
            chunks = [word + " " for word in full_text.split()]
            if not chunks:
                chunks = [""]

        total_chunks = len(chunks)
        for idx, chunk in enumerate(chunks):
            is_final = idx == total_chunks - 1
            yield LLMStreamChunk(
                delta=chunk,
                is_final=is_final,
                finish_reason="stop" if is_final else None,
            )

    @property
    def call_history(self) -> list[str]:
        return list(self._call_history)
