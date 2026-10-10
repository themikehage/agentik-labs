from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Callable


class PromptCacheSerializer:
    @staticmethod
    def compute_sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def serialize_prompt(
        self,
        static_system_prefix: str,
        few_shot_examples: list[dict[str, str]],
        schema_definitions: dict[str, Any],
        dynamic_variables: dict[str, Any],
        place_variables_early: bool = False,
    ) -> tuple[str, str]:
        examples_str = json.dumps(few_shot_examples, sort_keys=True, ensure_ascii=False)
        schema_str = json.dumps(schema_definitions, sort_keys=True, ensure_ascii=False)
        variables_str = json.dumps(dynamic_variables, sort_keys=True, ensure_ascii=False)

        if place_variables_early:
            prefix = f"{variables_str}\n{static_system_prefix}\n{examples_str}\n{schema_str}"
            full_prompt = prefix
        else:
            prefix = f"{static_system_prefix}\n{examples_str}\n{schema_str}"
            full_prompt = f"{prefix}\nUSER_INPUT:\n{variables_str}"

        prefix_hash = self.compute_sha256(prefix)
        return full_prompt, prefix_hash


@dataclass(frozen=True)
class PricingModel:
    base_input_usd_per_m: float
    cache_write_usd_per_m: float
    cache_read_usd_per_m: float
    output_usd_per_m: float
    version: str = "2026-v1"


class PromptCacheEconomics:
    def __init__(self, pricing: PricingModel) -> None:
        self.pricing = pricing

    def calculate_break_even_reads(self, ignore_write_surcharge: bool = False) -> int:
        if ignore_write_surcharge:
            return 1

        denom = self.pricing.base_input_usd_per_m - self.pricing.cache_read_usd_per_m
        if denom <= 0:
            return 1
        numerator = self.pricing.cache_write_usd_per_m - self.pricing.cache_read_usd_per_m
        n = math.ceil(numerator / denom)
        return max(1, n)

    def calculate_cost_comparison(self, prefix_tokens: int, reuse_count: int) -> dict[str, float]:
        tokens_in_millions = prefix_tokens / 1_000_000.0
        cost_uncached = reuse_count * (tokens_in_millions * self.pricing.base_input_usd_per_m)
        if reuse_count <= 0:
            cost_cached = 0.0
        else:
            write_cost = tokens_in_millions * self.pricing.cache_write_usd_per_m
            read_cost = (reuse_count - 1) * (tokens_in_millions * self.pricing.cache_read_usd_per_m)
            cost_cached = write_cost + read_cost

        savings_ratio = (
            (cost_uncached - cost_cached) / cost_uncached if cost_uncached > 0 else 0.0
        )
        return {
            "cost_uncached_usd": round(cost_uncached, 6),
            "cost_cached_usd": round(cost_cached, 6),
            "savings_ratio": round(savings_ratio, 4),
        }


@dataclass
class ValidationResult:
    is_valid: bool
    layer_failed: str | None = None
    error_message: str | None = None
    data: dict[str, Any] | None = None


class ThreeLayerValidator:
    def validate_invoice(self, raw_payload: str) -> ValidationResult:
        try:
            parsed = json.loads(raw_payload)
        except json.JSONDecodeError as err:
            return ValidationResult(
                is_valid=False,
                layer_failed="syntax",
                error_message=f"Syntax Error: Invalid JSON - {err}",
            )

        if not isinstance(parsed, dict):
            return ValidationResult(
                is_valid=False,
                layer_failed="schema",
                error_message="Schema Error: Root payload must be an object",
            )

        required_fields = {"invoice_id", "items", "total_amount_usd", "currency"}
        if not required_fields.issubset(parsed.keys()):
            missing = required_fields - parsed.keys()
            return ValidationResult(
                is_valid=False,
                layer_failed="schema",
                error_message=f"Schema Error: Missing required fields {missing}",
            )

        if not isinstance(parsed["items"], list):
            return ValidationResult(
                is_valid=False,
                layer_failed="schema",
                error_message="Schema Error: 'items' must be a list",
            )

        for item in parsed["items"]:
            if not isinstance(item, dict) or "qty" not in item or "unit_price" not in item:
                return ValidationResult(
                    is_valid=False,
                    layer_failed="schema",
                    error_message="Schema Error: Each item must have 'qty' and 'unit_price'",
                )

        if not parsed["items"]:
            return ValidationResult(
                is_valid=False,
                layer_failed="business_semantic",
                error_message="Business Rule Violation: Invoice items list cannot be empty",
            )

        calculated_total = 0.0
        for item in parsed["items"]:
            qty = item["qty"]
            price = item["unit_price"]
            if qty <= 0 or price <= 0:
                return ValidationResult(
                    is_valid=False,
                    layer_failed="business_semantic",
                    error_message="Business Rule Violation: Item quantity and price must be positive",
                )
            calculated_total += qty * price

        declared_total = float(parsed["total_amount_usd"])
        if abs(calculated_total - declared_total) > 0.01:
            return ValidationResult(
                is_valid=False,
                layer_failed="business_semantic",
                error_message=(
                    f"Business Rule Violation: Declared total ({declared_total}) does not match "
                    f"sum of item line totals ({calculated_total})"
                ),
            )

        return ValidationResult(is_valid=True, data=parsed)


@dataclass
class ToolExecutionResult:
    is_error: bool
    content: Any
    error_code: str | None = None
    message: str | None = None


class ToolExecutionEngine:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[dict[str, Any], Callable[..., Any]]] = {}

    def register_tool(
        self,
        name: str,
        parameters_schema: dict[str, type],
        handler: Callable[..., Any],
    ) -> None:
        self._tools[name] = (parameters_schema, handler)

    def execute_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        if tool_name not in self._tools:
            return ToolExecutionResult(
                is_error=True,
                content=None,
                error_code="TOOL_NOT_FOUND",
                message=f"Tool '{tool_name}' is not registered in runtime.",
            )

        schema, handler = self._tools[tool_name]
        for param_name, expected_type in schema.items():
            if param_name not in arguments:
                return ToolExecutionResult(
                    is_error=True,
                    content=None,
                    error_code="INVALID_ARGUMENTS",
                    message=f"Missing required parameter '{param_name}'.",
                )
            if not isinstance(arguments[param_name], expected_type):
                return ToolExecutionResult(
                    is_error=True,
                    content=None,
                    error_code="INVALID_ARGUMENTS",
                    message=(
                        f"Parameter '{param_name}' must be of type {expected_type.__name__}, "
                        f"got {type(arguments[param_name]).__name__}."
                    ),
                )

        try:
            output = handler(**arguments)
            return ToolExecutionResult(
                is_error=False,
                content=output,
            )
        except Exception as ex:
            return ToolExecutionResult(
                is_error=True,
                content=None,
                error_code="EXECUTION_FAILED",
                message=f"Tool execution failed internally: {ex}",
            )
