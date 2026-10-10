from __future__ import annotations

from labkit.llm import LLMClient, ReplayClient, SimClient


def test_clients_fulfill_llm_client_protocol() -> None:
    replay = ReplayClient()
    sim = SimClient(seed=123)

    assert isinstance(replay, LLMClient)
    assert isinstance(sim, LLMClient)
