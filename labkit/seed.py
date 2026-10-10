from __future__ import annotations

import hashlib
import random
from typing import Any, Sequence


def derive_seed(
    user_identifier: str | int,
    lab_name: str = "default-lab",
    salt: str = "agentik-v3-deterministic",
) -> int:
    """
    Derives a deterministic 32-bit integer seed for lab scenario parameterization.

    Guarantees:
    - Same user + lab => identical seed across all runs and platforms.
    - Different users => distinct parameters (anti-plagiarism).
    """
    norm_user = str(user_identifier).strip().lower()
    norm_lab = str(lab_name).strip().lower()
    raw = f"{norm_user}:{norm_lab}:{salt}".encode("utf-8")

    digest = hashlib.sha256(raw).hexdigest()
    # 31-bit positive signed integer
    seed_int = int(digest[:8], 16) & 0x7FFFFFFF
    return seed_int


def parameterize_lab(
    user_identifier: str | int,
    lab_name: str,
    parameter_space: dict[str, Sequence[Any]],
) -> dict[str, Any]:
    """
    Selects reproducible per-user scenario parameters from a predefined parameter space.

    Example:
    parameter_space = {
        "target_pii_entities": ["EMAIL", "IBAN", "CREDIT_CARD", "PASSPORT"],
        "cache_token_threshold": [1024, 2048, 4096],
        "chaos_injection_step": ["auth_refresh", "vector_search", "tool_call"],
    }
    """
    seed_int = derive_seed(user_identifier, lab_name)
    rng = random.Random(seed_int)

    assigned: dict[str, Any] = {}
    for key, choices in parameter_space.items():
        if not choices:
            continue
        assigned[key] = rng.choice(list(choices))

    return assigned
