from __future__ import annotations

import hashlib
import re
from typing import Any

# Pattern matching words, numbers, punctuation, and whitespace sequences
_TOKEN_PATTERN = re.compile(r"""\w+|[^\w\s]|\s+""", re.UNICODE)


class OfflineTokenizer:
    """Deterministic offline token counter and prefix hasher requiring zero network calls."""

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self.encoding_name = encoding_name
        self._tiktoken_enc: Any = None

        # Attempt to use tiktoken if available offline
        try:
            import tiktoken
            self._tiktoken_enc = tiktoken.get_encoding(encoding_name)
        except Exception:
            self._tiktoken_enc = None

    def encode(self, text: str) -> list[int]:
        if self._tiktoken_enc is not None:
            try:
                return self._tiktoken_enc.encode(text)
            except Exception:
                pass

        # Offline deterministic fallback
        matches = _TOKEN_PATTERN.findall(text)
        tokens: list[int] = []
        for piece in matches:
            # Deterministic hash modulo 100000 to represent token ID
            h = int(hashlib.md5(piece.encode("utf-8")).hexdigest()[:6], 16)
            tokens.append(h)
        return tokens

    def decode(self, tokens: list[int]) -> str:
        if self._tiktoken_enc is not None:
            try:
                return self._tiktoken_enc.decode(tokens)
            except Exception:
                pass
        # Fallback placeholder when decoding offline mock tokens
        return f"[Decoded {len(tokens)} offline tokens]"

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        if self._tiktoken_enc is not None:
            try:
                return len(self._tiktoken_enc.encode(text))
            except Exception:
                pass
        return len(self.encode(text))

    @staticmethod
    def prefix_hash(prefix_text: str) -> str:
        """Computes a canonical SHA-256 hash for Prompt Caching prefix stability verification."""
        normalized = prefix_text.strip().encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()
