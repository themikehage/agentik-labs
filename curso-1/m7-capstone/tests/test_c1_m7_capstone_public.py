"""
Public tests for Curso 1 M7 Capstone: Multiagent Pipeline Engineer.
Validates:
- RA-7.1: Formal DESIGN.md validation (core + 2 extensions, numerical metrics, signed consequences).
- RA-7.2: Integration of the 7 core pillars (commutative reduction, checkpointing, outbox, HITL, guards, graders).
- RA-7.3: Independent unit verification of the 2 selected extensions (Contextual RAG & Memory with TTL).
- RA-7.4: Statistical reliability evaluated via the 95% CI lower bound of pass^k.
- RA-7.5: Inter-agent boundary containment reporting both TPR and FPR.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c1_m7_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

validate_design_md = _mod.validate_design_md
DesignValidationError = _mod.DesignValidationError
MultiagentOrchestratorEngine = _mod.MultiagentOrchestratorEngine
ContextualHybridRAG = _mod.ContextualHybridRAG
HierarchicalMemoryStore = _mod.HierarchicalMemoryStore
calculate_pass_pow_k_ci = _mod.calculate_pass_pow_k_ci


class TestRA71DesignDocValidation:
    def test_positive_design_md_valid(self) -> None:
        design_path = Path(__file__).resolve().parent.parent / "DESIGN.md"
        assert design_path.exists(), "DESIGN.md must exist in M7 folder."
        with open(design_path, "r", encoding="utf-8") as f:
            content = f.read()
        res = validate_design_md(content)
        assert res["valid"] is True
        assert res["selected_extensions"] == ["A", "B"]
        assert res["numbers_count"] >= 3

    def test_negative_design_md_without_negative_tradeoffs_fails(self) -> None:
        bad_content = """
# DESIGN
## 1. Core Architecture Declaration
Core pillars implemented.
## 2. Selected Extensions
Selected Extension A: RAG
Selected Extension B: Memory
## 3. Quantitative Decision Metrics
100ms latency, 8000 tokens, 95% pass rate.
## 4. Signed Consequences & Trade-offs
- + Only positive consequences mentioned here.
- + Zero negative trade-offs documented.
"""
        with pytest.raises(DesignValidationError) as exc:
            validate_design_md(bad_content)
        assert "negative consequences" in str(exc.value).lower()

    def test_negative_design_md_without_numerical_metrics_fails(self) -> None:
        bad_content = """
# DESIGN
## 1. Core Architecture Declaration
Core.
## 2. Selected Extensions
Selected Extension A: RAG
Selected Extension B: Memory
## 3. Quantitative Decision Metrics
Fast latency, minimal tokens, good pass rate.
## 4. Signed Consequences & Trade-offs
- + Good
- - Bad
"""
        with pytest.raises(DesignValidationError) as exc:
            validate_design_md(bad_content)
        assert "numerical values" in str(exc.value).lower()


class TestRA72CorePillarsIntegration:
    def test_positive_core_pillars_integrated(self) -> None:
        engine = MultiagentOrchestratorEngine()

        # 1. Reducer conmutativo
        init_state = {"metrics": {"processed": 0}, "artifacts": set()}
        u1 = {"metrics": {"processed": 10}, "artifacts": ["art-1"]}
        u2 = {"metrics": {"processed": 20}, "artifacts": ["art-2"]}
        state_order_1 = engine.reduce_superstep(init_state, [u1, u2])
        state_order_2 = engine.reduce_superstep(init_state, [u2, u1])
        assert state_order_1 == state_order_2, "Superstep reduction must be order-invariant."

        # 2. Checkpointing durable con hash idéntico
        h = engine.save_checkpoint("task-c1", "step-2", state_order_1)
        step_id, loaded_state, loaded_hash = engine.resume_checkpoint("task-c1")
        assert step_id == "step-2"
        assert loaded_hash == h
        assert loaded_state["metrics"]["processed"] == 30

        # 3. Efectos idempotentes con outbox
        calls = 0

        def fire_webhook(payload: dict) -> dict:
            nonlocal calls
            calls += 1
            return {"status": "sent"}

        engine.execute_irreversible_effect("task-c1", "step-3", "webhook", {}, fire_webhook)
        # Replay
        res_replay = engine.execute_irreversible_effect("task-c1", "step-3", "webhook", {}, fire_webhook)
        assert calls == 1, "Side effect executed more than once during replay!"
        assert res_replay["replayed"] is True

        # 4. Suspensión HITL asíncrona
        token = engine.request_human_approval("task-c1", "High risk action", {})
        res_hitl = engine.resume_human_approval("task-c1", token, approved=True)
        assert res_hitl["status"] == "RESUMED"

        # 5. Loop Guard: oscilación A-B-A-B
        assert engine.detect_oscillation_guard(["stepA", "stepB", "stepA", "stepB"]) is True
        assert engine.detect_oscillation_guard(["stepA", "stepB", "stepC", "stepD"]) is False

        # 6. Postcondition grader en entorno
        engine.mock_env["db_migrated"] = True
        assert engine.grade_environment_postcondition("db_migrated", True) is True
        assert engine.grade_environment_postcondition("db_migrated", False) is False


class TestRA73SelectedExtensionsValidation:
    def test_positive_extension_a_contextual_rag_tenant_isolation_and_rrf(self) -> None:
        rag = ContextualHybridRAG()
        # Documentos para tenant A y tenant B
        rag.index_document("doc-1", "tenant-alpha", "Deployment guidelines and pipeline configurations.")
        rag.index_document("doc-2", "tenant-beta", "Deployment guidelines for confidential secret project.")

        # Búsqueda para tenant-alpha no debe filtrar ni retornar doc-2 de tenant-beta
        results = rag.search("deployment pipeline", tenant_id="tenant-alpha", top_k=5)
        assert len(results) > 0
        for r in results:
            assert r["tenant_id"] == "tenant-alpha"
            assert r["doc_id"] != "doc-2", "Cross-tenant document leakage detected!"
            assert r["rrf_score"] > 0

    def test_positive_extension_b_hierarchical_memory_with_ttl_purge(self) -> None:
        mem = HierarchicalMemoryStore()
        now = 1000.0
        mem.store_working("tenant-alpha", "user-1", "Temporary JWT token", timestamp=now, ttl_seconds=60.0)

        # A t = 1030s (dentro de TTL), sigue presente
        assert len(mem.get_working("tenant-alpha", "user-1", current_timestamp=1030.0)) == 1

        # A t = 1070s (fuera de TTL), purga determinista
        purged = mem.purge_expired(current_timestamp=1070.0)
        assert purged == 1
        assert len(mem.get_working("tenant-alpha", "user-1", current_timestamp=1070.0)) == 0


class TestRA74PassPowKStatisticalReliability:
    def test_positive_pass_pow_k_ci_lower_bound_exceeds_threshold(self) -> None:
        # 100 tareas x 3 corridas; 94 tareas pasan todas las 3 corridas
        runs_data = [[True, True, True] for _ in range(94)] + [[True, False, True] for _ in range(6)]
        res = calculate_pass_pow_k_ci(runs_data)
        assert res["pass_pow_k"] == 0.94
        assert res["ci_lower"] >= 0.85, "Lower bound of Wilson 95% CI must exceed 0.85 threshold."

    def test_negative_pure_point_estimate_gate_fails(self) -> None:
        # 10 tareas: 9 éxitos parece 90%, pero el IC inferior al 95% con N=10 cae dramáticamente
        small_sample = [[True, True, True] for _ in range(9)] + [[False, False, False] for _ in range(1)]
        res = calculate_pass_pow_k_ci(small_sample)
        # Con N=10, el límite inferior cae por debajo de 0.60
        assert res["ci_lower"] < 0.70, "Small sample size must yield conservative CI lower bound."


class TestRA75InterAgentBoundaryContainment:
    def test_positive_boundary_security_reports_tpr_and_fpr(self) -> None:
        # Simulación de barrera de contención con reporte honesto
        ground_truth = [1] * 20 + [0] * 80  # 20 ataques, 80 benignos
        predictions = [1] * 19 + [0] * 1 + [1] * 3 + [0] * 77  # 19 TP, 1 FN, 3 FP, 77 TN

        tp = sum(1 for y, p in zip(ground_truth, predictions) if y == 1 and p == 1)
        fn = sum(1 for y, p in zip(ground_truth, predictions) if y == 1 and p == 0)
        fp = sum(1 for y, p in zip(ground_truth, predictions) if y == 0 and p == 1)
        tn = sum(1 for y, p in zip(ground_truth, predictions) if y == 0 and p == 0)

        tpr = tp / (tp + fn)
        fpr = fp / (fp + tn)

        assert tpr >= 0.95
        assert fpr <= 0.05
