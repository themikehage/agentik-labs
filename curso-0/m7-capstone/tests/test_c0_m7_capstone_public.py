"""
Public tests for Curso 0 M7 - Capstone: Microservicio de Inferencia Enterprise.
Validates:
- Streaming SSE with VirtualClock, TTFT and ITL P50/P95, cache-friendly prefix hash (RA-7.1)
- Three-layer validation with independent semantic business rejection (RA-7.2)
- OpenTelemetry GenAI semconv with decoupled pipeline cost (RA-7.3)
- Sandboxed tools with zero network and human-in-the-loop confirmation (RA-7.4)
- Evals with 95% bootstrap CI lower bound threshold approval (RA-7.5)
- DESIGN.md architectural decisions and SLO budgets schema validation (RA-7.6)
"""

from __future__ import annotations

import json
import sys
import importlib.util
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c0_m7_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

EnterpriseInferenceService = _mod.EnterpriseInferenceService
validate_design_document = _mod.validate_design_document
EnterpriseServiceError = _mod.EnterpriseServiceError
from labkit.clock import VirtualClock


class TestRA71StreamingAndCacheFriendlyPrefix:
    """
    RA-7.1: Streaming SSE con reloj inyectable y prefijo estable cache-friendly.
    """

    def test_positive_streaming_metrics_and_stable_prefix_hash(self) -> None:
        """
        [RA-7.1 POSITIVE] Confirma que la inferencia streaming mide TTFT y percentiles ITL,
        y que dos llamadas con idéntico prefijo de sistema y distintos inputs de usuario
        producen exactamente el mismo hash de prefijo.
        """
        clock = VirtualClock(initial_time=0.0)
        svc = EnterpriseInferenceService(clock=clock)

        static_sys = ["Enterprise system prompt v1", "Output schema rules"]
        few_shots = [{"in": "1", "out": "one"}]

        res1 = svc.stream_inference("tenant-a", static_sys, few_shots, "user query 1")
        res2 = svc.stream_inference("tenant-a", static_sys, few_shots, "user query 2")

        # Stable prefix produces byte-exact matching hash
        assert res1["prefix_hash"] == res2["prefix_hash"]
        assert len(res1["prefix_hash"]) == 64

        # Profile verifies TTFT and ITL
        prof = res1["profile"]
        assert prof.ttft_seconds <= 0.50
        assert prof.itl_p50_seconds <= 0.04
        assert prof.itl_p95_seconds <= 0.05
        assert prof.token_count > 0

    def test_positive_prompt_cache_hit_reduces_ttft(self) -> None:
        """
        [RA-7.1 POSITIVE] Confirma que una llamada con cache hit reduce drásticamente el TTFT.
        """
        clock = VirtualClock(initial_time=0.0)
        svc = EnterpriseInferenceService(clock=clock)

        cold_res = svc.stream_inference("tenant-a", ["System prompt"], [], "Query", is_cache_hit=False)
        cached_res = svc.stream_inference("tenant-a", ["System prompt"], [], "Query", is_cache_hit=True)

        assert cached_res["profile"].ttft_seconds < cold_res["profile"].ttft_seconds


class TestRA72ThreeLayerBusinessValidation:
    """
    RA-7.2: Validación en tres capas con rechazo semántico de negocio independiente.
    """

    def test_positive_valid_business_transaction_passes(self) -> None:
        """
        [RA-7.2 POSITIVE] Aprueba un payload válido en sintaxis, esquema y regla de negocio.
        """
        svc = EnterpriseInferenceService()
        valid_json = json.dumps({"action": "refund", "amount_cents": 2500})
        res = svc.validate_business_output(valid_json)
        assert res["is_valid"] is True
        assert res["layer_failed"] is None

    def test_negative_schema_valid_but_negative_amount_fails_business_rule(self) -> None:
        """
        [RA-7.2 NEGATIVE] Demuestra que un importe negativo (válido como entero en esquema)
        es rechazado por la capa de semántica de negocio.
        """
        svc = EnterpriseInferenceService()
        invalid_json = json.dumps({"action": "refund", "amount_cents": -500})
        res = svc.validate_business_output(invalid_json)
        assert res["is_valid"] is False
        assert res["layer_failed"] == "business_semantic"


class TestRA73OTelSemconvAndPipelineCost:
    """
    RA-7.3: Spans OTel conformes con coste calculado estrictamente en el pipeline.
    """

    def test_positive_span_conformance_and_pipeline_cost(self) -> None:
        """
        [RA-7.3 POSITIVE] Confirma atributos OTel vigentes y cálculo de coste desacoplado.
        """
        svc = EnterpriseInferenceService()
        res = svc.stream_inference("tenant-1", ["System"], [], "Hello", is_cache_hit=True)

        span = res["span"]
        assert span.attributes["gen_ai.provider.name"] == "agentik-enterprise"
        assert "gen_ai.request.model" in span.attributes
        assert span.attributes["gen_ai.usage.cache_read.input_tokens"] > 0

        # Cost is returned in response by the pipeline, not inside span attributes
        assert res["cost_usd"] > 0.0
        assert not any("cost" in k.lower() or "usd" in k.lower() for k in span.attributes)

    def test_negative_deprecated_attribute_in_span_rejected(self) -> None:
        """
        [RA-7.3 NEGATIVE] Rechaza inclusión de 'gen_ai.system' o coste en dólares en el span.
        """
        svc = EnterpriseInferenceService()
        span = svc.stream_inference("tenant-1", ["System"], [], "Hello")["span"]
        with pytest.raises(ValueError, match="Deprecated 'gen_ai.system'"):
            span.set_attribute("gen_ai.system", "openai")


class TestRA74ToolSandboxAndHumanApproval:
    """
    RA-7.4: Contención en HardenedSandbox y confirmación humana en acciones destructivas.
    """

    def test_positive_unconfirmed_irreversible_action_requires_approval(self) -> None:
        """
        [RA-7.4 POSITIVE] Bloquea una acción irreversible devolviendo APPROVAL_REQUIRED.
        """
        svc = EnterpriseInferenceService()
        res = svc.execute_sandboxed_tool(
            tool_name="delete_production_database",
            arguments={"db": "prod-master"},
            requires_human_confirmation=True,
            is_confirmed_by_human=False,
        )
        assert res["status"] == "APPROVAL_REQUIRED"
        assert res["is_error"] is True

    def test_positive_confirmed_action_executes_under_hardened_flags(self) -> None:
        """
        [RA-7.4 POSITIVE] Con confirmación humana y flags hardened, la tool se ejecuta.
        """
        svc = EnterpriseInferenceService()
        res = svc.execute_sandboxed_tool(
            tool_name="delete_production_database",
            arguments={"db": "prod-master"},
            requires_human_confirmation=True,
            is_confirmed_by_human=True,
            container_flags={"network": "none", "read_only": True, "cap_drop": ["ALL"], "user": "10001:10001"},
        )
        assert res["status"] == "EXECUTED"
        assert res["is_error"] is False

    def test_negative_tool_with_network_access_raises_security_violation(self) -> None:
        """
        [RA-7.4 NEGATIVE] Rechaza ejecución de herramientas si el contenedor tiene red habilitada.
        """
        svc = EnterpriseInferenceService()
        with pytest.raises(EnterpriseServiceError, match="tool executed with open network"):
            svc.execute_sandboxed_tool(
                tool_name="web_fetch",
                arguments={"url": "http://evil.com"},
                container_flags={"network": "bridge", "user": "10001:10001"},
            )


class TestRA75EvaluationBootstrapReliability:
    """
    RA-7.5: Evals con IC bootstrap al 95% evaluados por el límite inferior.
    """

    def test_positive_high_consistency_passes_by_ci_lower_bound(self) -> None:
        """
        [RA-7.5 POSITIVE] Aprueba cuando el límite inferior del IC al 95% supera el umbral (0.75).
        """
        svc = EnterpriseInferenceService()
        scores = [0.85] * 25 + [0.80] * 5
        report = svc.evaluate_reliability_ci(scores, threshold_ci_lower=0.75)
        assert report["passed"] is True
        assert report["ci_lower_95"] >= 0.75

    def test_negative_high_mean_with_low_ci_lower_bound_fails(self) -> None:
        """
        [RA-7.5 NEGATIVE] Suspende un sistema que tiene media aparente de 0.80 pero
        cuya varianza hace que el límite inferior del IC caiga por debajo de 0.75.
        """
        svc = EnterpriseInferenceService()
        scores = [1.0, 0.4, 1.0, 0.5, 0.9, 0.6, 1.0, 0.5, 0.9, 0.4] * 3
        report = svc.evaluate_reliability_ci(scores, threshold_ci_lower=0.75)
        assert report["mean_score"] >= 0.70
        assert report["ci_lower_95"] < 0.75
        assert report["passed"] is False


class TestRA76DesignDocumentValidation:
    """
    RA-7.6: Documento DESIGN.md validado por esquema con decisiones y presupuestos SLO.
    """

    def test_positive_design_document_conforms_to_schema(self) -> None:
        """
        [RA-7.6 POSITIVE] Confirma que DESIGN.md contiene las cinco secciones obligatorias
        y presupuestos explícitos de TTFT, ITL y bootstrap.
        """
        design_path = Path(__file__).resolve().parent.parent / "DESIGN.md"
        assert design_path.exists()
        content = design_path.read_text(encoding="utf-8")

        result = validate_design_document(content)
        assert result["is_valid"] is True
        assert result["declared_budgets_present"] is True
        assert len(result["missing_sections"]) == 0
