# STUB: implement the capstone here. See README.md. Run: uv run pytest curso-0/m7-capstone/tests
"""C0-M7 capstone: enterprise inference microservice (student stub)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from labkit.clock import VirtualClock


class EnterpriseServiceError(Exception):
    """Service-level error carrying a human message and a stable error code."""

    def __init__(self, message: str, error_code: str = "SERVICE_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


@dataclass
class StreamingProfile:
    """Streaming latency profile, all durations in seconds."""

    ttft_seconds: float
    tpot_seconds: float
    itl_p50_seconds: float
    itl_p95_seconds: float
    total_duration_seconds: float
    token_count: int


@dataclass
class OTelSpanRecord:
    """Minimal OpenTelemetry GenAI span record."""

    name: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def set_attribute(self, key: str, value: Any) -> None:
        """Store an attribute, rejecting deprecated or financial-cost keys with ValueError.

        The deprecated key 'gen_ai.system' must raise ValueError whose message
        starts with "Deprecated 'gen_ai.system'". Cost/price attributes are forbidden.
        """
        raise NotImplementedError("Implement span attribute validation")


class EnterpriseInferenceService:
    """Streaming inference service with validation, tracing, sandboxing and evals."""

    def __init__(
        self,
        clock: VirtualClock | None = None,
        seed: int = 42,
        pricing_catalog: dict[str, Any] | None = None,
    ) -> None:
        self.clock = clock if clock is not None else VirtualClock(initial_time=100.0)
        self.seed = seed
        self.pricing: dict[str, Any] = pricing_catalog or {}
        self.spans: list[OTelSpanRecord] = []

    def serialize_prompt(
        self,
        static_system_blocks: list[str],
        few_shots: list[dict[str, str]],
        user_input: str,
    ) -> tuple[str, str]:
        """Return (full_prompt, prefix_hash) where the 64-char hex hash depends only
        on the static prefix (system blocks + few-shots), never on user_input."""
        raise NotImplementedError("Implement cache-friendly prompt serialization")

    def stream_inference(
        self,
        tenant_id: str,
        static_prefix_blocks: list[str],
        few_shots: list[dict[str, str]],
        user_input: str,
        model_name: str = "agentik-reason-70b",
        is_cache_hit: bool = False,
        generated_tokens: list[str] | None = None,
    ) -> dict[str, Any]:
        """Simulate streaming on the injected clock and return a dict with keys
        tenant_id, prefix_hash, tokens, profile (StreamingProfile), span
        (OTelSpanRecord) and cost_usd.

        TTFT must be much lower on a cache hit; ITL p50/p95 must stay within the
        budgets in README.md. The span uses current GenAI semconv attributes
        (including cache-read tokens on a hit) and never contains cost data;
        cost is computed outside the span from the pricing catalog.
        """
        raise NotImplementedError("Implement streaming inference with metrics, span and cost")

    def validate_business_output(self, raw_json_str: str) -> dict[str, Any]:
        """Three-layer validation (syntax, schema, business_semantic).

        Return {"is_valid": bool, "layer_failed": str | None, ...}. Payloads need
        'action' and 'amount_cents'; amount_cents must be a positive integer.
        """
        raise NotImplementedError("Implement three-layer output validation")

    def execute_sandboxed_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        requires_human_confirmation: bool = False,
        is_confirmed_by_human: bool = False,
        container_flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a tool under a hardened container policy.

        Unconfirmed irreversible actions return status "APPROVAL_REQUIRED" with
        is_error True. Network-enabled containers raise EnterpriseServiceError
        (message contains "tool executed with open network"); root users are also
        rejected. Success returns status "EXECUTED" with is_error False.
        """
        raise NotImplementedError("Implement sandboxed tool execution")

    def evaluate_reliability_ci(
        self,
        sample_scores: list[float],
        threshold_ci_lower: float = 0.75,
        num_bootstrap: int = 1000,
    ) -> dict[str, Any]:
        """Deterministic (seeded) 95% bootstrap CI over the scores.

        Return passed, mean_score, ci_lower_95, ci_upper_95, threshold_ci_lower.
        Approval depends on the CI lower bound, not the mean. Empty input raises ValueError.
        """
        raise NotImplementedError("Implement bootstrap reliability evaluation")


def validate_design_document(markdown_text: str) -> dict[str, Any]:
    """Validate DESIGN.md structure.

    Return {"is_valid": bool, "missing_sections": list[str],
    "declared_budgets_present": bool}. See README.md for the required sections
    and the budgets that must be declared.
    """
    raise NotImplementedError("Implement DESIGN.md schema validation")
