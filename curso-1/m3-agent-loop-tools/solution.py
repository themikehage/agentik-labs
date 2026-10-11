from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Any, Callable
from labkit.clock import Clock, VirtualClock


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    preconditions: list[str]
    when_not_to_use: str


class ToolSpecificationRegistry:
    def __init__(self) -> None:
        self.tools: dict[str, ToolSpec] = {}

    def register_tool(self, spec: ToolSpec) -> None:
        if not spec.when_not_to_use or len(spec.when_not_to_use.strip()) < 15:
            raise ValueError(
                f"Tool '{spec.name}' must declare an explicit 'when_not_to_use' clause (≥15 chars) "
                "to prevent semantic overlap with neighboring tools."
            )

        if not spec.preconditions or len(spec.preconditions) < 1:
            raise ValueError(f"Tool '{spec.name}' must declare at least one verifiable precondition.")

        self.tools[spec.name] = spec

    def validate_disjoint_selection(self, tool_a_name: str, tool_b_name: str) -> bool:
        ta = self.tools.get(tool_a_name)
        tb = self.tools.get(tool_b_name)
        if not ta or not tb:
            raise KeyError("Both tools must be registered.")

        # Ensure tool B is referenced in tool A's when_not_to_use or vice-versa
        disjoint_a = tb.name.lower() in ta.when_not_to_use.lower() or "no usar para" in ta.when_not_to_use.lower()
        disjoint_b = ta.name.lower() in tb.when_not_to_use.lower() or "no usar para" in tb.when_not_to_use.lower()

        if not (disjoint_a or disjoint_b):
            raise ValueError(f"Tools '{tool_a_name}' and '{tool_b_name}' lack mutually disjoint selection boundaries.")

        return True


class ActionableErrorTransformer:
    def transform_exception(self, exc: Exception, tool_name: str) -> dict[str, Any]:
        exc_str = str(exc)
        # Verify no raw stack trace is leaked
        formatted = traceback.format_exc()

        suggestion = "Verifique los argumentos de entrada y reintente con los parámetros corregidos."
        if "timeout" in exc_str.lower() or isinstance(exc, TimeoutError):
            suggestion = "El servicio tardó demasiado (timeout); intente consultar una ventana temporal menor o use un fallback."
        elif "not found" in exc_str.lower() or "404" in exc_str:
            suggestion = "El identificador no existe en la base de datos; consulte el listado previo."

        structured_error = {
            "is_error": True,
            "tool_name": tool_name,
            "error_type": type(exc).__name__,
            "message": exc_str,
            "suggestion": suggestion,
            "recoverable": True,
        }

        json_repr = str(structured_error)
        if "Traceback (most recent call last)" in json_repr:
            raise ValueError("Raw stack trace leaked into structured error response.")

        return structured_error


class HardBudgetManager:
    def __init__(
        self,
        max_tokens: int = 10_000,
        max_tool_calls: int = 10,
        max_cost_usd: float = 0.50,
        clock: Clock | None = None,
    ) -> None:
        self.max_tokens = max_tokens
        self.max_tool_calls = max_tool_calls
        self.max_cost_usd = max_cost_usd
        self.clock = clock or VirtualClock()

        self.spent_tokens: int = 0
        self.tool_calls_count: int = 0
        self.spent_cost_usd: float = 0.0

    def record_usage(self, tokens: int, cost_usd: float) -> None:
        self.spent_tokens += tokens
        self.spent_cost_usd = round(self.spent_cost_usd + cost_usd, 4)

    def record_tool_call(self) -> None:
        self.tool_calls_count += 1

    def is_exhausted(self) -> tuple[bool, str | None]:
        if self.spent_cost_usd >= self.max_cost_usd:
            return True, f"Budget exceeded: spent ${self.spent_cost_usd:.3f} >= limit ${self.max_cost_usd:.3f}"
        if self.spent_tokens >= self.max_tokens:
            return True, f"Token ceiling reached: {self.spent_tokens} >= {self.max_tokens}"
        if self.tool_calls_count >= self.max_tool_calls:
            return True, f"Tool call ceiling reached: {self.tool_calls_count} >= {self.max_tool_calls}"
        return False, None


class LoopGuardDetector:
    def detect_oscillation(self, call_history: list[tuple[str, str]]) -> bool:
        if len(call_history) < 4:
            return False

        # Check for A-B-A-B cycle
        last_4 = call_history[-4:]
        c1, c2, c3, c4 = last_4
        if c1 == c3 and c2 == c4 and c1 != c2:
            return True

        # Check for A-A-A repetition
        last_3 = call_history[-3:]
        if last_3[0] == last_3[1] == last_3[2]:
            return True

        return False


@dataclass
class GovernedRunResult:
    status: str  # "success_postcondition", "stopped_budget", "stopped_oscillation", "stopped_max_steps"
    steps: int
    spend_usd: float
    output: Any = None


class GovernedAgentHarness:
    def __init__(
        self,
        budget_manager: HardBudgetManager,
        loop_guard: LoopGuardDetector,
        error_transformer: ActionableErrorTransformer,
    ) -> None:
        self.budget_manager = budget_manager
        self.loop_guard = loop_guard
        self.error_transformer = error_transformer

    def run(
        self,
        max_steps: int,
        tools: dict[str, Callable[[Any], Any]],
        step_generator: Callable[[int, dict[str, Any]], tuple[str, str]],
        postcondition_checker: Callable[[dict[str, Any]], bool],
    ) -> GovernedRunResult:
        steps = 0
        call_history: list[tuple[str, str]] = []
        environment_state = {"resolved": False, "attempts": 0}

        while steps < max_steps:
            # 1. Budget check
            exhausted, reason = self.budget_manager.is_exhausted()
            if exhausted:
                return GovernedRunResult("stopped_budget", steps, self.budget_manager.spent_cost_usd)

            steps += 1
            self.budget_manager.record_usage(tokens=200, cost_usd=0.01)

            # 2. Get planned tool call from agent step generator
            tool_name, tool_arg = step_generator(steps, environment_state)
            call_history.append((tool_name, tool_arg))

            # 3. Check loop guard for A-B-A-B oscillation
            if self.loop_guard.detect_oscillation(call_history):
                return GovernedRunResult("stopped_oscillation", steps, self.budget_manager.spent_cost_usd)

            # 4. Execute tool with error transformation
            tool_fn = tools.get(tool_name)
            self.budget_manager.record_tool_call()
            if tool_fn:
                try:
                    tool_result = tool_fn(tool_arg)
                    environment_state["last_result"] = tool_result
                except Exception as err:
                    structured_err = self.error_transformer.transform_exception(err, tool_name)
                    environment_state["last_error"] = structured_err

            # 5. External postcondition check
            if postcondition_checker(environment_state):
                return GovernedRunResult("success_postcondition", steps, self.budget_manager.spent_cost_usd, environment_state)

        return GovernedRunResult("stopped_max_steps", steps, self.budget_manager.spent_cost_usd)
