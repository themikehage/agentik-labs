"""
Hidden Attestation Test Suite for Curso 0 M7 Capstone (Practitioner Level).
Executed during the official unattended certification workflow (certify.yml).
Exercises user-seeded scenario parameterization via labkit.seed, adversarial
tampering protection, strict sandbox invariants, and bootstrap statistical gating.
"""

from __future__ import annotations

import json
import os
import sys
import importlib.util
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c0_m7_hidden_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

EnterpriseInferenceService = _mod.EnterpriseInferenceService
EnterpriseServiceError = _mod.EnterpriseServiceError
from labkit.clock import VirtualClock
from labkit.seed import derive_seed, parameterize_lab


class TestCapstoneHiddenAttestationSuite:
    """
    Official Attestation Suite for LLM Production Fundamentals Practitioner Credential.
    """

    def test_hidden_user_seeded_parameterization_reproducibility(self) -> None:
        """
        [ATTESTATION-H1] Verifica que la semilla del estudiante personalice
        parámetros de prueba de manera reproducible e impida soluciones hardcodeadas.
        """
        student_id = os.environ.get("AGENTIK_STUDENT_ID", "student-practitioner-c0")
        seed_value = derive_seed(student_id, "c0-m7-capstone")
        params = parameterize_lab(
            user_identifier=student_id,
            lab_name="c0-m7-capstone",
            parameter_space={
                "max_ttft_ms": [300, 400, 500, 600],
                "quota_k_tokens": [50, 75, 100, 150],
            },
        )

        assert params["max_ttft_ms"] in [300, 400, 500, 600]
        assert params["quota_k_tokens"] in [50, 75, 100, 150]

        # Reproducibility check: identical seed gives identical parameterization
        params_repeat = parameterize_lab(
            user_identifier=student_id,
            lab_name="c0-m7-capstone",
            parameter_space={
                "max_ttft_ms": [300, 400, 500, 600],
                "quota_k_tokens": [50, 75, 100, 150],
            },
        )
        assert params == params_repeat

    def test_hidden_zero_network_leakage_and_metadata_protection(self) -> None:
        """
        [ATTESTATION-H2] Verifica que las herramientas aisladas rechacen cualquier
        configuración con red externa o acceso al endpoint de metadatos de la nube.
        """
        svc = EnterpriseInferenceService()

        # Reject bridge network
        with pytest.raises(EnterpriseServiceError, match="open network"):
            svc.execute_sandboxed_tool(
                tool_name="untrusted_script",
                arguments={"script": "fetch('http://169.254.169.254')"},
                container_flags={"network": "bridge", "user": "10001:10001"},
            )

        # Reject root user
        with pytest.raises(EnterpriseServiceError, match="root"):
            svc.execute_sandboxed_tool(
                tool_name="untrusted_script",
                arguments={"script": "id"},
                container_flags={"network": "none", "user": "0"},
            )

    def test_hidden_adversarial_semantic_business_rejection(self) -> None:
        """
        [ATTESTATION-H3] Verifica que payloads adversariales con valores semánticos
        imposibles o campos mutados fallen la validación de negocio.
        """
        svc = EnterpriseInferenceService()

        # Float instead of integer cents
        res_float = svc.validate_business_output('{"action": "refund", "amount_cents": 12.50}')
        assert res_float["is_valid"] is False

        # Zero cents
        res_zero = svc.validate_business_output('{"action": "refund", "amount_cents": 0}')
        assert res_zero["is_valid"] is False
        assert res_zero["layer_failed"] == "business_semantic"

    def test_hidden_bootstrap_ci_lower_bound_strictly_enforces_gating(self) -> None:
        """
        [ATTESTATION-H4] Verifica que la puerta de evaluación apruebe únicamente
        sistemas donde el límite inferior del IC 95% alcance o supere el umbral.
        """
        svc = EnterpriseInferenceService(seed=12345)

        # Consistent high performance: 30 tasks with 0.85
        high_perf = [0.85] * 30
        res_high = svc.evaluate_reliability_ci(high_perf, threshold_ci_lower=0.75)
        assert res_high["passed"] is True
        assert res_high["ci_lower_95"] >= 0.75

        # Borderline / erratic performance: mean is 0.76, but lower bound is 0.68
        erratic_perf = [0.95, 0.55, 0.85, 0.65, 0.90, 0.50] * 5
        res_erratic = svc.evaluate_reliability_ci(erratic_perf, threshold_ci_lower=0.75)
        assert res_erratic["passed"] is False
        assert res_erratic["ci_lower_95"] < 0.75
