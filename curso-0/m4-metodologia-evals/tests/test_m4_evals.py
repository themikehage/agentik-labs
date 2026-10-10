"""
Reference tests for Curso 0 M4 - Metodología de Evals.
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
_spec = importlib.util.spec_from_file_location("c0_m4_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

EvalTask = _mod.EvalTask
EvaluationDataset = _mod.EvaluationDataset
OutcomeGrader = _mod.OutcomeGrader
UnbiasedPassMetrics = _mod.UnbiasedPassMetrics
BootstrapPairedComparator = _mod.BootstrapPairedComparator


class TestRA41EvaluationDatasetBalance:
    """
    RA-4.1: Dataset de evaluación con 20-50 tareas con balance capability/regression declarado.
    """

    def test_positive_balanced_dataset_accepted(self) -> None:
        """
        [RA-4.1 POSITIVE] Valida un dataset de 30 tareas con 15 de capability y 15 de regression.
        """
        tasks = []
        for i in range(15):
            tasks.append(
                EvalTask(
                    task_id=f"cap-{i}",
                    prompt=f"Perform capability task {i}",
                    category="capability",
                    expected_outcome={"status": "completed", "id": i},
                )
            )
        for i in range(15):
            tasks.append(
                EvalTask(
                    task_id=f"reg-{i}",
                    prompt=f"Perform regression task {i}",
                    category="regression",
                    expected_outcome={"status": "verified", "id": i},
                )
            )

        dataset = EvaluationDataset(tasks)
        assert len(dataset.tasks) == 30
        assert dataset.capability_count == 15
        assert dataset.regression_count == 15

    def test_negative_tiny_or_unbalanced_dataset_rejected(self) -> None:
        """
        [RA-4.1 NEGATIVE] Rechaza datasets de menos de 20 tareas o desbalanceados (> 65% de una categoría).
        """
        # Case 1: Only 5 tasks (< 20)
        tiny_tasks = [
            EvalTask(f"t-{i}", "prompt", "capability", {}) for i in range(5)
        ]
        with pytest.raises(ValueError, match="between 20 and 50 tasks"):
            EvaluationDataset(tiny_tasks)

        # Case 2: 25 tasks but 23 capability and only 2 regression (unbalanced)
        unbalanced_tasks = [
            EvalTask(f"t-{i}", "prompt", "capability", {}) for i in range(23)
        ] + [
            EvalTask(f"reg-{i}", "prompt", "regression", {}) for i in range(2)
        ]
        with pytest.raises(ValueError, match="balanced between capability and regression"):
            EvaluationDataset(unbalanced_tasks)


class TestRA42OutcomeGraderVsTranscriptFraud:
    """
    RA-4.2: Grader de outcome observable que suspende fraudes de transcript.
    """

    def test_positive_real_outcome_passes(self) -> None:
        """
        [RA-4.2 POSITIVE] Aprueba al agente cuando el estado real de la infraestructura
        coincide con el resultado esperado.
        """
        transcript = "I have provisioned the database replica and synced tables."
        actual_env = {"replica_status": "synced", "lag_ms": 12}
        expected = {"replica_status": "synced", "lag_ms": 12}

        grade = OutcomeGrader.grade(transcript, actual_env, expected)
        assert grade["passed"] is True
        assert grade["outcome_matches"] is True
        assert grade["simulation_only"] is False

    def test_negative_transcript_fraud_caught_and_failed(self) -> None:
        """
        [RA-4.2 NEGATIVE] Suspende al sistema que simula en texto haber completado
        la acción pero deja el entorno sin mutar.
        """
        fraudulent_transcript = (
            "Task completed successfully! Created deployment manifest at /k8s/deploy.yaml "
            "with replicas: 5 and verified readiness."
        )
        # In reality, the file was never written or has empty/wrong state
        actual_env = {"files_created": []}
        expected = {"files_created": ["/k8s/deploy.yaml"]}

        grade = OutcomeGrader.grade(fraudulent_transcript, actual_env, expected)
        assert grade["passed"] is False
        assert grade["transcript_claims_success"] is True
        assert grade["simulation_only"] is True
        assert "files_created" in grade["missing_keys"] or "files_created" in grade["mismatched_keys"]


class TestRA43UnbiasedPassMetrics:
    """
    RA-4.3: Cálculo programático insesgado de pass@k y pass^k.
    """

    def test_positive_unbiased_combinatorial_estimators(self) -> None:
        """
        [RA-4.3 POSITIVE] Comprueba el cálculo insesgado de pass@k (Chen et al.)
        y pass^k (tau-bench / Yao et al.) usando combinatoria exacta C(c,k)/C(n,k).
        """
        n = 10  # 10 trials
        c = 6   # 6 successes
        k = 3

        # pass@3 unbiased: 1 - C(10-6, 3) / C(10, 3) = 1 - C(4, 3) / C(10, 3) = 1 - 4/120 = 1 - 0.0333 = 0.9667
        pass_at_3 = UnbiasedPassMetrics.pass_at_k(n=n, c=c, k=k)
        assert pytest.approx(pass_at_3, abs=1e-4) == 0.9667

        # pass^3 unbiased: C(6, 3) / C(10, 3) = 20 / 120 = 0.1667
        pass_hat_3 = UnbiasedPassMetrics.pass_hat_k(n=n, c=c, k=k)
        assert pytest.approx(pass_hat_3, abs=1e-4) == 0.1667

    def test_negative_naive_empirical_multiplication_exhibits_bias(self) -> None:
        """
        [RA-4.3 NEGATIVE] Demuestra que el estimador ingenuo (c/n)^k difiere
        del estimador combinatorio insesgado bajo tamaño finito de muestra.
        """
        n = 10
        c = 6
        k = 3

        unbiased_hat = UnbiasedPassMetrics.pass_hat_k(n=n, c=c, k=k)  # 20/120 = 0.1667
        naive_hat = UnbiasedPassMetrics.naive_empirical_pass_hat_k(n=n, c=c, k=k)  # (0.6)^3 = 0.2160

        assert unbiased_hat != pytest.approx(naive_hat, abs=1e-2)
        assert naive_hat > unbiased_hat  # Naive overestimates consistency on small sample


class TestRA44BootstrapPairedConfidenceInterval:
    """
    RA-4.4: Comparador pareado de versiones con intervalo de confianza al 95% por bootstrap.
    """

    def test_positive_significant_improvement_identified(self) -> None:
        """
        [RA-4.4 POSITIVE] Confirma significancia estadística cuando el límite inferior
        del IC 95% bootstrap es estrictamente mayor que cero.
        """
        # Version B consistently outperforms Version A across 25 paired tasks
        scores_a = [0.60] * 25
        scores_b = [0.85] * 25

        report = BootstrapPairedComparator.compare(
            scores_a=scores_a,
            scores_b=scores_b,
            num_bootstrap_samples=1000,
            seed=42,
        )
        assert report["mean_delta"] == 0.25
        assert report["ci_lower_95"] > 0.10
        assert report["is_statistically_significant"] is True
        assert report["winner"] == "version_b"

    def test_negative_overlapping_zero_declares_inconclusive(self) -> None:
        """
        [RA-4.4 NEGATIVE] Detecta que una supuesta 'mejora en media' con IC que cruza el cero
        es ruido estadístico y debe declararse 'inconclusive'.
        """
        # Version B has higher average (mean delta = +0.04), but variance is high and crosses zero
        scores_a = [0.8, 0.4, 0.9, 0.2, 0.5, 0.7, 0.3, 0.6, 0.8, 0.4] * 2
        scores_b = [0.7, 0.5, 0.8, 0.3, 0.6, 0.6, 0.4, 0.7, 0.9, 0.3] * 2

        report = BootstrapPairedComparator.compare(
            scores_a=scores_a,
            scores_b=scores_b,
            num_bootstrap_samples=1000,
            seed=42,
        )
        # CI lower is negative or near zero, indicating overlap
        assert report["ci_lower_95"] <= 0.0 or not report["is_statistically_significant"]
        assert report["winner"] == "inconclusive"
