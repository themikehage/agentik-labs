"""
C1-M4: Orquestación y Concurrencia
Implementación de referencia para reducers conmutativos, OCC, bucle evaluador-generador
y diagnóstico forense de divergencia en sistemas multi-agente.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable


class ConcurrencyConflictError(Exception):
    """Excepción lanzada cuando falla una comprobación de versión en OCC."""
    pass


class InvalidTopologyChoiceError(Exception):
    """Excepción lanzada cuando una topología no es admisible para el problema."""
    pass


def validate_topology_choice(data: dict[str, Any]) -> bool:
    """
    RA-4.1: Valida que la selección de topología cumpla el esquema formal
    y rechaza elecciones conceptualmente erróneas (ej. consenso para agregación aritmética).
    """
    required_keys = {
        "problem_id",
        "task_type",
        "problem_description",
        "chosen_topology",
        "rejected_topologies",
        "rationale",
        "tradeoffs",
    }
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"Missing required keys in topology choice: {missing}")

    valid_topologies = {"split-and-merge", "orchestrator-workers", "voting"}
    if data["chosen_topology"] not in valid_topologies:
        raise ValueError(f"Invalid topology '{data['chosen_topology']}'. Must be one of {valid_topologies}")

    if not isinstance(data["rejected_topologies"], list) or len(data["rejected_topologies"]) == 0:
        raise ValueError("rejected_topologies must be a non-empty list documenting alternative trade-offs.")

    for rej in data["rejected_topologies"]:
        if "topology" not in rej or "rejection_reason" not in rej:
            raise ValueError("Each rejected topology must document topology and rejection_reason.")

    # Antipatrón: consenso/voting para agregación matemática determinista
    if data.get("task_type") in ("deterministic_numeric_partitioning", "exact_arithmetic"):
        if data["chosen_topology"] == "voting":
            raise InvalidTopologyChoiceError(
                "Voting/consensus topology cannot be chosen for deterministic arithmetic aggregation."
            )

    return True


class CommutativeStateReducer:
    """
    RA-4.2: Reducer conmutativo e invariante al orden de llegada de escrituras en superpasos.
    """

    @staticmethod
    def reduce(
        current_state: dict[str, Any],
        updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Aplica una lista de actualizaciones concurrentes garantizando invarianza
        ante cualquier permutación del orden de las actualizaciones.
        """
        new_state = copy.deepcopy(current_state)
        if "counters" not in new_state:
            new_state["counters"] = {}
        if "unique_items" not in new_state:
            new_state["unique_items"] = set()
        if "keyed_records" not in new_state:
            new_state["keyed_records"] = {}

        for update in updates:
            # 1. Contadores aditivos (la suma es asociativa y conmutativa)
            for k, val in update.get("counters", {}).items():
                new_state["counters"][k] = new_state["counters"].get(k, 0) + val

            # 2. Conjuntos únicos (la unión de conjuntos es asociativa y conmutativa)
            for item in update.get("unique_items", []):
                new_state["unique_items"].add(item)

            # 3. Registros con clave determinista (resolución por max timestamp o ID ordenado)
            for rec_id, rec_data in update.get("keyed_records", {}).items():
                if rec_id not in new_state["keyed_records"]:
                    new_state["keyed_records"][rec_id] = rec_data
                else:
                    # En colisión, orden determinista por timestamp / versión más alta
                    existing = new_state["keyed_records"][rec_id]
                    if rec_data.get("version", 0) > existing.get("version", 0):
                        new_state["keyed_records"][rec_id] = rec_data

        return new_state

    @staticmethod
    def non_commutative_reduce(
        current_state: dict[str, Any],
        updates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Reducer no conmutativo ingenuo (antipatrón): list.append sin orden determinista.
        """
        new_state = copy.deepcopy(current_state)
        if "event_log" not in new_state:
            new_state["event_log"] = []
        for update in updates:
            new_state["event_log"].append(update.get("event"))
        return new_state


class OptimisticConcurrencyController:
    """
    RA-4.3: Control de Concurrencia Optimista (OCC) con versionado estricto.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[int, Any]] = {}

    def set_initial(self, resource_id: str, data: Any, version: int = 1) -> None:
        self._store[resource_id] = (version, copy.deepcopy(data))

    def get(self, resource_id: str) -> tuple[int, Any]:
        if resource_id not in self._store:
            raise KeyError(f"Resource '{resource_id}' does not exist.")
        version, data = self._store[resource_id]
        return version, copy.deepcopy(data)

    def put(self, resource_id: str, expected_version: int, new_data: Any) -> int:
        """
        Actualiza el recurso solo si la versión esperada coincide con la actual.
        Incrementa la versión en 1 y retorna la nueva versión.
        """
        if resource_id not in self._store:
            raise KeyError(f"Resource '{resource_id}' does not exist.")

        curr_version, _ = self._store[resource_id]
        if curr_version != expected_version:
            raise ConcurrencyConflictError(
                f"OCC conflict on '{resource_id}': expected version {expected_version}, but found {curr_version}."
            )

        new_version = curr_version + 1
        self._store[resource_id] = (new_version, copy.deepcopy(new_data))
        return new_version

    def last_write_wins_put(self, resource_id: str, new_data: Any) -> int:
        """
        Antipatrón Last-Write-Wins: sobrescribe sin verificar versión.
        """
        curr_version, _ = self._store.get(resource_id, (0, None))
        new_version = curr_version + 1
        self._store[resource_id] = (new_version, copy.deepcopy(new_data))
        return new_version


class EvaluatorGeneratorLoop:
    """
    RA-4.4: Bucle evaluador-generador con cotas duras de corrección,
    diagnóstico explícito de convergencia y contratos de nodo disjuntos.
    """

    @staticmethod
    def execute(
        generator_fn: Callable[[str, str | None], dict[str, Any]],
        evaluator_fn: Callable[[dict[str, Any]], dict[str, Any]],
        initial_prompt: str,
        max_iterations: int = 5,
        target_score: float = 0.85,
    ) -> dict[str, Any]:
        if max_iterations <= 0:
            raise ValueError("max_iterations must be positive and bounded.")

        iterations_history: list[dict[str, Any]] = []
        feedback: str | None = None
        converged = False
        final_candidate: dict[str, Any] | None = None

        for step in range(1, max_iterations + 1):
            candidate = generator_fn(initial_prompt, feedback)
            # Validar esquema disjunto del generador
            if "content" not in candidate or "candidate_id" not in candidate:
                raise ValueError("Generator output lacks required disjoint contract schema.")

            evaluation = evaluator_fn(candidate)
            # Validar esquema disjunto del evaluador
            if "score" not in evaluation or "critique" not in evaluation:
                raise ValueError("Evaluator output lacks required disjoint contract schema.")

            score = float(evaluation["score"])
            feedback = evaluation["critique"]
            final_candidate = candidate

            iterations_history.append({
                "step": step,
                "score": score,
                "critique": feedback,
                "candidate_id": candidate["candidate_id"],
            })

            if score >= target_score:
                converged = True
                break

        return {
            "converged": converged,
            "steps_executed": len(iterations_history),
            "max_iterations": max_iterations,
            "final_score": iterations_history[-1]["score"] if iterations_history else 0.0,
            "final_candidate": final_candidate,
            "history": iterations_history,
        }


class ConcurrencyDivergenceClassifier:
    """
    RA-4.5: Clasificador forense que diagnostica si una divergencia
    se debe a un reducer no conmutativo o a contención por locks/OCC.
    """

    @staticmethod
    def classify(evidence: dict[str, Any]) -> str:
        order_divergent = evidence.get("order_divergent", False)
        occ_conflicts = evidence.get("occ_conflicts", 0)
        lock_timeouts = evidence.get("lock_timeouts", 0)

        if order_divergent:
            return "NON_COMMUTATIVE_REDUCER"

        if occ_conflicts > 0 or lock_timeouts > 0:
            return "CONCURRENCY_CONTENTION"

        return "UNKNOWN_DIAGNOSIS"
