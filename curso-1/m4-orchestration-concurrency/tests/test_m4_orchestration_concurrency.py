"""
Tests unitarios deterministas para C1-M4: Orquestación y Concurrencia.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
from pathlib import Path
from typing import Any

import pytest

_CURRENT_DIR = Path(__file__).resolve().parent
_M4_DIR = _CURRENT_DIR.parent
_SOLUTION_PATH = _M4_DIR / "solution.py"

_spec = importlib.util.spec_from_file_location("c1_m4_solution", _SOLUTION_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Could not load solution module from {_SOLUTION_PATH}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

validate_topology_choice = _mod.validate_topology_choice
ConcurrencyConflictError = _mod.ConcurrencyConflictError
InvalidTopologyChoiceError = _mod.InvalidTopologyChoiceError
CommutativeStateReducer = _mod.CommutativeStateReducer
OptimisticConcurrencyController = _mod.OptimisticConcurrencyController
EvaluatorGeneratorLoop = _mod.EvaluatorGeneratorLoop
ConcurrencyDivergenceClassifier = _mod.ConcurrencyDivergenceClassifier


class TestRA41TopologyChoice:
    def test_positive_topology_choice_valid_json(self) -> None:
        json_path = _M4_DIR / "topology_choice.json"
        assert json_path.exists(), "topology_choice.json must exist in M4 folder."
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert validate_topology_choice(data) is True

    def test_negative_topology_voting_for_arithmetic_fails(self) -> None:
        invalid_data = {
            "problem_id": "bad-topology-1",
            "task_type": "deterministic_numeric_partitioning",
            "problem_description": "Numeric sum of distributed tensors.",
            "chosen_topology": "voting",
            "rejected_topologies": [
              {"topology": "split-and-merge", "rejection_reason": "arbitrary"}
            ],
            "rationale": "Flawed assumption that voting resolves arithmetic.",
            "tradeoffs": {"latency": "high", "cost": "3x", "deterministic_guarantee": "none"},
        }
        with pytest.raises(InvalidTopologyChoiceError):
            validate_topology_choice(invalid_data)


class TestRA42CommutativeReducer:
    def test_positive_commutative_reducer_permutation_invariance(self) -> None:
        init_state = {"counters": {"requests": 0}, "unique_items": set(), "keyed_records": {}}
        updates = [
            {"counters": {"requests": 10}, "unique_items": ["agent-A"], "keyed_records": {"rec1": {"version": 1, "val": "x"}}},
            {"counters": {"requests": 25}, "unique_items": ["agent-B"], "keyed_records": {"rec2": {"version": 1, "val": "y"}}},
            {"counters": {"requests": 5}, "unique_items": ["agent-C"], "keyed_records": {"rec1": {"version": 2, "val": "x_updated"}}},
        ]

        states = []
        for perm in itertools.permutations(updates):
            reduced = CommutativeStateReducer.reduce(init_state, list(perm))
            states.append((reduced["counters"], sorted(list(reduced["unique_items"])), reduced["keyed_records"]))

        # Todas las permutaciones deben producir exactamente el mismo estado
        first = states[0]
        for s in states[1:]:
            assert s == first, "Reducer output diverged under different execution arrival orders!"

    def test_negative_non_commutative_reducer_fails_permutation_invariance(self) -> None:
        init_state = {"event_log": []}
        updates = [{"event": "E1"}, {"event": "E2"}, {"event": "E3"}]

        perms = list(itertools.permutations(updates))
        state_a = CommutativeStateReducer.non_commutative_reduce(init_state, list(perms[0]))
        state_b = CommutativeStateReducer.non_commutative_reduce(init_state, list(perms[-1]))

        # El log en orden naive diverge
        assert state_a["event_log"] != state_b["event_log"]


class TestRA43OptimisticConcurrencyControl:
    def test_positive_occ_versioning_succeeds_and_increments(self) -> None:
        occ = OptimisticConcurrencyController()
        occ.set_initial("res-1", {"balance": 100}, version=1)

        v1, data1 = occ.get("res-1")
        assert v1 == 1
        assert data1["balance"] == 100

        data1["balance"] += 50
        v2 = occ.put("res-1", expected_version=1, new_data=data1)
        assert v2 == 2

        v_curr, data_curr = occ.get("res-1")
        assert v_curr == 2
        assert data_curr["balance"] == 150

    def test_negative_occ_concurrent_conflict_raises_error(self) -> None:
        occ = OptimisticConcurrencyController()
        occ.set_initial("res-shared", {"status": "pending"}, version=1)

        # Worker A actualiza primero
        occ.put("res-shared", expected_version=1, new_data={"status": "approved_by_A"})

        # Worker B intenta actualizar con la versión que leyó inicialmente (v1 ya caducada)
        with pytest.raises(ConcurrencyConflictError) as exc_info:
            occ.put("res-shared", expected_version=1, new_data={"status": "rejected_by_B"})
        assert "OCC conflict" in str(exc_info.value)

    def test_negative_last_write_wins_overwrites_silently(self) -> None:
        occ = OptimisticConcurrencyController()
        occ.set_initial("res-lww", {"value": "initial"}, version=1)

        occ.put("res-lww", expected_version=1, new_data={"value": "worker_A"})
        # Last-write-wins sobrescribe y borra la actualización de worker_A sin advertir
        occ.last_write_wins_put("res-lww", new_data={"value": "worker_B_overwrote"})
        _, current = occ.get("res-lww")
        assert current["value"] == "worker_B_overwrote"


class TestRA44EvaluatorGeneratorLoop:
    def test_positive_evaluator_generator_converges_within_bound(self) -> None:
        def generator(prompt: str, critique: str | None) -> dict[str, Any]:
            step_count = int(critique.split(":")[1]) if critique and "step:" in critique else 0
            return {
                "candidate_id": f"cand-{step_count + 1}",
                "content": f"Solution draft {step_count + 1}",
            }

        def evaluator(candidate: dict[str, Any]) -> dict[str, Any]:
            cid = candidate["candidate_id"]
            if cid == "cand-1":
                return {"score": 0.60, "critique": "Needs more detail step:1"}
            return {"score": 0.95, "critique": "Optimal step:2"}

        res = EvaluatorGeneratorLoop.execute(
            generator_fn=generator,
            evaluator_fn=evaluator,
            initial_prompt="Generate optimized plan",
            max_iterations=4,
            target_score=0.85,
        )
        assert res["converged"] is True
        assert res["steps_executed"] == 2
        assert res["final_score"] == 0.95

    def test_negative_unbounded_or_unconverged_stops_at_hard_ceiling(self) -> None:
        def generator(prompt: str, critique: str | None) -> dict[str, Any]:
            return {"candidate_id": "cand-static", "content": "Static poor solution"}

        def evaluator(candidate: dict[str, Any]) -> dict[str, Any]:
            return {"score": 0.40, "critique": "Unacceptable quality"}

        res = EvaluatorGeneratorLoop.execute(
            generator_fn=generator,
            evaluator_fn=evaluator,
            initial_prompt="Hard task",
            max_iterations=3,
            target_score=0.85,
        )
        assert res["converged"] is False
        assert res["steps_executed"] == 3


class TestRA45ConcurrencyDivergenceClassifier:
    def test_positive_classifies_non_commutative_reducer_vs_contention(self) -> None:
        evidence_reducer = {"order_divergent": True, "occ_conflicts": 0, "lock_timeouts": 0}
        diag_reducer = ConcurrencyDivergenceClassifier.classify(evidence_reducer)
        assert diag_reducer == "NON_COMMUTATIVE_REDUCER"

        evidence_contention = {"order_divergent": False, "occ_conflicts": 14, "lock_timeouts": 2}
        diag_contention = ConcurrencyDivergenceClassifier.classify(evidence_contention)
        assert diag_contention == "CONCURRENCY_CONTENTION"

    def test_negative_misattributing_divergence_fails(self) -> None:
        evidence_reducer = {"order_divergent": True, "occ_conflicts": 0, "lock_timeouts": 0}
        diag = ConcurrencyDivergenceClassifier.classify(evidence_reducer)
        assert diag != "CONCURRENCY_CONTENTION"
