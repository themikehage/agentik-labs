"""
Reference tests for Curso 3 M2 - Criterio de Solución, Buy vs Build y TCO.
Validates:
- RA-2.1: Solution classification discarding alternatives with cited failure modes (positive & negative).
- RA-2.2: Identifying exclusive RAG failure modes and rejecting hallucination elimination claims (positive & negative).
- RA-2.3: MADR 3.x ADR schema validation enforcing positive and negative consequences (positive & negative).
- RA-2.4: Unit TCO cost modeling with strictly monotonic sensitivity verification (positive & negative).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c3_m2_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

SolutionEvaluator = _mod.SolutionEvaluator
SolutionDecision = _mod.SolutionDecision
DiscardedOption = _mod.DiscardedOption
RagFailureModeAnalyzer = _mod.RagFailureModeAnalyzer
RagFailureMode = _mod.RagFailureMode
MadrAdrValidator = _mod.MadrAdrValidator
TcoCostModel = _mod.TcoCostModel


class TestRA21SolutionClassification:
    """
    RA-2.1: Clasificación de solución descartando opciones con modos de fallo citados.
    """

    def test_positive_decision_with_discarded_failure_modes(self) -> None:
        """
        [RA-2.1 POSITIVE] Confirma que una decisión de arquitectura fundamentada
        descarta explícitamente opciones alternativas con sus modos de fallo reales.
        """
        evaluator = SolutionEvaluator()
        decision = SolutionDecision(
            chosen_pattern="RAG Híbrido con Verificación de Citas",
            justification="El conocimiento normativo cambia semanalmente y exige trazabilidad documental a nivel de párrafo.",
            discarded_options=[
                DiscardedOption(
                    name="Fine-Tuning de Modelo Base",
                    failure_mode="Obsolescencia acelerada del conocimiento congelado en pesos y opacidad total en auditoría de fuentes.",
                ),
                DiscardedOption(
                    name="Long-Context sin Caching",
                    failure_mode="Explosión lineal de latencia P95 y costes inasumibles ante documentos de más de 100k tokens.",
                ),
            ],
        )

        assert evaluator.evaluate_decision(decision) is True

    def test_negative_decision_without_discarded_failure_modes_fails(self) -> None:
        """
        [RA-2.1 NEGATIVE] Demuestra que una justificación unidireccional que solo habla
        de las bondades de la opción elegida sin analizar modos de fallo descartados falla.
        """
        evaluator = SolutionEvaluator()
        one_sided_decision = SolutionDecision(
            chosen_pattern="RAG",
            justification="Elegimos RAG porque es moderno, rápido y nos gusta la arquitectura.",
            discarded_options=[],
        )

        with pytest.raises(ValueError, match="cite failure modes of discarded options"):
            evaluator.evaluate_decision(one_sided_decision)


class TestRA22RagFailureModesAndMitigations:
    """
    RA-2.2: Identificación de modos de fallo exclusivos de RAG y mitigaciones correspondientes.
    """

    def test_positive_identifies_multiple_exclusive_rag_failure_modes(self) -> None:
        """
        [RA-2.2 POSITIVE] Confirma identificación rigurosa de al menos dos modos de fallo
        intrínsecos del RAG (retrieval erróneo, conflicto documental, citación espuria).
        """
        analyzer = RagFailureModeAnalyzer()
        modes = [
            RagFailureMode(
                name="retrieval_error",
                description="El paso de búsqueda semántica recupera fragmentos irrelevantes por proximidad léxica engañosa.",
                mitigation="Incorporar reranker contextual y filtrado híbrido con búsqueda BM25 densa y dispersa.",
            ),
            RagFailureMode(
                name="source_conflict",
                description="Dos pólizas vigentes contienen cláusulas contradictorias sobre el mismo ámbito de cobertura.",
                mitigation="Algoritmo de resolución temporal con metadatos de vigencia y precedencia legal explícita.",
            ),
        ]

        result = analyzer.analyze_failure_modes(modes)
        assert result["status"] == "valid"
        assert result["mode_count"] == 2

    def test_negative_claiming_rag_eliminates_hallucinations_fails(self) -> None:
        """
        [RA-2.2 NEGATIVE] Demuestra que propagar el mito de que 'RAG elimina las alucinaciones'
        es detectado y bloqueado como falsedad técnica.
        """
        analyzer = RagFailureModeAnalyzer()
        fallacious_claims = [
            "Con nuestra arquitectura RAG logramos cero alucinaciones en respuestas a clientes."
        ]

        with pytest.raises(ValueError, match="Asserting that RAG eliminates or prevents hallucinations is a fundamental misconception"):
            analyzer.validate_rag_claims(fallacious_claims)


class TestRA23MadrAdrSchema:
    """
    RA-2.3: Validación de adr.md contra esquema MADR (incluyendo consecuencias negativas).
    """

    def test_positive_valid_madr_document_with_positive_and_negative_consequences(self) -> None:
        """
        [RA-2.3 POSITIVE] Confirma que un ADR en formato MADR 3.x con todas sus secciones
        y consecuencias positivas y negativas balanceadas pasa la validación formal.
        """
        validator = MadrAdrValidator()
        adr_doc = {
            "titulo": "ADR-003: Adopción de LiteLLM Proxy como Gateway Enterprise",
            "estado": "aceptado",
            "contexto": "Múltiples unidades de negocio acceden a proveedores LLM sin control de costes ni cuotas.",
            "decision": "Desplegar LiteLLM Proxy con persistencia Postgres para control presupuestario por virtual keys.",
            "opciones_consideradas": [
                {
                    "opcion": "LiteLLM Proxy",
                    "pros": ["Soporta presupuestos duros", "Compatible OpenAI API"],
                    "contras": ["Requiere gestión de infraestructura Postgres"],
                },
                {
                    "opcion": "Acceso directo con SDKs dispersos",
                    "pros": ["Cero infraestructura intermediaria"],
                    "contras": ["Imposible auditar gasto ni aplicar virtual keys centralizadas"],
                },
            ],
            "consecuencias": {
                "positivas": [
                    "Presupuestos duros garantizan techo de gasto mensual por tenant.",
                    "Atribución unificada de tokens y costes en una sola tabla SQL.",
                ],
                "negativas": [
                    "Añade un salto adicional de latencia de red de ~10ms en el camino crítico.",
                    "Requiere alta disponibilidad y mantenimiento de base de datos relacional.",
                ],
            },
        }

        res = validator.validate_schema(adr_doc)
        assert res["estado"] == "aceptado"
        assert len(res["consecuencias"]["negativas"]) >= 1

    def test_negative_omitting_negative_consequences_fails(self) -> None:
        """
        [RA-2.3 NEGATIVE] Demuestra que omitir consecuencias negativas en un ADR
        es rechazado por incumplimiento del esquema MADR.
        """
        validator = MadrAdrValidator()
        one_sided_adr = {
            "titulo": "ADR-004: Solución Mágica",
            "estado": "aceptado",
            "contexto": "Contexto",
            "decision": "Decisión",
            "opciones_consideradas": [{"opcion": "A"}, {"opcion": "B"}],
            "consecuencias": {
                "positivas": ["Todo es perfecto y sin desventajas."],
                "negativas": [],  # Omisión de compensaciones negativas
            },
        }

        with pytest.raises(ValueError, match="strictly requires negative consequences"):
            validator.validate_schema(one_sided_adr)


class TestRA24TcoCostModel:
    """
    RA-2.4: Modelado unitario de TCO y verificación de sensibilidad monótona.
    """

    def test_positive_monotonic_sensitivity_across_token_scales(self) -> None:
        """
        [RA-2.4 POSITIVE] Confirma que el modelo calcula costes unitarios por consulta
        y exhibe sensibilidad monótona ante el aumento de tokens y volumen.
        """
        model = TcoCostModel(
            input_cost_per_m=2.5,
            output_cost_per_m=10.0,
            vector_query_cost_usd=0.001,
            rerank_cost_usd=0.0005,
            infra_monthly_usd=400.0,
            expected_monthly_queries=50_000,
        )

        cost_1k = model.calculate_cost_per_query(input_tokens=1000, output_tokens=300)
        cost_4k = model.calculate_cost_per_query(input_tokens=4000, output_tokens=300)
        assert cost_4k > cost_1k

        # Monotonicity test over scaling ranges
        token_scales = [1000, 2000, 5000, 10000]
        assert model.assert_monotonic_sensitivity("input_tokens", token_scales) is True

        # Scale economies test
        query_volumes = [10_000, 50_000, 200_000]
        assert model.assert_monotonic_sensitivity("expected_monthly_queries", query_volumes) is True

    def test_negative_static_hardcoded_model_fails_sensitivity_check(self) -> None:
        """
        [RA-2.4 NEGATIVE] Demuestra que un modelo ficticio o estático que devuelve cifras
        planas sin sensibilidad real es detectado y rechazado.
        """
        class DummyStaticModel(TcoCostModel):
            def calculate_cost_per_query(self, *args, **kwargs) -> float:
                return 0.050000  # Hardcoded flat cost

        dummy = DummyStaticModel()
        with pytest.raises(ValueError, match="strictly monotonic"):
            dummy.assert_monotonic_sensitivity("input_tokens", [1000, 5000, 10000])
