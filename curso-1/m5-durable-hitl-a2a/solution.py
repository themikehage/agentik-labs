"""
C1-M5: Estado Durable, HITL y A2A
Implementación de referencia para checkpointing durable, outbox idempotente,
suspensión asíncrona HITL, clean-slate handoff y máquina de estados A2A.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable


class InvalidStateTransitionError(Exception):
    """Excepción lanzada ante una transición ilegal en el ciclo de vida de la tarea A2A."""
    pass


class RawHistoryLeakError(Exception):
    """Excepción lanzada cuando un handoff transporta historial bruto no estructurado."""
    pass


def canonical_hash(data: Any) -> str:
    """Calcula el hash SHA-256 canónico de cualquier estructura serializable."""
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class DurableCheckpointEngine:
    """
    RA-5.1: Persistencia y reanudación desde checkpoints con coincidencia exacta de hash.
    """

    def __init__(self) -> None:
        self._checkpoints: dict[str, list[dict[str, Any]]] = {}

    def save_checkpoint(self, task_id: str, step_id: str, state: dict[str, Any]) -> str:
        state_copy = copy.deepcopy(state)
        state_hash = canonical_hash(state_copy)
        record = {
            "step_id": step_id,
            "state_hash": state_hash,
            "state": state_copy,
        }
        if task_id not in self._checkpoints:
            self._checkpoints[task_id] = []
        self._checkpoints[task_id].append(record)
        return state_hash

    def resume_from_checkpoint(self, task_id: str) -> tuple[str, dict[str, Any], str]:
        """
        Retorna (step_id, state, state_hash) del último checkpoint persistido.
        Verifica que el hash coincida exactamente con los datos almacenados.
        """
        if task_id not in self._checkpoints or not self._checkpoints[task_id]:
            raise KeyError(f"No checkpoint found for task '{task_id}'.")

        latest = self._checkpoints[task_id][-1]
        step_id = latest["step_id"]
        stored_hash = latest["state_hash"]
        state = copy.deepcopy(latest["state"])

        computed_hash = canonical_hash(state)
        if stored_hash != computed_hash:
            raise ValueError(f"State corruption detected! Stored: {stored_hash}, computed: {computed_hash}")

        return step_id, state, stored_hash


class IdempotentOutboxManager:
    """
    RA-5.2: Idempotencia estricta de efectos secundarios no reversibles
    mediante claves estables y patrón outbox.
    """

    def __init__(self) -> None:
        self._outbox: dict[str, dict[str, Any]] = {}
        self.call_count: int = 0

    def execute_or_replay_effect(
        self,
        task_id: str,
        step_id: str,
        action: str,
        payload: dict[str, Any],
        effect_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        idempotency_key = f"{task_id}:{step_id}:{action}"

        if idempotency_key in self._outbox:
            cached = copy.deepcopy(self._outbox[idempotency_key])
            cached["replayed"] = True
            return cached

        self.call_count += 1
        result = effect_fn(payload)
        record = {
            "idempotency_key": idempotency_key,
            "result": result,
            "replayed": False,
        }
        self._outbox[idempotency_key] = record
        return copy.deepcopy(record)


class AsyncHITLCoordinator:
    """
    RA-5.3: Human-in-the-Loop asíncrono con suspensión sin bloqueo de hilo/proceso.
    """

    def __init__(self) -> None:
        self._pending_interrupts: dict[str, dict[str, Any]] = {}

    def suspend_for_human(
        self,
        task_id: str,
        reason: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        interrupt_token = f"hitl-token-{hashlib.sha256(task_id.encode()).hexdigest()[:12]}"
        self._pending_interrupts[task_id] = {
            "token": interrupt_token,
            "reason": reason,
            "context": copy.deepcopy(context),
            "status": "SUSPENDED",
        }
        # Retorno inmediato no bloqueante
        return {
            "status": "SUSPENDED",
            "task_id": task_id,
            "token": interrupt_token,
        }

    def resume_with_human_decision(
        self,
        task_id: str,
        token: str,
        approved: bool,
        modifications: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if task_id not in self._pending_interrupts:
            raise KeyError(f"No pending HITL interrupt for task '{task_id}'.")

        record = self._pending_interrupts[task_id]
        if record["token"] != token:
            raise ValueError("Invalid HITL resume token.")

        record["status"] = "RESUMED"
        record["approved"] = approved
        record["modifications"] = modifications or {}
        del self._pending_interrupts[task_id]

        return {
            "task_id": task_id,
            "status": "RESUMED",
            "approved": approved,
            "modifications": record["modifications"],
        }


class CleanSlateHandoff:
    """
    RA-5.4: Clean-slate handoff transportando exclusivamente estados y contratos
    estructurados sin transferir el historial bruto de conversación.
    """

    FORBIDDEN_RAW_KEYS = {
        "messages",
        "raw_history",
        "chat_turns",
        "conversation_history",
        "transcript",
    }

    @classmethod
    def validate_handoff_payload(cls, payload: dict[str, Any]) -> bool:
        if payload.get("contains_raw_history", False) is True:
            raise RawHistoryLeakError("Handoff payload explicitly declared containing raw history.")

        for k in payload.keys():
            if k in cls.FORBIDDEN_RAW_KEYS:
                raise RawHistoryLeakError(f"Forbidden raw history field '{k}' detected in handoff payload.")

        # Verificar campos requeridos de clean-slate handoff
        if "structured_context" not in payload:
            raise ValueError("Handoff payload must contain 'structured_context'.")

        return True


class A2ALifecycleStateMachine:
    """
    RA-5.5: Ciclo de vida formal de tareas A2A:
    submitted -> working -> input-required -> completed / failed.
    """

    VALID_STATES = {"submitted", "working", "input-required", "completed", "failed"}
    VALID_TRANSITIONS = {
        "submitted": {"working"},
        "working": {"input-required", "completed", "failed"},
        "input-required": {"working", "failed"},
        "completed": set(),
        "failed": set(),
    }

    def __init__(self, initial_state: str = "submitted") -> None:
        if initial_state not in self.VALID_STATES:
            raise ValueError(f"Invalid initial state '{initial_state}'.")
        self.current_state = initial_state
        self.history = [initial_state]

    def transition(self, next_state: str) -> str:
        if next_state not in self.VALID_STATES:
            raise ValueError(f"Unknown target state '{next_state}'.")

        allowed = self.VALID_TRANSITIONS.get(self.current_state, set())
        if next_state not in allowed:
            raise InvalidStateTransitionError(
                f"Illegal transition from '{self.current_state}' to '{next_state}'. Allowed: {allowed}"
            )

        self.current_state = next_state
        self.history.append(next_state)
        return self.current_state


def validate_a2a_task_json(data: dict[str, Any]) -> bool:
    """Valida la especificación formal del archivo a2a_task.json."""
    required = {"task_id", "client_agent", "target_agent", "task_spec", "state_handoff", "lifecycle_state"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Missing required keys in a2a_task.json: {missing}")

    CleanSlateHandoff.validate_handoff_payload(data["state_handoff"])

    # Validar que lifecycle_state inicial sea uno de los válidos
    state_machine = A2ALifecycleStateMachine(data["lifecycle_state"])
    return True
