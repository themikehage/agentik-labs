from __future__ import annotations

from labkit.seed import derive_seed, parameterize_lab


def test_derive_seed_deterministic() -> None:
    seed1 = derive_seed("alice", "lab-m1")
    seed2 = derive_seed("alice", "lab-m1")
    seed_bob = derive_seed("bob", "lab-m1")

    assert seed1 == seed2
    assert seed1 != seed_bob
    assert 0 <= seed1 <= 0x7FFFFFFF


def test_parameterize_lab_reproducibility() -> None:
    space = {
        "pii_entity": ["EMAIL", "PASSPORT", "IBAN", "SSN"],
        "cache_limit": [1024, 2048, 4096],
    }

    params_alice_1 = parameterize_lab("alice_gh", "m1-inferencia", space)
    params_alice_2 = parameterize_lab("alice_gh", "m1-inferencia", space)
    params_bob = parameterize_lab("bob_gh", "m1-inferencia", space)

    assert params_alice_1 == params_alice_2
    assert params_alice_1["pii_entity"] in space["pii_entity"]
    assert params_alice_1["cache_limit"] in space["cache_limit"]
