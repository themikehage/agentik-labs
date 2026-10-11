"""
Tests unitarios deterministas para C1-M6: Fallos, Seguridad y Evals de Agentes.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

_CURRENT_DIR = Path(__file__).resolve().parent
_M6_DIR = _CURRENT_DIR.parent
_SOLUTION_PATH = _M6_DIR / "solution.py"

_spec = importlib.util.spec_from_file_location("c1_m6_solution", _SOLUTION_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Could not load solution module from {_SOLUTION_PATH}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

validate_mast_classify_json = _mod.validate_mast_classify_json
PostconditionEnvironmentGrader = _mod.PostconditionEnvironmentGrader
BoundarySecurityEvaluator = _mod.BoundarySecurityEvaluator
FourAxisEvalHarness = _mod.FourAxisEvalHarness
UnsubstantiatedClaimError = _mod.UnsubstantiatedClaimError


class TestRA61MASTTaxonomy:
    def test_positive_mast_json_valid(self) -> None:
        json_path = _M6_DIR / "mast_classify.json"
        assert json_path.exists(), "mast_classify.json must exist in M6 folder."
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert validate_mast_classify_json(data) is True

    def test_negative_generic_category_fails(self) -> None:
        bad_data = {
            "taxonomy": "MAST",
            "version": "1.0",
            "incidents": [
                {
                    "incident_id": "INC-BAD",
                    "symptom": "Random bug",
                    "category": "agent_failure",  # Antipatrón: categoría genérica no taxonomizada
                    "root_cause": "Unknown",
                    "remediation": "Retry",
                }
            ],
            "orchestrabench_caveats": {"methodological_caveats": ["caveat-1"]},
        }
        with pytest.raises(ValueError) as exc_info:
            validate_mast_classify_json(bad_data)
        assert "Invalid incident category" in str(exc_info.value)


class TestRA62OrchestraBenchCaveats:
    def test_positive_acknowledges_methodological_caveats(self) -> None:
        json_path = _M6_DIR / "mast_classify.json"
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        caveats = data.get("orchestrabench_caveats", {}).get("methodological_caveats", [])
        assert len(caveats) >= 2, "Must document at least 2 methodological caveats for OrchestraBench."


class TestRA63PostconditionGraders:
    def test_positive_grader_verifies_environment_match(self) -> None:
        agent_output = {"status": "SUCCESS", "message": "Record migrated"}
        env = {"record_status": "MIGRATED_OK", "tenant_id": "cust-42"}

        ok, msg = PostconditionEnvironmentGrader.grade(
            agent_output=agent_output,
            environment=env,
            expected_key="record_status",
            expected_val="MIGRATED_OK",
        )
        assert ok is True
        assert msg == "POSTCONDITION_VERIFIED"

    def test_negative_detects_silent_failure_when_agent_claims_success(self) -> None:
        # El agente emite JSON válido con status SUCCESS, pero en la base de datos el registro no existe
        agent_output = {"status": "SUCCESS", "message": "Transaction committed"}
        env = {"transaction_applied": False}

        ok, msg = PostconditionEnvironmentGrader.grade(
            agent_output=agent_output,
            environment=env,
            expected_key="transaction_applied",
            expected_val=True,
        )
        assert ok is False
        assert "SILENT_FAILURE" in msg


class TestRA64BoundarySecurityTPR_FPR:
    def test_positive_computes_tpr_and_fpr_accurately(self) -> None:
        labels = [1, 1, 1, 1, 0, 0, 0, 0]
        preds = [1, 1, 1, 0, 0, 0, 0, 1]  # 3 TP, 1 FN, 1 FP, 3 TN
        metrics = BoundarySecurityEvaluator.compute_tpr_fpr(labels, preds)
        assert metrics["tpr"] == 0.75  # 3/4
        assert metrics["fpr"] == 0.25  # 1/4

        # Validación del informe de seguridad
        assert BoundarySecurityEvaluator.validate_security_claim(metrics) is True

    def test_negative_rejects_unsubstantiated_or_trivial_containment(self) -> None:
        # Omisión de FPR
        with pytest.raises(UnsubstantiatedClaimError):
            BoundarySecurityEvaluator.validate_security_claim({"tpr": 1.0})

        # Bloqueo total trivial (TPR 100% pero 50% de falsos positivos bloqueando tráfico legítimo)
        with pytest.raises(UnsubstantiatedClaimError):
            BoundarySecurityEvaluator.validate_security_claim({"tpr": 1.0, "fpr": 0.50})


class TestRA65FourAxisEvalAndPassK:
    def test_positive_evaluates_pass_pow_k_with_wilson_ci(self) -> None:
        # 100 tareas con k=3 corridas cada una; 95 tareas pasaron las 3 corridas
        runs_data = [[True, True, True] for _ in range(95)] + [[True, False, True] for _ in range(5)]
        report = FourAxisEvalHarness.evaluate_unattended_autonomy_gate(runs_data, min_ci_threshold=0.85)

        assert report["total_tasks"] == 100
        assert report["pass_pow_k_rate"] == 0.95
        assert report["pass_at_k_rate"] == 1.00
        assert report["ci_95_lower_bound"] > 0.85
        assert report["autonomy_authorized"] is True

    def test_negative_rejects_autonomy_when_pass_at_k_is_high_but_pass_pow_k_fails(self) -> None:
        # 100 tareas: en 80 tareas solo pasa 1 o 2 de las 3 corridas (alta varianza estocástica)
        # pass@3 es alto (100%), pero pass^3 es solo 20%
        runs_data = [[True, True, True] for _ in range(20)] + [[True, False, False] for _ in range(80)]
        report = FourAxisEvalHarness.evaluate_unattended_autonomy_gate(runs_data, min_ci_threshold=0.80)

        assert report["pass_at_k_rate"] == 1.00
        assert report["pass_pow_k_rate"] == 0.20
        assert report["autonomy_authorized"] is False, "Unattended autonomy should not be granted on high pass@k with low pass^k!"
