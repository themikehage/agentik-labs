from __future__ import annotations

from labkit.tokenizer import OfflineTokenizer


def test_offline_tokenizer_token_counting() -> None:
    tok = OfflineTokenizer()
    assert tok.count_tokens("") == 0
    assert tok.count_tokens("Hello world") >= 2

    tokens = tok.encode("Multi-agent architecture 2026")
    assert isinstance(tokens, list)
    assert len(tokens) >= 3


def test_prefix_hash_determinism() -> None:
    prefix_a = "You are a senior enterprise architect. Follow RFC 2119 strictly."
    prefix_b = "You are a senior enterprise architect. Follow RFC 2119 strictly."
    prefix_diff = "You are a junior assistant. Answer quickly."

    hash_a = OfflineTokenizer.prefix_hash(prefix_a)
    hash_b = OfflineTokenizer.prefix_hash(prefix_b)
    hash_diff = OfflineTokenizer.prefix_hash(prefix_diff)

    assert hash_a == hash_b
    assert hash_a != hash_diff
    assert len(hash_a) == 64  # SHA-256 hex length
