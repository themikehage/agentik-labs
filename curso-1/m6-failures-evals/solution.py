"""
C1-M6: Fallos, Seguridad y Evals de Agentes
Implementación de referencia para clasificación MAST, caveats OrchestraBench,
post-condition graders observables, seguridad inter-agente (TPR/FPR) y evals de 4 ejes con pass^k e IC 95%.
"""

from __future__ import annotations

import copy
import json
import math
from typing import Any


class UnsubstantiatedClaimError(Exception):
    """Excepción lanzada cuando una aseveración de seguridad o benchmark omite métricas críticas."""
    pass


class SilentFailureError(Exception):
    """Excepción lanzada cuando un agente reporta éxito pero el entorno no satisface la postcondición."""
    pass


def validate_mast_classify_json(data: dict[str, Any]) -> bool:
    """
    RA-6.1 & RA-6.2: Valida la taxonomía MAST y los caveats de OrchestraBench.
    """
    if data.get("taxonomy") != "MAST":
        raise ValueError("Invalid taxonomy. Must be 'MAST'.")

    valid_categories = {"SPECIFICATION", "COORDINATION", "VERIFICATION"}
    incidents = data.get("incidents", [])
    if not isinstance(incidents, list) or len(incidents) == 0:
        raise ValueError("Incidents must be a non-empty list.")

    for inc in incidents:
        for req in ("incident_id", "symptom", "category", "root_cause", "remediation"):
            if req not in inc:
                raise ValueError(f"Incident missing required field '{req}'.")
        if inc["category"] not in valid_categories:
            raise ValueError(
                f"Invalid incident category '{inc['category']}'. Must be one of {valid_categories}. "
                "Generic tags like 'agent_failure' are rejected."
            )

    caveats = data.get("orchestrabench_caveats", {})
    if not caveats or not caveats.get("methodological_caveats"):
        raise ValueError("OrchestraBench caveats must document methodological caveats.")

    return True


class PostconditionEnvironmentGrader:
    """
    RA-6.3: Grader que inspecciona el estado observable en el entorno
    para atrapar fallos silenciosos (agente auto-reporta éxito pero el entorno está inalterado).
    """

    @staticmethod
    def grade(
        agent_output: dict[str, Any],
        environment: dict[str, Any],
        expected_key: str,
        expected_val: Any,
    ) -> tuple[bool, str]:
        # Validar consistencia del reporte del agente
        reported_status = agent_output.get("status", "").upper()

        actual_val = environment.get(expected_key)
        condition_satisfied = actual_val == expected_val

        if reported_status == "SUCCESS" and not condition_satisfied:
            return (
                False,
                f"SILENT_FAILURE: Agent self-reported SUCCESS, but environment state '{expected_key}' "
                f"is '{actual_val}', expected '{expected_val}'.",
            )

        if not condition_satisfied:
            return False, f"POSTCONDITION_FAILED: Expected '{expected_val}', found '{actual_val}'."

        return True, "POSTCONDITION_VERIFIED"


class BoundarySecurityEvaluator:
    """
    RA-6.4: Evaluación de contención y seguridad inter-agente midiendo TPR y FPR.
    Rechaza promesas de 100% de contención que omitan o escondan el FPR.
    """

    @staticmethod
    def compute_tpr_fpr(labels: list[int], predictions: list[int]) -> dict[str, float]:
        """
        labels: 1 = malicious/injection, 0 = benign
        predictions: 1 = blocked/flagged, 0 = allowed
        """
        if len(labels) != len(predictions) or len(labels) == 0:
            raise ValueError("Labels and predictions must be non-empty and of equal length.")

        tp = sum(1 for y, y_hat in zip(labels, predictions) if y == 1 and y_hat == 1)
        fn = sum(1 for y, y_hat in zip(labels, predictions) if y == 1 and y_hat == 0)
        fp = sum(1 for y, y_hat in zip(labels, predictions) if y == 0 and y_hat == 1)
        tn = sum(1 for y, y_hat in zip(labels, predictions) if y == 0 and y_hat == 0)

        tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        return {
            "tp": float(tp),
            "fn": float(fn),
            "fp": float(fp),
            "tn": float(tn),
            "tpr": round(tpr, 4),
            "fpr": round(fpr, 4),
        }

    @staticmethod
    def validate_security_claim(claim_report: dict[str, Any]) -> bool:
        if "tpr" not in claim_report or "fpr" not in claim_report:
            raise UnsubstantiatedClaimError("Security claim must report both TPR and FPR explicitly.")

        # Si proclama 100% contención (TPR == 1.0) pero FPR es omitido o absurdo (ej. bloquea todo)
        if claim_report["tpr"] == 1.0 and claim_report["fpr"] > 0.30:
            raise UnsubstantiatedClaimError(
                f"Trivial containment: TPR=1.0 obtained at unacceptable false positive cost (FPR={claim_report['fpr']})."
            )

        return True


class FourAxisEvalHarness:
    """
    RA-6.5: Arnés de evals sobre 4 ejes (trayectoria, herramientas, resultado, coste)
    y métrica estricta de consistencia pass^k con intervalo de confianza Wilson al 95%.
    """

    @staticmethod
    def calculate_wilson_ci_lower_bound(successes: int, total: int, confidence: float = 0.95) -> float:
        if total <= 0:
            return 0.0

        # Para 95% de confianza, z = 1.95996
        z = 1.959964
        p_hat = successes / total
        denominator = 1.0 + (z**2) / total
        center = p_hat + (z**2) / (2.0 * total)
        spread = z * math.sqrt((p_hat * (1.0 - p_hat) / total) + (z**2) / (4.0 * (total**2)))
        lower_bound = (center - spread) / denominator
        return max(0.0, round(lower_bound, 4))

    @classmethod
    def evaluate_unattended_autonomy_gate(
        cls,
        task_k_runs: list[list[bool]],
        min_ci_threshold: float = 0.80,
    ) -> dict[str, Any]:
        """
        task_k_runs: lista de tareas, donde cada elemento es una lista de booleanos
        representando k ejecuciones independientes de la misma tarea.
        pass^k: la tarea pasa si y solo si TODAS sus k corridas son True.
        """
        total_tasks = len(task_k_runs)
        if total_tasks == 0:
            raise ValueError("Evaluation task dataset cannot be empty.")

        pass_pow_k_successes = 0
        pass_at_k_successes = 0

        for runs in task_k_runs:
            if all(runs):
                pass_pow_k_successes += 1
            if any(runs):
                pass_at_k_successes += 1

        pass_pow_k_rate = pass_pow_k_successes / total_tasks
        pass_at_k_rate = pass_at_k_successes / total_tasks

        ci_lower = cls.calculate_wilson_ci_lower_bound(pass_pow_k_successes, total_tasks)
        authorized = ci_lower >= min_ci_threshold

        return {
            "total_tasks": total_tasks,
            "pass_pow_k_rate": round(pass_pow_k_rate, 4),
            "pass_at_k_rate": round(pass_at_k_rate, 4),
            "ci_95_lower_bound": ci_lower,
            "min_ci_threshold": min_ci_threshold,
            "autonomy_authorized": authorized,
        }
