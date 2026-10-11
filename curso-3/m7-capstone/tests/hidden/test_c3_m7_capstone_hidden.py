"""
Hidden Attestation Test Suite for Curso 3 M7 Capstone (Practitioner Level).
Executed during the official unattended certification workflow (certify.yml).
Exercises user-seeded scenario parameterization via labkit.seed, strict privacy invariants,
hard budget cutoff boundaries, and automated model failover reproducibility.
"""

from __future__ import annotations

import os
import sys
import importlib.util
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c3_m7_hidden_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

EnterpriseDeliverySystem = _mod.EnterpriseDeliverySystem
BudgetExceededError = _mod.BudgetExceededError
from labkit.seed import derive_seed, parameterize_lab


class TestCapstoneHiddenAttestationSuite:
    """
    Official Attestation Suite for Forward Deployed Engineer Practitioner Credential.
    """

    def test_hidden_user_seeded_parameterization_reproducibility(self) -> None:
        """
        [ATTESTATION-H1] Verifica que la semilla del estudiante personalice
        parámetros de prueba de manera reproducible e impida soluciones hardcodeadas.
        """
        student_id = os.environ.get("AGENTIK_STUDENT_ID", "student-practitioner-c3")
        seed_value = derive_seed(student_id, "c3-m7-capstone")
        params = parameterize_lab(
            user_identifier=student_id,
            lab_name="c3-m7-capstone",
            parameter_space={
                "quota_usd": [0.05, 0.10, 0.15, 0.20],
                "max_allowed_latency_ms": [2000, 2500, 3000, 3500],
            },
        )

        assert params["quota_usd"] in [0.05, 0.10, 0.15, 0.20]
        assert params["max_allowed_latency_ms"] in [2000, 2500, 3000, 3500]

        # Reproducibility check: identical seed gives identical parameterization
        params_repeat = parameterize_lab(
            user_identifier=student_id,
            lab_name="c3-m7-capstone",
            parameter_space={
                "quota_usd": [0.05, 0.10, 0.15, 0.20],
                "max_allowed_latency_ms": [2000, 2500, 3000, 3500],
            },
        )
        assert params == params_repeat

    def test_hidden_failover_and_budget_invariants(self) -> None:
        """
        [ATTESTATION-H2] Valida que bajo condiciones sembradas por usuario,
        el sistema ejecute corte presupuestario duro y conmute automáticamente a failover.
        """
        student_id = os.environ.get("AGENTIK_STUDENT_ID", "student-practitioner-c3")
        params = parameterize_lab(
            user_identifier=student_id,
            lab_name="c3-m7-capstone",
            parameter_space={
                "quota_usd": [0.04, 0.06, 0.08],
            },
        )
        quota = float(params["quota_usd"])

        # System with simulated primary failure (must use secondary model)
        sys_failover = EnterpriseDeliverySystem(simulate_primary_failure=True)
        sys_failover.register_virtual_key("vkey-seeded", tenant="tenant-audit", max_budget_usd=quota)

        jwt = {"sub": f"usr-{student_id}", "tenant_id": "tenant-audit"}
        res = sys_failover.process_request(
            virtual_key_id="vkey-seeded",
            user_jwt=jwt,
            prompt="Consulta segura de siniestro",
            cost_usd=quota * 0.5,
        )

        assert res["status"] == "success"
        assert res["failover_triggered"] is True
        assert res["model_used"] == "anthropic/claude-3-haiku"

        # Next request attempts remaining cost plus extra -> must raise BudgetExceededError
        with pytest.raises(BudgetExceededError):
            sys_failover.process_request(
                virtual_key_id="vkey-seeded",
                user_jwt=jwt,
                prompt="Segunda consulta",
                cost_usd=quota * 0.6,  # 0.5 + 0.6 = 1.1 * quota > quota!
            )

    def test_hidden_zero_pii_leakage_invariants(self) -> None:
        """
        [ATTESTATION-H3] Verifica invariante de fuga cero de PII directa
        para múltiples combinaciones sembradas de identificadores y correos.
        """
        system = EnterpriseDeliverySystem()
        system.register_virtual_key("vkey-attest", tenant="tenant-pii", max_budget_usd=1.0)
        jwt = {"sub": "auditor-oidc-root"}

        pii_cases = [
            ("Cliente DNI 78901234X solicita peritaje urgente.", "78901234X"),
            ("Notificar a maria.santos@hospital.example sobre liquidacion.", "maria.santos@hospital.example"),
            ("Asegurado extranjero NIE Y1234567Z en expediente.", "Y1234567Z"),
        ]

        for text, direct_identifier in pii_cases:
            res = system.process_request("vkey-attest", jwt, text, cost_usd=0.001)
            assert res["status"] == "success"
            # Invariant: raw identifier MUST NOT exist in sanitized prompt!
            assert direct_identifier not in res["sanitized_prompt"]
            # Must contain pseudonymized placeholder
            assert "[NIF_" in res["sanitized_prompt"] or "[EMAIL_" in res["sanitized_prompt"]
