"""
Reference tests for Curso 1 M3 - Bucle del Agente y Herramientas.
Validates:
- RA-3.1: Independent verifiable stops (postcondition vs budget vs max steps).
- RA-3.2: Formal tool specification enforcing when_not_to_use clauses.
- RA-3.3: Actionable structured error transformation preventing raw stack trace leaks.
- RA-3.4: Hard budget manager tracking tokens, costs and tool call limits.
- RA-3.5: Loop guard detecting A-B-A-B oscillation and no-progress cycles.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c1_m3_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

GovernedAgentHarness = _mod.GovernedAgentHarness
ToolSpecificationRegistry = _mod.ToolSpecificationRegistry
ToolSpec = _mod.ToolSpec
ActionableErrorTransformer = _mod.ActionableErrorTransformer
HardBudgetManager = _mod.HardBudgetManager
LoopGuardDetector = _mod.LoopGuardDetector


class TestRA31IndependentVerifiableStops:
    """
    RA-3.1: Paradas independientes y verificables (postcondición vs presupuesto).
    """

    def test_positive_stops_on_external_postcondition_and_budget_exhaustion(self) -> None:
        """
        [RA-3.1 POSITIVE] Confirma que el arnés se detiene con éxito cuando la postcondición
        se verifica en el entorno, y corta limpiamente si se agota el presupuesto.
        """
        budget = HardBudgetManager(max_cost_usd=0.20, max_tool_calls=5)
        loop_guard = LoopGuardDetector()
        err_trans = ActionableErrorTransformer()
        harness = GovernedAgentHarness(budget, loop_guard, err_trans)

        tools = {"fetch_policy": lambda arg: {"policy_id": arg, "status": "active"}}

        # Scenario A: Success via postcondition
        def step_gen_ok(step: int, env: dict) -> tuple[str, str]:
            if step == 2:
                env["resolved"] = True
            return ("fetch_policy", f"POL-{step}")

        res = harness.run(
            max_steps=10,
            tools=tools,
            step_generator=step_gen_ok,
            postcondition_checker=lambda env: env.get("resolved", False),
        )
        assert res.status == "success_postcondition"
        assert res.steps == 2

    def test_negative_loop_without_external_stop_hangs_unless_budget_cuts_it(self) -> None:
        """
        [RA-3.1 NEGATIVE] Demuestra que si la herramienta falla permanentemente y no
        se cumple la postcondición, el presupuesto duro corta deterministamente el bucle.
        """
        budget = HardBudgetManager(max_cost_usd=0.03, max_tool_calls=10)
        harness = GovernedAgentHarness(budget, LoopGuardDetector(), ActionableErrorTransformer())

        tools = {"failing_tool": lambda arg: (_ for _ in ()).throw(RuntimeError("DB Connection Failed"))}

        # Step generator alternates slightly to not trigger oscillation
        def step_gen_fail(step: int, env: dict) -> tuple[str, str]:
            return ("failing_tool", f"query_{step}")

        res = harness.run(
            max_steps=20,
            tools=tools,
            step_generator=step_gen_fail,
            postcondition_checker=lambda env: False,  # Never satisfied
        )
        assert res.status == "stopped_budget"


class TestRA32ToolSpecificationAndDisjointness:
    """
    RA-3.2: Especificación formal de herramientas y cláusula when_not_to_use.
    """

    def test_positive_valid_tools_with_negative_clauses(self) -> None:
        """
        [RA-3.2 POSITIVE] Confirma registro exitoso de herramientas que declaran
        precondiciones y cláusulas explícitas de exclusión mutua.
        """
        registry = ToolSpecificationRegistry()
        t1 = ToolSpec(
            name="search_customer_by_nif",
            description="Busca la ficha del cliente a partir de su documento NIF/NIE.",
            input_schema={"type": "object", "properties": {"nif": {"type": "string"}}},
            preconditions=["NIF con formato valido"],
            when_not_to_use="No usar para busquedas genericas de pólizas; use search_policy_by_id.",
        )
        t2 = ToolSpec(
            name="search_policy_by_id",
            description="Obtiene las coberturas de una póliza conociendo su número.",
            input_schema={"type": "object", "properties": {"policy_id": {"type": "string"}}},
            preconditions=["Identificador de póliza disponible"],
            when_not_to_use="No usar para localizar al cliente por su NIF; use search_customer_by_nif.",
        )

        registry.register_tool(t1)
        registry.register_tool(t2)
        assert registry.validate_disjoint_selection("search_customer_by_nif", "search_policy_by_id") is True

    def test_negative_tool_omits_when_not_to_use_fails(self) -> None:
        """
        [RA-3.2 NEGATIVE] Demuestra que omitir la cláusula 'when_not_to_use' es rechazado
        por riesgo de solapamiento semántico en la selección del modelo.
        """
        registry = ToolSpecificationRegistry()
        ambiguous_tool = ToolSpec(
            name="ambiguous_search",
            description="Busca cosas.",
            input_schema={},
            preconditions=["algo"],
            when_not_to_use="",  # Vacío
        )
        with pytest.raises(ValueError, match="must declare an explicit 'when_not_to_use' clause"):
            registry.register_tool(ambiguous_tool)


class TestRA33ActionableErrorTransformation:
    """
    RA-3.3: Transformación de excepciones crudas en respuestas accionables sin stack trace.
    """

    def test_positive_transforms_exception_to_structured_actionable_json(self) -> None:
        """
        [RA-3.3 POSITIVE] Confirma que un error de infraestructura se convierte
        en una respuesta estructurada con sugerencias de corrección legibles para el LLM.
        """
        transformer = ActionableErrorTransformer()
        err = TimeoutError("Connection to policy DB timed out after 5000ms")

        structured = transformer.transform_exception(err, tool_name="fetch_policy")
        assert structured["is_error"] is True
        assert structured["tool_name"] == "fetch_policy"
        assert "timeout" in structured["suggestion"].lower()
        assert "Traceback" not in str(structured)


class TestRA34HardBudgetTracking:
    """
    RA-3.4: Techo de presupuesto duro monitorizando tokens y coste.
    """

    def test_positive_hard_budget_tracks_tokens_and_tool_calls(self) -> None:
        """
        [RA-3.4 POSITIVE] Confirma que el gestor acumula gasto y detecta agotamiento
        tan pronto como se sobrepasa cualquiera de las cotas configuradas.
        """
        budget = HardBudgetManager(max_tokens=1000, max_tool_calls=3, max_cost_usd=0.05)
        assert budget.is_exhausted()[0] is False

        budget.record_usage(tokens=500, cost_usd=0.02)
        budget.record_tool_call()
        assert budget.is_exhausted()[0] is False

        # Exceed tool calls ceiling
        budget.record_tool_call()
        budget.record_tool_call()
        exhausted, reason = budget.is_exhausted()
        assert exhausted is True
        assert "Tool call ceiling reached" in reason


class TestRA35OscillationAndLoopGuards:
    """
    RA-3.5: Detección de oscilación A-B-A-B y guardas de bucle.
    """

    def test_positive_detects_abab_oscillation_and_halts_deterministically(self) -> None:
        """
        [RA-3.5 POSITIVE] Confirma que una secuencia cíclica sin progreso A-B-A-B
        es detectada por el Loop Guard, deteniendo el harness con estado stopped_oscillation.
        """
        budget = HardBudgetManager(max_cost_usd=1.0)
        loop_guard = LoopGuardDetector()
        harness = GovernedAgentHarness(budget, loop_guard, ActionableErrorTransformer())

        tools = {
            "search_web": lambda q: "Sin resultados",
            "check_cache": lambda q: "Cache miss",
        }

        # Alternates A-B-A-B with identical arguments
        def step_gen_oscillate(step: int, env: dict) -> tuple[str, str]:
            if step % 2 == 1:
                return ("search_web", "query-fixed")
            return ("check_cache", "query-fixed")

        res = harness.run(
            max_steps=10,
            tools=tools,
            step_generator=step_gen_oscillate,
            postcondition_checker=lambda env: False,
        )
        assert res.status == "stopped_oscillation"
        assert res.steps == 4  # A, B, A, B -> caught at step 4!
