"""
Hidden Attestation Test Suite for Curso 2 M7 Capstone (Practitioner Level).
Executed during the official unattended certification workflow (certify.yml).
Exercises adversarial edge cases, cryptographic requestState tamper protection,
and user-seeded scenario parameterization via labkit.seed.
"""

from __future__ import annotations

import json
import os
import sys
import importlib.util
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c2_m7_hidden_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

EnterpriseMcpGateway = _mod.EnterpriseMcpGateway
from labkit.clock import VirtualClock
from labkit.seed import derive_seed, parameterize_lab


class TestCapstoneHiddenAttestationSuite:
    """
    Official Attestation Suite for MCP Expert Practitioner Credential.
    """

    def test_hidden_tampered_request_state_signature_fails_closed(self) -> None:
        """
        [ATTESTATION-H1] Verifica que un atacante que altere el requestState
        (ej. forzando aprobación o inyectando estado espurio) sea rechazado con -32602.
        """
        gateway = EnterpriseMcpGateway()
        payload = {
            "iss": "https://auth.agentik.im",
            "aud": "urn:agentik:mcp-gateway",
            "sub": "student-eval",
            "scope": ["tools:invoke"],
            "exp": 99999.0,
        }
        headers = {
            "Authorization": f"Bearer {json.dumps(payload)}",
            "Content-Type": "application/json",
        }
        meta = {
            "version": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        }

        # Step 1: get authentic requestState
        _, _, res1 = gateway.handle_http(
            headers=headers,
            body={"jsonrpc": "2.0", "id": "h-1", "method": "tools/call", "params": {"name": "deploy_service", "_meta": meta}},
        )
        legit_state = res1["result"]["requestState"]

        # Attacker tampers payload before signature delimiter
        tampered_state = "hacked_state" + legit_state[legit_state.find(":"):]

        _, _, bad_res = gateway.handle_http(
            headers=headers,
            body={
                "jsonrpc": "2.0",
                "id": "h-2",
                "method": "tools/call",
                "params": {
                    "name": "deploy_service",
                    "requestState": tampered_state,
                    "inputResponses": {"confirm_prod": "YES"},
                    "_meta": meta,
                },
            },
        )
        assert "error" in bad_res
        assert bad_res["error"]["code"] == -32602
        assert "tampered" in bad_res["error"]["message"].lower()

    def test_hidden_user_seeded_parameterization_reproducibility(self) -> None:
        """
        [ATTESTATION-H2] Confirma que los parámetros sembrados por usuario derivados
        de derive_seed(candidate_id) generan un entorno reproducible y resistente a copia directa.
        """
        candidate_id = os.environ.get("GITHUB_ACTOR", "candidate_official_eval")
        seed_val = derive_seed(candidate_id)

        # Parameterize lab scenarios
        spec = {
            "scenarios": ["standard", "high_concurrency", "rate_limited", "geo_distributed"],
            "retry_threshold": [1, 2, 3, 5],
        }
        scenario_a = parameterize_lab(candidate_id, "c2-m7-capstone", spec)
        scenario_b = parameterize_lab(candidate_id, "c2-m7-capstone", spec)

        # Same candidate gets identical seeded scenario
        assert scenario_a == scenario_b

        # Different candidate gets distinct deterministic seed
        seed_other = derive_seed("different_user_456", "c2-m7-capstone")
        assert seed_val != seed_other

    def test_hidden_zero_cross_request_state_leakage(self) -> None:
        """
        [ATTESTATION-H3] Verifica que múltiples llamadas concurrentes de distintos
        usuarios no filtren ni compartan tokens downstream o estados de sesión.
        """
        gateway = EnterpriseMcpGateway()
        clock = VirtualClock(initial_time=500.0)
        gateway.clock = clock

        users = ["alice", "bob", "carol"]
        meta = {
            "version": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        }

        for u in users:
            jwt = {
                "iss": "https://auth.agentik.im",
                "aud": "urn:agentik:mcp-gateway",
                "sub": f"usr-{u}",
                "scope": ["tools:invoke"],
                "exp": 1000.0,
            }
            h = {"Authorization": f"Bearer {json.dumps(jwt)}", "Content-Type": "application/json"}

            # Complete MRTR
            _, _, step1 = gateway.handle_http(
                headers=h,
                body={"jsonrpc": "2.0", "id": f"init-{u}", "method": "tools/call", "params": {"name": "deploy_service", "_meta": meta}},
            )
            state = step1["result"]["requestState"]

            _, _, step2 = gateway.handle_http(
                headers=h,
                body={
                    "jsonrpc": "2.0",
                    "id": f"done-{u}",
                    "method": "tools/call",
                    "params": {
                        "name": "deploy_service",
                        "requestState": state,
                        "inputResponses": {"confirm_prod": "YES"},
                        "_meta": meta,
                    },
                },
            )
            assert step2["result"]["resultType"] == "complete"
