"""
Reference tests for Curso 3 M5 - Guardrails y SLOs.
Validates:
- RA-5.1: Colang / Guardrails latency budget differentiation by rail type (positive & negative).
- RA-5.2: Empirical evaluation with TPR, FPR and Wilson Confidence Intervals (positive & negative).
- RA-5.3: Strict separation between SLI, SLO, SLA and error budget policies (positive & negative).
- RA-5.4: Acceptance gate enforcement blocking deployment on regression breaks (positive & negative).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c3_m5_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

GuardrailsConfigValidator = _mod.GuardrailsConfigValidator
GuardrailEvaluator = _mod.GuardrailEvaluator
SloSpecValidator = _mod.SloSpecValidator
AcceptanceGate = _mod.AcceptanceGate
RegressionBreachError = _mod.RegressionBreachError


class TestRA51RailConfigurationAndLatencyBudgets:
    """
    RA-5.1: Configuración de rails con presupuesto de latencia diferenciado por tipo.
    """

    def test_positive_differentiated_latency_budgets_for_deterministic_and_self_check(self) -> None:
        """
        [RA-5.1 POSITIVE] Confirma que la configuración asigna presupuestos realistas:
        milisegundos para comprobaciones deterministas y cientos de ms para self-check LLM.
        """
        validator = GuardrailsConfigValidator()
        valid_config = {
            "input_rails": ["keyword_jailbreak_filter", "self_check_input_safety"],
            "output_rails": ["regex_pii_filter", "self_check_hallucination"],
            "budgets": [
                {
                    "rail_name": "keyword_jailbreak_filter",
                    "rail_type": "deterministic",
                    "latency_budget_ms": 10.0,
                },
                {
                    "rail_name": "self_check_input_safety",
                    "rail_type": "self_check_llm",
                    "latency_budget_ms": 350.0,
                },
            ],
        }

        res = validator.validate_rails_configuration(valid_config)
        assert res["status"] == "valid"
        assert res["input_rails_count"] == 2

    def test_negative_allocating_under_15ms_to_self_check_llm_fails(self) -> None:
        """
        [RA-5.1 NEGATIVE] Demuestra que asignar presupuestos irrealistas (<15ms)
        a rails que invocan un LLM evaluador (self-check) es rechazado.
        """
        validator = GuardrailsConfigValidator()
        unrealistic_config = {
            "input_rails": ["self_check_intent"],
            "output_rails": ["self_check_hallucination"],
            "budgets": [
                {
                    "rail_name": "regex_filter",
                    "rail_type": "deterministic",
                    "latency_budget_ms": 5.0,
                },
                {
                    "rail_name": "self_check_intent",
                    "rail_type": "self_check_llm",
                    "latency_budget_ms": 12.0,  # Falaz: self-check en 12ms!
                },
            ],
        }

        with pytest.raises(ValueError, match="Self-check rails invoke LLM inference and require at least 150-500ms"):
            validator.validate_rails_configuration(unrealistic_config)


class TestRA52EmpiricalEvaluationWithConfidenceIntervals:
    """
    RA-5.2: Evaluación empírica con TPR, FPR e Intervalo de Confianza del 95%.
    """

    def test_positive_evaluates_tpr_and_fpr_with_wilson_ci(self) -> None:
        """
        [RA-5.2 POSITIVE] Confirma que la evaluación sobre dataset adversarial
        reporta TPR y FPR con intervalos de confianza acotados matemáticamente.
        """
        evaluator = GuardrailEvaluator()
        adversarial_dataset = [
            {"id": "adv-1", "is_adversarial": True},
            {"id": "adv-2", "is_adversarial": True},
            {"id": "adv-3", "is_adversarial": True},
            {"id": "ben-1", "is_adversarial": False},
            {"id": "ben-2", "is_adversarial": False},
        ]
        predictions = [
            {"id": "adv-1", "is_blocked": True},
            {"id": "adv-2", "is_blocked": True},
            {"id": "adv-3", "is_blocked": False},  # False negative
            {"id": "ben-1", "is_blocked": False},
            {"id": "ben-2", "is_blocked": False},
        ]

        metrics = evaluator.evaluate_adversarial_dataset(adversarial_dataset, predictions)
        assert metrics["TPR"].rate == 0.6667
        assert metrics["TPR"].ci_lower > 0.0
        assert metrics["TPR"].ci_upper <= 1.0
        assert metrics["FPR"].rate == 0.0

    def test_negative_claiming_100_percent_jailbreak_blocking_fails(self) -> None:
        """
        [RA-5.2 NEGATIVE] Demuestra que prometer '100% de bloqueo de jailbreaks'
        es rechazado como afirmación estadísticamente inconsistente.
        """
        evaluator = GuardrailEvaluator()
        with pytest.raises(ValueError, match="Promising 100% jailbreak blocking is factually impossible"):
            evaluator.validate_claims(["Nuestra suite de Guardrails garantiza bloqueo del 100% de ataques."])


class TestRA53SloSpecificationSeparation:
    """
    RA-5.3: Especificación de SLOs separando SLI, SLO y SLA con política de error budget.
    """

    def test_positive_valid_slo_separating_sli_slo_sla_and_error_budget(self) -> None:
        """
        [RA-5.3 POSITIVE] Confirma que una especificación SRE válida establece
        SLO interno agresivo (99.5%), SLA contractual conservador (99.0%) y error budget.
        """
        validator = SloSpecValidator()
        valid_spec = {
            "sli": {
                "name": "inference_availability_ratio",
                "metric_expression": "successful_responses / total_valid_requests",
            },
            "slo": {
                "target_threshold": 0.995,  # 99.5% internal target
                "window_days": 30,
            },
            "sla": {
                "contractual_commitment": 0.990,  # 99.0% contractual commitment
                "penalty_clauses": ["10% de compensacion en factura si disponibilidad < 99.0%"],
            },
            "error_budget_policy": {
                "action_on_exhaustion": "freeze_non_critical_deployments",
            },
        }

        res = validator.validate_specification(valid_spec)
        assert res["status"] == "valid"
        assert res["slo_target"] == 0.995
        assert res["sla_target"] == 0.990
        assert res["error_budget_percentage"] == 0.5

    def test_negative_sla_higher_or_equal_to_slo_fails(self) -> None:
        """
        [RA-5.3 NEGATIVE] Demuestra que fijar un SLA contractual igual o más agresivo
        que el SLO interno es detectado como violación de principios SRE.
        """
        validator = SloSpecValidator()
        inverted_spec = {
            "sli": {"name": "avail", "metric_expression": "ok / total"},
            "slo": {"target_threshold": 0.990},
            "sla": {
                "contractual_commitment": 0.995,  # Error: SLA > SLO
                "penalty_clauses": ["Multa"],
            },
            "error_budget_policy": {"action_on_exhaustion": "freeze"},
        }

        with pytest.raises(ValueError, match="SLA commitment .* cannot be greater than or equal to internal SLO"):
            validator.validate_specification(inverted_spec)


class TestRA54AcceptanceGateRegressionEnforcement:
    """
    RA-5.4: Acceptance gate contra golden set bloqueando regresiones previas.
    """

    def test_positive_golden_set_passing_and_regressions_clean_approves(self) -> None:
        """
        [RA-5.4 POSITIVE] Confirma que el gate aprueba despliegue cuando el golden set
        supera el umbral y todas las regression evals históricas pasan limpias.
        """
        gate = AcceptanceGate()
        regressions = [
            {"case_name": "eval_fecha_bisiesto_siniestro", "passed": True},
            {"case_name": "eval_poliza_nif_con_guion", "passed": True},
        ]

        result = gate.evaluate_gate(
            golden_set_score=0.965,
            min_threshold=0.920,
            regression_evals=regressions,
        )
        assert result["gate_status"] == "APPROVED"
        assert result["regressions_clean"] is True

    def test_negative_gate_blocks_if_historical_regression_breaks(self) -> None:
        """
        [RA-5.4 NEGATIVE] Demuestra que el gate bloquea el pase a producción si
        alguna regression eval histórica falla, aun cuando el golden set promedio sea alto.
        """
        gate = AcceptanceGate()
        regressions_with_break = [
            {"case_name": "eval_fecha_bisiesto_siniestro", "passed": True},
            {"case_name": "eval_poliza_nif_con_guion", "passed": False},  # Regresión rota
        ]

        with pytest.raises(RegressionBreachError, match="Acceptance Gate BLOCKED"):
            gate.evaluate_gate(
                golden_set_score=0.950,
                min_threshold=0.920,
                regression_evals=regressions_with_break,
            )
