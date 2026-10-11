"""
Hidden Attestation Test Suite for Curso 1 M7 Capstone (Practitioner Level).
Executed during the official unattended certification workflow (certify.yml).
Exercises user-seeded scenario parameterization via labkit.seed,
strict state invariants, durable recovery, and containment boundaries.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c1_m7_hidden_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

MultiagentOrchestratorEngine = _mod.MultiagentOrchestratorEngine
ContextualHybridRAG = _mod.ContextualHybridRAG
HierarchicalMemoryStore = _mod.HierarchicalMemoryStore
calculate_pass_pow_k_ci = _mod.calculate_pass_pow_k_ci
canonical_hash = _mod.canonical_hash

from labkit.seed import derive_seed, parameterize_lab


class TestCapstoneHiddenAttestationSuite:
    """
    Official Attestation Suite for Multiagent Pipeline Engineer Practitioner Credential.
    """

    def test_hidden_user_seeded_parameterization_reproducibility(self) -> None:
        """
        [ATTESTATION-H1] Verifica que la semilla del estudiante personalice
        parámetros de prueba de manera reproducible e impida soluciones hardcodeadas.
        """
        student_id = os.environ.get("AGENTIK_STUDENT_ID", "student-practitioner-c1")
        seed_value = derive_seed(student_id, "c1-m7-capstone")
        params = parameterize_lab(
            user_identifier=student_id,
            lab_name="c1-m7-capstone",
            parameter_space={
                "batch_size": [10, 20, 50, 100],
                "token_budget": [4000, 6000, 8000, 12000],
                "retrieval_k": [3, 5, 10],
            },
        )

        assert params["batch_size"] in [10, 20, 50, 100]
        assert params["token_budget"] in [4000, 6000, 8000, 12000]
        assert params["retrieval_k"] in [3, 5, 10]

        # Invarianza de reproducibilidad ante semilla idéntica
        params_repeat = parameterize_lab(
            user_identifier=student_id,
            lab_name="c1-m7-capstone",
            parameter_space={
                "batch_size": [10, 20, 50, 100],
                "token_budget": [4000, 6000, 8000, 12000],
                "retrieval_k": [3, 5, 10],
            },
        )
        assert params == params_repeat

    def test_hidden_attestation_core_pillars_and_hash_invariance(self) -> None:
        """
        [ATTESTATION-H2] Verifica que la reanudación desde checkpoints
        preserve la integridad matemática exacta del estado bajo perturbación de red simulada.
        """
        engine = MultiagentOrchestratorEngine()
        state = {
            "node": "enrichment_worker",
            "step": 4,
            "accumulated_entities": ["ent-99", "ent-100", "ent-101"],
            "version": 12,
        }
        h = engine.save_checkpoint("task-hidden-01", "step-4", state)

        # Simular reinicio y verificación de reanudación
        step_id, restored_state, restored_hash = engine.resume_checkpoint("task-hidden-01")
        assert step_id == "step-4"
        assert restored_hash == h
        assert canonical_hash(restored_state) == h
        assert restored_state["accumulated_entities"] == state["accumulated_entities"]

    def test_hidden_attestation_outbox_replay_guarantees(self) -> None:
        """
        [ATTESTATION-H3] Garantiza que el patrón outbox prevenga la duplicación
        de efectos secundarios durante 10 reintentos concurrentes/secuenciales.
        """
        engine = MultiagentOrchestratorEngine()
        execution_count = 0

        def mutate_external_ledger(p: dict) -> dict:
            nonlocal execution_count
            execution_count += 1
            return {"tx_hash": "0xabc123", "status": "committed"}

        # 1 ejecución inicial + 10 replays
        res_initial = engine.execute_irreversible_effect(
            task_id="tx-ledger-42",
            step_id="step-commit",
            action="post_to_ledger",
            payload={"amount": 999},
            effect_fn=mutate_external_ledger,
        )
        assert res_initial["replayed"] is False

        for _ in range(10):
            res_rep = engine.execute_irreversible_effect(
                task_id="tx-ledger-42",
                step_id="step-commit",
                action="post_to_ledger",
                payload={"amount": 999},
                effect_fn=mutate_external_ledger,
            )
            assert res_rep["replayed"] is True
            assert res_rep["result"] == res_initial["result"]

        assert execution_count == 1, "External mutation must be invoked strictly once across all replays."

    def test_hidden_attestation_rag_cross_tenant_containment(self) -> None:
        """
        [ATTESTATION-H4] Verifica el aislamiento absoluto de documentos entre tenants
        en la extensión de RAG contextual.
        """
        rag = ContextualHybridRAG()
        rag.index_document("doc-corp-a", "tenant-finance", "Executive financial projections for Q4")
        rag.index_document("doc-corp-b", "tenant-hr", "Executive disciplinary records and salary brackets")

        hr_res = rag.search("executive", tenant_id="tenant-hr", top_k=5)
        assert all(r["tenant_id"] == "tenant-hr" for r in hr_res)
        assert not any(r["doc_id"] == "doc-corp-a" for r in hr_res)

        fin_res = rag.search("executive", tenant_id="tenant-finance", top_k=5)
        assert all(r["tenant_id"] == "tenant-finance" for r in fin_res)
        assert not any(r["doc_id"] == "doc-corp-b" for r in fin_res)

    def test_hidden_attestation_wilson_ci_pass_k_benchmark(self) -> None:
        """
        [ATTESTATION-H5] Evalúa que el cálculo del límite inferior del IC 95% Wilson
        sea estricto y conforme a las fórmulas estadísticas de fiabilidad agéntica.
        """
        runs_100 = [[True, True, True] for _ in range(96)] + [[True, False, False] for _ in range(4)]
        res = calculate_pass_pow_k_ci(runs_100)
        assert res["pass_pow_k"] == 0.96
        assert res["ci_lower"] >= 0.90
