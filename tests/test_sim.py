from __future__ import annotations

import pytest
from labkit.sim import SimClient


def test_sim_client_reproducibility_same_seed_yields_same_results() -> None:
    """Verifies that the same seed produces the exact same sequence of results."""
    client_a = SimClient(seed=42, pass_rate=0.7)
    client_b = SimClient(seed=42, pass_rate=0.7)

    results_a = [client_a.complete(f"Prompt {i}").content for i in range(20)]
    results_b = [client_b.complete(f"Prompt {i}").content for i in range(20)]

    assert results_a == results_b


def test_sim_client_distinct_seeds_yield_different_results() -> None:
    """Verifies that different seeds produce different outcomes for non-trivial pass rates."""
    client_a = SimClient(seed=1001, pass_rate=0.5)
    client_b = SimClient(seed=9999, pass_rate=0.5)

    results_a = [client_a.complete(f"Prompt {i}").content for i in range(30)]
    results_b = [client_b.complete(f"Prompt {i}").content for i in range(30)]

    assert results_a != results_b


def test_sim_client_pass_rate_extremes() -> None:
    client_always_pass = SimClient(seed=1, pass_rate=1.0)
    for _ in range(10):
        resp = client_always_pass.complete("test")
        assert resp.finish_reason == "stop"
        assert resp.content == client_always_pass.success_content

    client_always_fail = SimClient(seed=1, pass_rate=0.0)
    for _ in range(10):
        resp = client_always_fail.complete("test")
        assert resp.finish_reason == "error"
        assert resp.content == client_always_fail.failure_content


def test_sim_client_invalid_pass_rate() -> None:
    with pytest.raises(ValueError, match="pass_rate must be between 0.0 and 1.0"):
        SimClient(seed=1, pass_rate=1.5)


def test_sim_client_streaming() -> None:
    client = SimClient(seed=42, pass_rate=1.0, success_content="Alpha Beta Gamma")
    chunks = list(client.stream("Prompt"))
    assert len(chunks) == 3
    assert chunks[0].delta == "Alpha "
    assert chunks[1].delta == "Beta "
    assert chunks[2].delta == "Gamma"
    assert chunks[2].is_final


def test_sim_client_string_seed_reproducibility() -> None:
    client_a = SimClient(seed="student-practitioner-alice", pass_rate=0.7)
    client_b = SimClient(seed="student-practitioner-alice", pass_rate=0.7)

    results_a = [client_a.complete(f"Prompt {i}").metadata["roll"] for i in range(20)]
    results_b = [client_b.complete(f"Prompt {i}").metadata["roll"] for i in range(20)]

    assert results_a == results_b


def test_sim_client_string_seed_distinct_users() -> None:
    client_alice = SimClient(seed="student-practitioner-alice", pass_rate=0.5)
    client_bob = SimClient(seed="student-practitioner-bob", pass_rate=0.5)

    results_alice = [client_alice.complete(f"Prompt {i}").metadata["roll"] for i in range(20)]
    results_bob = [client_bob.complete(f"Prompt {i}").metadata["roll"] for i in range(20)]

    assert results_alice != results_bob


def test_sim_client_string_seed_reset() -> None:
    client = SimClient(seed="student-reset-test", pass_rate=0.7)
    first_run = [client.complete(f"Prompt {i}").metadata["roll"] for i in range(10)]
    client.reset()
    second_run = [client.complete(f"Prompt {i}").metadata["roll"] for i in range(10)]

    assert first_run == second_run


def test_sim_client_string_seed_independent_of_pythonhashseed() -> None:
    import os
    import subprocess
    import sys

    cmd = [
        sys.executable,
        "-c",
        (
            "from labkit.sim import SimClient\n"
            "c = SimClient(seed='cross_process_seed', pass_rate=0.5)\n"
            "print(c.complete('test').metadata['roll'])\n"
        ),
    ]

    env1 = os.environ.copy()
    env1["PYTHONHASHSEED"] = "12345"
    out1 = subprocess.check_output(cmd, env=env1, text=True, cwd=os.path.dirname(os.path.dirname(__file__))).strip()

    env2 = os.environ.copy()
    env2["PYTHONHASHSEED"] = "67890"
    out2 = subprocess.check_output(cmd, env=env2, text=True, cwd=os.path.dirname(os.path.dirname(__file__))).strip()

    assert out1 == out2
    assert float(out1) > 0.0

