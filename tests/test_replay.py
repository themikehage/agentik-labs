from __future__ import annotations

import pytest
from labkit.replay import ReplayClient, CassetteMismatchError, LLMMessage


def test_replay_client_exact_matching() -> None:
    client = ReplayClient()
    client.add_recording(
        prompt="Explain KV cache in 5 words.",
        response_content="Avoids recomputing past token keys.",
        prompt_tokens=7,
        completion_tokens=6,
    )

    resp = client.complete("Explain KV cache in 5 words.")
    assert resp.content == "Avoids recomputing past token keys."
    assert resp.prompt_tokens == 7
    assert resp.completion_tokens == 6
    assert resp.total_tokens == 13
    assert resp.finish_reason == "stop"


def test_replay_client_mismatch_error() -> None:
    client = ReplayClient()
    client.add_recording(prompt="foo", response_content="bar")

    with pytest.raises(CassetteMismatchError, match="No cassette match found"):
        client.complete("unrecorded prompt")


def test_replay_client_streaming() -> None:
    client = ReplayClient()
    client.add_recording(
        prompt="Stream tokens",
        response_content="TokenA TokenB",
        chunks=["TokenA ", "TokenB"],
    )

    chunks = list(client.stream("Stream tokens"))
    assert len(chunks) == 2
    assert chunks[0].delta == "TokenA "
    assert not chunks[0].is_final
    assert chunks[1].delta == "TokenB"
    assert chunks[1].is_final
    assert chunks[1].finish_reason == "stop"


def test_replay_client_message_sequence_prompt() -> None:
    client = ReplayClient()
    client.add_recording(
        prompt="system: You are a helper\nuser: Hello",
        response_content="Hi there!",
    )

    messages = [
        LLMMessage(role="system", content="You are a helper"),
        LLMMessage(role="user", content="Hello"),
    ]
    resp = client.complete(messages)
    assert resp.content == "Hi there!"
