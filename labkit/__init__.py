"""
agentik-labkit: Core library for deterministic, zero-cost, reproducible LLM labs.
"""

from labkit.clock import Clock, RealClock, VirtualClock
from labkit.llm import (
    LLMClient,
    LLMMessage,
    LLMResponse,
    LLMStreamChunk,
    ReplayClient,
    SimClient,
    CassetteMismatchError,
)
from labkit.fake_provider import FakeProviderServer
from labkit.tokenizer import OfflineTokenizer
from labkit.assert_env import (
    assert_fs_matches,
    assert_db_matches,
    assert_http_endpoint,
    EnvironmentAssertionError,
)
from labkit.sandbox import (
    HardenedSandbox,
    HardeningViolationError,
    validate_hardened_flags,
    REQUIRED_HARDENING_FLAGS,
)
from labkit.seed import derive_seed, parameterize_lab

__all__ = [
    # Clock
    "Clock",
    "RealClock",
    "VirtualClock",
    # LLM Port & Adapters
    "LLMClient",
    "LLMMessage",
    "LLMResponse",
    "LLMStreamChunk",
    "ReplayClient",
    "SimClient",
    "CassetteMismatchError",
    # Fake Provider
    "FakeProviderServer",
    # Tokenizer
    "OfflineTokenizer",
    # Outcome Assertions
    "assert_fs_matches",
    "assert_db_matches",
    "assert_http_endpoint",
    "EnvironmentAssertionError",
    # Hardened Sandbox
    "HardenedSandbox",
    "HardeningViolationError",
    "validate_hardened_flags",
    "REQUIRED_HARDENING_FLAGS",
    # Seeding
    "derive_seed",
    "parameterize_lab",
]
