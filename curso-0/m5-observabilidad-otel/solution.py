from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class SemconvViolationError(Exception):
    pass


@dataclass
class OTelGenAISpan:
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def set_attribute(self, key: str, value: Any) -> None:
        if key == "gen_ai.system":
            raise SemconvViolationError(
                "Deprecated attribute 'gen_ai.system' is prohibited. Use 'gen_ai.provider.name' instead."
            )
        if any(cost_word in key.lower() for cost_word in ["cost", "price", "usd", "cents"]):
            raise SemconvViolationError(
                f"Financial cost attribute '{key}' is forbidden inside OpenTelemetry GenAI span. "
                "Cost calculation must be computed in the backend/pipeline."
            )
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append({"name": name, "attributes": attributes or {}})


class InMemorySpanExporter:
    def __init__(self) -> None:
        self.exported_spans: list[OTelGenAISpan] = []

    def export(self, span: OTelGenAISpan) -> None:
        self.exported_spans.append(span)

    def clear(self) -> None:
        self.exported_spans.clear()


class PIISanitizer:
    API_KEY_REGEX = re.compile(r"sk-[a-zA-Z0-9_-]{16,}")
    BEARER_REGEX = re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{16,}")
    EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

    @classmethod
    def redact(cls, text: str) -> str:
        s = cls.API_KEY_REGEX.sub("[REDACTED_API_KEY]", text)
        s = cls.BEARER_REGEX.sub("Bearer [REDACTED_TOKEN]", s)
        s = cls.EMAIL_REGEX.sub("[REDACTED_EMAIL]", s)
        return s


class OTelGenAITracer:
    def __init__(self, exporter: InMemorySpanExporter) -> None:
        self.exporter = exporter
        self.total_tokens_aggregated = 0

    def start_chat_span(
        self,
        provider_name: str,
        request_model: str,
        response_model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_input_tokens: int = 0,
        prompt_text: str | None = None,
        completion_text: str | None = None,
        capture_content_opt_in: bool = False,
    ) -> OTelGenAISpan:
        span = OTelGenAISpan(name=f"chat {request_model}")

        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", provider_name)
        span.set_attribute("gen_ai.request.model", request_model)
        span.set_attribute("gen_ai.response.model", response_model)
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", output_tokens)

        if cache_read_input_tokens > 0:
            span.set_attribute("gen_ai.usage.cache_read.input_tokens", cache_read_input_tokens)

        if capture_content_opt_in:
            if prompt_text:
                span.set_attribute("gen_ai.prompt", PIISanitizer.redact(prompt_text))
            if completion_text:
                span.set_attribute("gen_ai.completion", PIISanitizer.redact(completion_text))

        self.total_tokens_aggregated += (input_tokens + output_tokens)
        self.exporter.export(span)
        return span


class PipelineCostCalculator:
    def __init__(self, pricing_table: dict[str, dict[str, float]]) -> None:
        self.pricing_table = pricing_table

    def compute_cost_for_span(self, span: OTelGenAISpan) -> dict[str, Any]:
        provider = span.attributes.get("gen_ai.provider.name")
        model = span.attributes.get("gen_ai.response.model") or span.attributes.get("gen_ai.request.model")
        input_tokens = span.attributes.get("gen_ai.usage.input_tokens", 0)
        output_tokens = span.attributes.get("gen_ai.usage.output_tokens", 0)
        cache_tokens = span.attributes.get("gen_ai.usage.cache_read.input_tokens", 0)

        if not model or model not in self.pricing_table:
            raise KeyError(f"Pricing not defined for model '{model}' in pipeline cost table")

        rates = self.pricing_table[model]
        input_cost = (input_tokens / 1_000_000.0) * rates["input_usd_per_m"]
        output_cost = (output_tokens / 1_000_000.0) * rates["output_usd_per_m"]
        cache_cost = (cache_tokens / 1_000_000.0) * rates.get("cache_read_usd_per_m", 0.0)
        total_usd = input_cost + output_cost + cache_cost

        return {
            "provider": provider,
            "model": model,
            "total_usd": round(total_usd, 6),
            "input_usd": round(input_cost, 6),
            "output_usd": round(output_cost, 6),
            "cache_read_usd": round(cache_cost, 6),
        }
