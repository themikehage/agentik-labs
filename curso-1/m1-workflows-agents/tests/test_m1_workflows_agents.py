"""
Reference tests for Curso 1 M1 - De Workflows a Agentes.
Validates:
- RA-1.1: Classification into canonical Anthropic patterns rejecting sequential parallelism (positive & negative).
- RA-1.2: Justified agent discard citing >=2 architectural criteria (positive & negative).
- RA-1.3: Cost modeling with 95% Confidence Intervals over >=30 runs (positive & negative).
- RA-1.4: Minimal ReAct harness with independent verifiable stops (postcondition, max steps, budget).
- RA-1.5: Empirical comparison workflow vs agent demonstrating variance profile.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c1_m1_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

WorkflowPatternClassifier = _mod.WorkflowPatternClassifier
TaskSpec = _mod.TaskSpec
AgentCostDistributionModel = _mod.AgentCostDistributionModel
MinimalReActHarness = _mod.MinimalReActHarness
compare_workflow_vs_agent = _mod.compare_workflow_vs_agent


class TestRA11WorkflowPatternClassification:
    """
    RA-1.1: Clasificación de tareas en patrones canónicos de Anthropic.
    """

    def test_positive_classifies_tasks_into_canonical_anthropic_patterns(self) -> None:
        """
        [RA-1.1 POSITIVE] Confirma que tareas con diferentes características se clasifican
        en sus patrones canónicos correspondientes (prompt chaining, routing, parallel, etc.).
        """
        classifier = WorkflowPatternClassifier()

        task_chain = TaskSpec("T1", "Resumen secuencial", True, False, False, False, False)
        task_route = TaskSpec("T2", "Clasificador triaje", False, False, False, False, True)
        task_orch = TaskSpec("T3", "Coordinador peritos", False, True, False, False, False)
        task_eval = TaskSpec("T4", "Refinador con tests", True, False, False, True, False)
        task_agent = TaskSpec("T5", "Investigador abierto", False, False, True, False, False)

        assert classifier.classify_task(task_chain) == "prompt_chaining"
        assert classifier.classify_task(task_route) == "routing"
        assert classifier.classify_task(task_orch) == "orchestrator_workers"
        assert classifier.classify_task(task_eval) == "evaluator_optimizer"
        assert classifier.classify_task(task_agent) == "autonomous_agent"

    def test_negative_classifying_sequential_task_as_parallel_fails(self) -> None:
        """
        [RA-1.1 NEGATIVE] Demuestra que clasificar una tarea con dependencias causales
        secuenciales como 'parallelization' es rechazado como falacia arquitectónica.
        """
        classifier = WorkflowPatternClassifier()
        invalid_spec = {
            "task_id": "T-INVALID",
            "has_sequential_dependencies": True,
            "claimed_pattern": "parallelization",
        }

        with pytest.raises(ValueError, match="Sequential dependency violation"):
            classifier.classify_task(invalid_spec)


class TestRA12AgentDiscardMatrix:
    """
    RA-1.2: Descarte justificado de agente citando >=2 criterios objetivos.
    """

    def test_positive_justified_agent_discard_with_multiple_criteria(self) -> None:
        """
        [RA-1.2 POSITIVE] Confirma que fundamentar el descarte citando reproducibilidad
        estricta y baja latencia P95 supera la validación formal.
        """
        classifier = WorkflowPatternClassifier()
        justification = (
            "Para el cálculo actuarial de primas se requiere reproducibilidad estricta determinista "
            "y latencia P95 sub-segundo, eliminando bucles autónomos no acotados."
        )
        criteria = ["reproducibilidad_estricta", "baja_latencia_p95"]

        assert classifier.validate_agent_discard(justification, criteria) is True

    def test_negative_superficial_discard_without_objective_criteria_fails(self) -> None:
        """
        [RA-1.2 NEGATIVE] Demuestra que justificaciones simplistas ('es más simple')
        o que no alcancen 2 criterios técnicos son rechazadas.
        """
        classifier = WorkflowPatternClassifier()
        with pytest.raises(ValueError, match="Superficial discard rejected"):
            classifier.validate_agent_discard("No usamos agente porque el workflow es más simple.", ["reproducibilidad_estricta"])


class TestRA13CostModelConfidenceInterval:
    """
    RA-1.3: Modelo de costes con Intervalo de Confianza al 95% sobre simulaciones.
    """

    def test_positive_simulates_cost_distribution_with_95_percent_ci(self) -> None:
        """
        [RA-1.3 POSITIVE] Confirma que sobre >=30 corridas sembradas se obtiene
        un intervalo de confianza al 95% acotado con varianza estocástica.
        """
        model = AgentCostDistributionModel()
        summary = model.simulate_agent_costs(seed=42, num_runs=50, base_step_cost=0.005)

        assert summary["num_runs"] == 50
        assert summary["mean_cost_usd"] > 0.0
        assert summary["ci_95"][0] < summary["mean_cost_usd"] < summary["ci_95"][1]
        assert summary["variance"] > 0.0

    def test_negative_static_constant_multiplier_rejected(self) -> None:
        """
        [RA-1.3 NEGATIVE] Demuestra que reportar un multiplicador estático fijo ('15x')
        sin modelo estocástico de distribución es rechazado.
        """
        model = AgentCostDistributionModel()
        static_report = {"mean_cost_usd": 0.05, "multiplier": "15x"}  # Missing distribution and CI

        with pytest.raises(ValueError, match="Reporting a static literal multiplier"):
            model.assert_not_static_multiplier(static_report)


class TestRA14MinimalReActLoopStops:
    """
    RA-1.4: Bucle ReAct con paradas independientes y verificables.
    """

    def test_positive_react_stops_on_external_postcondition_and_budget_bounds(self) -> None:
        """
        [RA-1.4 POSITIVE] Confirma que el bucle ReAct finaliza con éxito cuando se cumple
        la postcondición externa observable, y se detiene si se agota el presupuesto.
        """
        harness = MinimalReActHarness()

        # Case 1: Postcondition met within budget
        def checker_ok(state: dict) -> bool:
            return state.get("completed_goal", False) and state.get("artifact_saved", False)

        result_success = harness.execute_loop(
            max_steps=10,
            budget_usd=0.10,
            postcondition_checker=checker_ok,
            step_cost=0.01,
        )
        assert result_success.status == "success_postcondition_met"
        assert result_success.steps_executed == 3

        # Case 2: Budget exhausted before postcondition
        def checker_never(state: dict) -> bool:
            return False

        result_budget = harness.execute_loop(
            max_steps=10,
            budget_usd=0.025,  # Only allows 2 steps at 0.01
            postcondition_checker=checker_never,
            step_cost=0.01,
        )
        assert result_budget.status == "stopped_budget_exceeded"

    def test_positive_react_stops_on_max_steps_when_infinite_loop_simulated(self) -> None:
        """
        [RA-1.4 POSITIVE] Demuestra que ante un agente sin progreso que simula bucle infinito,
        el harness corta limpiamente al alcanzar el techo de max_steps sin colgar el sistema.
        """
        harness = MinimalReActHarness()
        result_max = harness.execute_loop(
            max_steps=5,
            budget_usd=1.00,
            postcondition_checker=lambda s: False,
            step_cost=0.01,
            simulate_infinite_loop=True,
        )
        assert result_max.status == "stopped_max_steps_exceeded"
        assert result_max.steps_executed == 5


class TestRA15WorkflowVsAgentProfile:
    """
    RA-1.5: Perfil comparativo riguroso workflow vs agente.
    """

    def test_positive_comparative_variance_profile(self) -> None:
        """
        [RA-1.5 POSITIVE] Confirma que la comparación bajo idéntica metodología
        demuestra que el workflow presenta una varianza de coste y latencia significativamente menor.
        """
        # Workflow: deterministic steps -> minimal cost variance
        wf_metrics = [
            {"cost_usd": 0.010, "latency_s": 1.20},
            {"cost_usd": 0.010, "latency_s": 1.22},
            {"cost_usd": 0.010, "latency_s": 1.19},
        ]
        # Agent: stochastic multi-step exploration -> higher variance
        ag_metrics = [
            {"cost_usd": 0.035, "latency_s": 3.80},
            {"cost_usd": 0.080, "latency_s": 7.40},
            {"cost_usd": 0.020, "latency_s": 2.10},
        ]

        comparison = compare_workflow_vs_agent(wf_metrics, ag_metrics)
        assert comparison["workflow"]["cost_variance"] < comparison["agent"]["cost_variance"]
        assert comparison["variance_ratio_agent_to_wf"] > 1.0
