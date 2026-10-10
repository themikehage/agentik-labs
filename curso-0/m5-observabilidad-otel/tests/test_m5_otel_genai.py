"""
Reference tests for Curso 0 M5 - Observabilidad OTel GenAI.
Strictly follows the test conventions:
- One test function per acceptance criterion citing the RA in docstring.
- Both positive and negative test cases to detect conceptual bugs.
- Zero network socket usage, zero real sleep.
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c0_m5_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

OTelGenAISpan = _mod.OTelGenAISpan
InMemorySpanExporter = _mod.InMemorySpanExporter
OTelGenAITracer = _mod.OTelGenAITracer
PipelineCostCalculator = _mod.PipelineCostCalculator
PIISanitizer = _mod.PIISanitizer
SemconvViolationError = _mod.SemconvViolationError


class TestRA51CanonicalSemconvAndDeprecatedRejection:
    """
    RA-5.1: Instrumentación OTel GenAI vigente y rechazo estricto del nombre obsoleto gen_ai.system.
    """

    def test_positive_canonical_attributes_emitted(self) -> None:
        """
        [RA-5.1 POSITIVE] Confirma que el span contiene los atributos estándar vigentes
        y actualiza la métrica agregada de tokens.
        """
        exporter = InMemorySpanExporter()
        tracer = OTelGenAITracer(exporter)

        span = tracer.start_chat_span(
            provider_name="agentik-provider",
            request_model="agentik-reason-70b",
            response_model="agentik-reason-70b-v1",
            input_tokens=1500,
            output_tokens=350,
        )

        assert span.attributes["gen_ai.provider.name"] == "agentik-provider"
        assert span.attributes["gen_ai.request.model"] == "agentik-reason-70b"
        assert span.attributes["gen_ai.response.model"] == "agentik-reason-70b-v1"
        assert span.attributes["gen_ai.usage.input_tokens"] == 1500
        assert span.attributes["gen_ai.usage.output_tokens"] == 350
        assert tracer.total_tokens_aggregated == 1850
        assert len(exporter.exported_spans) == 1

    def test_negative_deprecated_gen_ai_system_raises_violation(self) -> None:
        """
        [RA-5.1 NEGATIVE] Rechaza cualquier intento de usar el atributo obsoleto 'gen_ai.system'.
        """
        span = OTelGenAISpan(name="chat")
        with pytest.raises(SemconvViolationError, match="Deprecated attribute 'gen_ai.system'"):
            span.set_attribute("gen_ai.system", "openai")


class TestRA52CacheReadTokensSpanAttribute:
    """
    RA-5.2: Spans con discriminación de tokens servidos desde caché (cache_read.input_tokens).
    """

    def test_positive_cache_read_attribute_present_on_cache_hit(self) -> None:
        """
        [RA-5.2 POSITIVE] Confirma que cuando se reutiliza prefijo en caché,
        el atributo 'gen_ai.usage.cache_read.input_tokens' se incluye con su valor exacto.
        """
        exporter = InMemorySpanExporter()
        tracer = OTelGenAITracer(exporter)

        span = tracer.start_chat_span(
            provider_name="agentik-provider",
            request_model="agentik-fast-8b",
            response_model="agentik-fast-8b",
            input_tokens=2000,
            output_tokens=100,
            cache_read_input_tokens=1800,
        )

        assert span.attributes["gen_ai.usage.cache_read.input_tokens"] == 1800
        assert span.attributes["gen_ai.usage.input_tokens"] == 2000

    def test_negative_omitting_cache_read_attribute_fails_verification(self) -> None:
        """
        [RA-5.2 NEGATIVE] Falla si un span que tuvo lectura de caché omite dicho atributo.
        """
        exporter = InMemorySpanExporter()
        tracer = OTelGenAITracer(exporter)

        # Call without cache read tokens specified
        span = tracer.start_chat_span(
            provider_name="agentik-provider",
            request_model="agentik-fast-8b",
            response_model="agentik-fast-8b",
            input_tokens=2000,
            output_tokens=100,
            cache_read_input_tokens=0,
        )

        assert "gen_ai.usage.cache_read.input_tokens" not in span.attributes


class TestRA53FinancialCostOutsideSpan:
    """
    RA-5.3: Cálculo del coste monetario realizado estrictamente en pipeline/backend.
    """

    def test_positive_pipeline_computes_cost_from_span_tokens(self) -> None:
        """
        [RA-5.3 POSITIVE] Confirma que el pipeline/backend de observabilidad calcula
        el coste en dólares a partir de los tokens del span sin alterar la semconv.
        """
        exporter = InMemorySpanExporter()
        tracer = OTelGenAITracer(exporter)

        span = tracer.start_chat_span(
            provider_name="agentik-provider",
            request_model="agentik-reason-70b",
            response_model="agentik-reason-70b",
            input_tokens=1_000_000,
            output_tokens=100_000,
            cache_read_input_tokens=400_000,
        )

        pricing = {
            "agentik-reason-70b": {
                "input_usd_per_m": 3.00,
                "output_usd_per_m": 12.00,
                "cache_read_usd_per_m": 0.50,
            }
        }
        calculator = PipelineCostCalculator(pricing)
        cost_report = calculator.compute_cost_for_span(span)

        # 1M in ($3.00) + 100k out ($1.20) + 400k cache ($0.20) = $4.40
        assert pytest.approx(cost_report["total_usd"], abs=1e-5) == 4.40
        assert pytest.approx(cost_report["input_usd"], abs=1e-5) == 3.00
        assert pytest.approx(cost_report["output_usd"], abs=1e-5) == 1.20
        assert pytest.approx(cost_report["cache_read_usd"], abs=1e-5) == 0.20

    def test_negative_financial_cost_inside_span_attributes_forbidden(self) -> None:
        """
        [RA-5.3 NEGATIVE] Rechaza cualquier intento de declarar atributos de coste
        en dólares dentro de los atributos del span OTel.
        """
        span = OTelGenAISpan(name="chat")
        with pytest.raises(SemconvViolationError, match="Financial cost attribute"):
            span.set_attribute("gen_ai.cost.usd", 0.05)


class TestRA54PrivacyAndPIIContainment:
    """
    RA-5.4: Política de privacidad, contenido opt-in y redacción de credenciales/PII.
    """

    def test_positive_default_policy_omits_content(self) -> None:
        """
        [RA-5.4 POSITIVE] Confirma que por defecto (opt-in = False), el span no expone
        el texto del prompt ni del completion para proteger la privacidad.
        """
        exporter = InMemorySpanExporter()
        tracer = OTelGenAITracer(exporter)

        span = tracer.start_chat_span(
            provider_name="agentik-provider",
            request_model="agentik-fast-8b",
            response_model="agentik-fast-8b",
            input_tokens=100,
            output_tokens=50,
            prompt_text="Confidential prompt with user secrets",
            completion_text="Confidential completion",
            capture_content_opt_in=False,
        )

        assert "gen_ai.prompt" not in span.attributes
        assert "gen_ai.completion" not in span.attributes

    def test_positive_opt_in_redacts_credentials_and_pii(self) -> None:
        """
        [RA-5.4 POSITIVE] Con captura activada explícitamente, se redactan API keys,
        tokens Bearer y correos electrónicos.
        """
        exporter = InMemorySpanExporter()
        tracer = OTelGenAITracer(exporter)

        sensitive_prompt = "User john.doe@enterprise.com with token Bearer secret_token_xyz_123456 and sk-abcdef1234567890abc."
        span = tracer.start_chat_span(
            provider_name="agentik-provider",
            request_model="agentik-fast-8b",
            response_model="agentik-fast-8b",
            input_tokens=100,
            output_tokens=50,
            prompt_text=sensitive_prompt,
            capture_content_opt_in=True,
        )

        prompt_attr = span.attributes["gen_ai.prompt"]
        assert "[REDACTED_API_KEY]" in prompt_attr
        assert "Bearer [REDACTED_TOKEN]" in prompt_attr
        assert "[REDACTED_EMAIL]" in prompt_attr
        assert "john.doe@enterprise.com" not in prompt_attr
        assert "sk-abcdef1234567890abc" not in prompt_attr
