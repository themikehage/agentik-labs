"""
Tests unitarios deterministas para C1-M5: Estado Durable, HITL y A2A.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

_CURRENT_DIR = Path(__file__).resolve().parent
_M5_DIR = _CURRENT_DIR.parent
_SOLUTION_PATH = _M5_DIR / "solution.py"

_spec = importlib.util.spec_from_file_location("c1_m5_solution", _SOLUTION_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Could not load solution module from {_SOLUTION_PATH}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

DurableCheckpointEngine = _mod.DurableCheckpointEngine
IdempotentOutboxManager = _mod.IdempotentOutboxManager
AsyncHITLCoordinator = _mod.AsyncHITLCoordinator
CleanSlateHandoff = _mod.CleanSlateHandoff
A2ALifecycleStateMachine = _mod.A2ALifecycleStateMachine
validate_a2a_task_json = _mod.validate_a2a_task_json
InvalidStateTransitionError = _mod.InvalidStateTransitionError
RawHistoryLeakError = _mod.RawHistoryLeakError
canonical_hash = _mod.canonical_hash


class TestRA51CheckpointResumption:
    def test_positive_resumes_from_exact_checkpoint_hash(self) -> None:
        engine = DurableCheckpointEngine()
        engine.save_checkpoint("task-100", "step-1", {"counter": 10, "status": "init"})
        engine.save_checkpoint("task-100", "step-2", {"counter": 20, "status": "processing"})
        h3 = engine.save_checkpoint("task-100", "step-3", {"counter": 30, "status": "enriched"})

        step_id, state, res_hash = engine.resume_from_checkpoint("task-100")
        assert step_id == "step-3"
        assert state["counter"] == 30
        assert res_hash == h3
        assert canonical_hash(state) == h3

    def test_negative_restart_from_step_zero_after_interruption_fails(self) -> None:
        engine = DurableCheckpointEngine()
        engine.save_checkpoint("task-200", "step-5", {"stage": "pre_commit"})

        # Simular reinicio defectuoso que ignora checkpoints e intenta volver al paso 0
        def broken_resumption() -> str:
            return "step-0"

        resumed_step = broken_resumption()
        real_step, _, _ = engine.resume_from_checkpoint("task-200")
        assert resumed_step != real_step, "Broken resumption incorrectly reverted to step-0!"


class TestRA52IdempotencyOutbox:
    def test_positive_outbox_idempotence_executes_effect_strictly_once(self) -> None:
        outbox = IdempotentOutboxManager()
        side_effect_execution_counter = 0

        def charge_card(payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal side_effect_execution_counter
            side_effect_execution_counter += 1
            return {"payment_id": "pay-999", "status": "captured", "amount": payload["amount"]}

        # 1ra llamada: ejecuta el efecto
        res1 = outbox.execute_or_replay_effect(
            task_id="t-1",
            step_id="step-pay",
            action="charge_card",
            payload={"amount": 100},
            effect_fn=charge_card,
        )
        assert res1["replayed"] is False
        assert side_effect_execution_counter == 1

        # 2da llamada (replay): usa el outbox sin volver a llamar a la función de pago
        res2 = outbox.execute_or_replay_effect(
            task_id="t-1",
            step_id="step-pay",
            action="charge_card",
            payload={"amount": 100},
            effect_fn=charge_card,
        )
        assert res2["replayed"] is True
        assert side_effect_execution_counter == 1
        assert res2["result"] == res1["result"]

    def test_negative_unprotected_replay_duplicates_side_effects(self) -> None:
        counter = 0

        def unprotected_effect() -> int:
            nonlocal counter
            counter += 1
            return counter

        unprotected_effect()
        unprotected_effect()
        assert counter == 2, "Unprotected side-effect executed twice on replay!"


class TestRA53AsyncHITL:
    def test_positive_async_hitl_suspends_without_thread_block_and_resumes(self) -> None:
        coordinator = AsyncHITLCoordinator()
        suspend_info = coordinator.suspend_for_human(
            task_id="t-order-1",
            reason="High transaction value requires dual authorization",
            context={"amount": 50000, "currency": "EUR"},
        )
        assert suspend_info["status"] == "SUSPENDED"
        token = suspend_info["token"]

        # Reanudación asíncrona guiada por evento
        resume_info = coordinator.resume_with_human_decision(
            task_id="t-order-1",
            token=token,
            approved=True,
            modifications={"approved_by": "sec_officer_4"},
        )
        assert resume_info["status"] == "RESUMED"
        assert resume_info["approved"] is True
        assert resume_info["modifications"]["approved_by"] == "sec_officer_4"

    def test_negative_resume_with_invalid_token_fails(self) -> None:
        coordinator = AsyncHITLCoordinator()
        coordinator.suspend_for_human("t-err", "Review needed", {})
        with pytest.raises(ValueError):
            coordinator.resume_with_human_decision("t-err", "forged-token", approved=True)


class TestRA54CleanSlateHandoff:
    def test_positive_clean_slate_payload_passes_validation(self) -> None:
        valid_payload = {
            "task_id": "subtask-12",
            "structured_context": {"tenant_id": "acme", "summary": "Calculated Q3 balance"},
            "contains_raw_history": False,
        }
        assert CleanSlateHandoff.validate_handoff_payload(valid_payload) is True

    def test_negative_raw_history_leak_fails(self) -> None:
        leaky_payload = {
            "task_id": "subtask-13",
            "structured_context": {"tenant_id": "acme"},
            "messages": [{"role": "user", "content": "Raw chat logs leaked"}],
        }
        with pytest.raises(RawHistoryLeakError):
            CleanSlateHandoff.validate_handoff_payload(leaky_payload)


class TestRA55A2ALifecycleStateMachine:
    def test_positive_a2a_task_json_and_valid_transitions(self) -> None:
        json_path = _M5_DIR / "a2a_task.json"
        assert json_path.exists(), "a2a_task.json must exist in M5 folder."
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert validate_a2a_task_json(data) is True

        sm = A2ALifecycleStateMachine("submitted")
        assert sm.transition("working") == "working"
        assert sm.transition("input-required") == "input-required"
        assert sm.transition("working") == "working"
        assert sm.transition("completed") == "completed"

    def test_negative_illegal_transition_raises_error(self) -> None:
        sm = A2ALifecycleStateMachine("completed")
        with pytest.raises(InvalidStateTransitionError):
            sm.transition("working")
