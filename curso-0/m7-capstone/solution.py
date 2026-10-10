from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from labkit.clock import VirtualClock
from labkit.seed import derive_seed


class EnterpriseServiceError(Exception):
    def __init__(self, message: str, error_code: str = "SERVICE_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


@dataclass
class StreamingProfile:
    ttft_seconds: float
    tpot_seconds: float
    itl_p50_seconds: float
    itl_p95_seconds: float
    total_duration_seconds: float
    token_count: int


@dataclass
class OTelSpanRecord:
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def set_attribute(self, key: str, value: Any) -> None:
        if key == "gen_ai.system":
            raise ValueError("Deprecated 'gen_ai.system' is prohibited. Use 'gen_ai.provider.name'.")
        if any(c in key.lower() for c in ["cost", "price", "usd", "cents"]):
            raise ValueError(f"Financial cost attribute '{key}' is forbidden inside OTel span.")
        self.attributes[key] = value


class EnterpriseInferenceService:
    DEFAULT_PRICING = {
        "version": "2026.01",
        "models": {
            "agentik-reason-70b": {
                "input_usd_per_m": 3.00,
                "output_usd_per_m": 12.00,
                "cache_read_usd_per_m": 0.50,
            },
            "agentik-fast-8b": {
                "input_usd_per_m": 0.50,
                "output_usd_per_m": 1.50,
                "cache_read_usd_per_m": 0.10,
            },
        },
    }

    def __init__(
        self,
        clock: VirtualClock | None = None,
        seed: int = 42,
        pricing_catalog: dict[str, Any] | None = None,
    ) -> None:
        self.clock = clock or VirtualClock(initial_time=100.0)
        self.seed = seed
        self.pricing = pricing_catalog or self.DEFAULT_PRICING
        self.spans: list[OTelSpanRecord] = []

    def serialize_prompt(
        self,
        static_system_blocks: list[str],
        few_shots: list[dict[str, str]],
        user_input: str,
    ) -> tuple[str, str]:
        sys_str = "\n".join(static_system_blocks)
        shots_str = json.dumps(few_shots, sort_keys=True, ensure_ascii=False)
        prefix = f"{sys_str}\n{shots_str}"
        prefix_hash = hashlib.sha256(prefix.encode("utf-8")).hexdigest()
        full_prompt = f"{prefix}\nUSER_QUERY:\n{user_input}"
        return full_prompt, prefix_hash

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
        full_prompt, prefix_hash = self.serialize_prompt(static_prefix_blocks, few_shots, user_input)
        tokens = generated_tokens or ["The", " enterprise", " service", " is", " verified", "."]

        start_time = self.clock.now()
        ttft = 0.08 if is_cache_hit else 0.45
        self.clock.sleep(ttft)
        first_token_time = self.clock.now()

        itl_intervals: list[float] = []
        last_time = first_token_time
        for _ in tokens[1:]:
            interval = 0.018
            self.clock.sleep(interval)
            current_time = self.clock.now()
            itl_intervals.append(current_time - last_time)
            last_time = current_time

        end_time = self.clock.now()
        total_time = end_time - start_time
        tpot = sum(itl_intervals) / len(itl_intervals) if itl_intervals else 0.0

        itl_sorted = sorted(itl_intervals) if itl_intervals else [0.0]
        p50 = itl_sorted[len(itl_sorted) // 2]
        p95 = itl_sorted[int(len(itl_sorted) * 0.95)]

        profile = StreamingProfile(
            ttft_seconds=round(ttft, 4),
            tpot_seconds=round(tpot, 4),
            itl_p50_seconds=round(p50, 4),
            itl_p95_seconds=round(p95, 4),
            total_duration_seconds=round(total_time, 4),
            token_count=len(tokens),
        )

        input_tokens = 1200
        output_tokens = len(tokens)
        cache_read_tokens = 1000 if is_cache_hit else 0

        span = OTelSpanRecord(name=f"chat {model_name}")
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", "agentik-enterprise")
        span.set_attribute("gen_ai.request.model", model_name)
        span.set_attribute("gen_ai.response.model", model_name)
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        if cache_read_tokens > 0:
            span.set_attribute("gen_ai.usage.cache_read.input_tokens", cache_read_tokens)
        self.spans.append(span)

        rates = self.pricing["models"].get(model_name, {"input_usd_per_m": 1.0, "output_usd_per_m": 2.0, "cache_read_usd_per_m": 0.2})
        cost_in = (input_tokens / 1_000_000.0) * rates["input_usd_per_m"]
        cost_out = (output_tokens / 1_000_000.0) * rates["output_usd_per_m"]
        cost_cache = (cache_read_tokens / 1_000_000.0) * rates.get("cache_read_usd_per_m", 0.0)
        cost_usd = round(cost_in + cost_out + cost_cache, 6)

        return {
            "tenant_id": tenant_id,
            "prefix_hash": prefix_hash,
            "tokens": tokens,
            "profile": profile,
            "span": span,
            "cost_usd": cost_usd,
        }

    def validate_business_output(self, raw_json_str: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_json_str)
        except json.JSONDecodeError as err:
            return {"is_valid": False, "layer_failed": "syntax", "error": str(err)}

        if not isinstance(parsed, dict) or "action" not in parsed or "amount_cents" not in parsed:
            return {"is_valid": False, "layer_failed": "schema", "error": "Missing required schema fields"}

        if not isinstance(parsed["amount_cents"], int) or parsed["amount_cents"] <= 0:
            return {
                "is_valid": False,
                "layer_failed": "business_semantic",
                "error": "Amount in cents must be a positive integer.",
            }

        return {"is_valid": True, "layer_failed": None, "data": parsed}

    def execute_sandboxed_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        requires_human_confirmation: bool = False,
        is_confirmed_by_human: bool = False,
        container_flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if requires_human_confirmation and not is_confirmed_by_human:
            return {
                "status": "APPROVAL_REQUIRED",
                "is_error": True,
                "message": f"Action '{tool_name}' is irreversible and requires explicit human confirmation.",
            }

        flags = container_flags or {
            "network": "none",
            "read_only": True,
            "cap_drop": ["ALL"],
            "user": "10001:10001",
        }

        if flags.get("network") != "none":
            raise EnterpriseServiceError("Security violation: tool executed with open network", "NETWORK_NOT_ISOLATED")
        if flags.get("user") in {"0", "root"}:
            raise EnterpriseServiceError("Security violation: tool executed as root", "ROOT_FORBIDDEN")

        return {
            "status": "EXECUTED",
            "is_error": False,
            "tool_name": tool_name,
            "output": f"Successfully executed {tool_name} with args {arguments}",
        }

    def evaluate_reliability_ci(
        self,
        sample_scores: list[float],
        threshold_ci_lower: float = 0.75,
        num_bootstrap: int = 1000,
    ) -> dict[str, Any]:
        if not sample_scores:
            raise ValueError("Evaluation scores sample cannot be empty.")

        rng = random.Random(self.seed)
        n = len(sample_scores)
        bootstrap_means: list[float] = []

        for _ in range(num_bootstrap):
            resample = [sample_scores[rng.randrange(n)] for _ in range(n)]
            bootstrap_means.append(sum(resample) / float(n))

        bootstrap_means.sort()
        ci_lower = bootstrap_means[int(num_bootstrap * 0.025)]
        ci_upper = bootstrap_means[int(num_bootstrap * 0.975)]
        mean_score = sum(sample_scores) / float(n)

        passed = ci_lower >= threshold_ci_lower

        return {
            "passed": passed,
            "mean_score": round(mean_score, 4),
            "ci_lower_95": round(ci_lower, 4),
            "ci_upper_95": round(ci_upper, 4),
            "threshold_ci_lower": threshold_ci_lower,
        }


def validate_design_document(markdown_text: str) -> dict[str, Any]:
    required_sections = [
        "# Architecture & System Design",
        "## Quantitative SLO Budgets",
        "## Resilience & Rate Limiting",
        "## Security & Containment Policy",
        "## Evaluation Methodology & Acceptance Thresholds",
    ]
    missing = [sec for sec in required_sections if sec not in markdown_text]
    return {
        "is_valid": len(missing) == 0,
        "missing_sections": missing,
        "declared_budgets_present": "TTFT" in markdown_text and "ITL" in markdown_text and "bootstrap" in markdown_text,
    }
