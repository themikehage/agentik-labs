from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    name: str
    has_sequential_dependencies: bool
    requires_dynamic_subtasks: bool
    is_open_ended: bool
    requires_iterative_feedback: bool
    is_branching_classification: bool


class WorkflowPatternClassifier:
    VALID_CRITERIA = {
        "reproducibilidad_estricta",
        "baja_latencia",
        "baja_latencia_p95",
        "coste_acotado",
        "coste_acotado_predecible",
        "ruta_de_control_fija",
    }

    def classify_task(self, task: TaskSpec | dict[str, Any]) -> str:
        if isinstance(task, dict):
            t_id = task.get("task_id", "")
            seq = bool(task.get("has_sequential_dependencies", False))
            dynamic = bool(task.get("requires_dynamic_subtasks", False))
            open_ended = bool(task.get("is_open_ended", False))
            feedback = bool(task.get("requires_iterative_feedback", False))
            branching = bool(task.get("is_branching_classification", False))
            pattern_claim = task.get("claimed_pattern")
        else:
            t_id = task.task_id
            seq = task.has_sequential_dependencies
            dynamic = task.requires_dynamic_subtasks
            open_ended = task.is_open_ended
            feedback = task.requires_iterative_feedback
            branching = task.is_branching_classification
            pattern_claim = None

        if pattern_claim == "parallelization" and seq:
            raise ValueError(
                f"Sequential dependency violation: Task '{t_id}' has strict causal sequential dependencies "
                "and cannot be categorized under 'parallelization'."
            )

        if open_ended:
            return "autonomous_agent"
        if feedback:
            return "evaluator_optimizer"
        if dynamic:
            return "orchestrator_workers"
        if branching:
            return "routing"
        if seq:
            return "prompt_chaining"
        return "parallelization"

    def validate_agent_discard(self, justification: str, criteria_cited: list[str]) -> bool:
        norm_just = justification.lower().strip()
        if len(norm_just) < 15 or "es mas simple" in norm_just or "es más simple" in norm_just:
            raise ValueError(
                "Superficial discard rejected: Justification must be grounded in concrete technical trade-offs, "
                "not vague statements like 'es más simple'."
            )

        matched_criteria = {c.lower().replace("-", "_") for c in criteria_cited if c.lower().replace("-", "_") in self.VALID_CRITERIA}
        if len(matched_criteria) < 2:
            raise ValueError(
                f"Discard justification must cite at least 2 explicit architectural criteria from: {self.VALID_CRITERIA}. "
                f"Got: {list(matched_criteria)}"
            )

        return True


class AgentCostDistributionModel:
    def simulate_agent_costs(
        self,
        seed: int,
        num_runs: int = 50,
        base_step_cost: float = 0.005,
    ) -> dict[str, Any]:
        if num_runs < 30:
            raise ValueError("Statistical robustness requires at least 30 simulated runs.")

        rng = random.Random(seed)
        costs: list[float] = []

        # Model stochastic exploration: number of steps follows geometric/Poisson process
        for _ in range(num_runs):
            steps = rng.randint(2, 9)
            token_jitter = rng.uniform(0.85, 1.35)
            run_cost = steps * base_step_cost * token_jitter
            costs.append(run_cost)

        mean_cost = sum(costs) / len(costs)
        variance = sum((c - mean_cost) ** 2 for c in costs) / (len(costs) - 1)
        std_dev = math.sqrt(variance)
        std_error = std_dev / math.sqrt(len(costs))

        # 95% Confidence Interval (t_0.025 ≈ 2.01 for n ~ 50)
        ci_lower = round(mean_cost - 2.00 * std_error, 5)
        ci_upper = round(mean_cost + 2.00 * std_error, 5)

        return {
            "num_runs": num_runs,
            "mean_cost_usd": round(mean_cost, 5),
            "variance": round(variance, 8),
            "ci_95": [ci_lower, ci_upper],
            "is_stochastic": True,
        }

    def assert_not_static_multiplier(self, reported_summary: dict[str, Any]) -> None:
        if not reported_summary.get("is_stochastic", False) or "ci_95" not in reported_summary:
            raise ValueError(
                "Cost modeling error: Reporting a static literal multiplier (e.g. '15x') without empirical "
                "distribution and confidence interval is rejected."
            )


@dataclass
class ReActState:
    steps_executed: int
    total_cost_usd: float
    status: str
    output: Any = None


class MinimalReActHarness:
    def execute_loop(
        self,
        max_steps: int,
        budget_usd: float,
        postcondition_checker: Callable[[dict[str, Any]], bool],
        step_cost: float = 0.01,
        simulate_infinite_loop: bool = False,
    ) -> ReActState:
        steps = 0
        current_spend = 0.0
        state = {"completed_goal": False, "artifact_saved": False}

        while True:
            # Check budget limit
            if (current_spend + step_cost) > budget_usd:
                return ReActState(steps, current_spend, status="stopped_budget_exceeded")

            # Check max steps limit
            if steps >= max_steps:
                return ReActState(steps, current_spend, status="stopped_max_steps_exceeded")

            # Simulate agent work step
            steps += 1
            current_spend = round(current_spend + step_cost, 4)

            if not simulate_infinite_loop:
                if steps >= 3:
                    state["completed_goal"] = True
                    state["artifact_saved"] = True

            # Independent external postcondition check
            if postcondition_checker(state):
                return ReActState(steps, current_spend, status="success_postcondition_met", output=state)


def compare_workflow_vs_agent(
    workflow_metrics: list[dict[str, float]],
    agent_metrics: list[dict[str, float]],
) -> dict[str, Any]:
    def compute_stats(items: list[dict[str, float]], key: str) -> tuple[float, float]:
        vals = [it[key] for it in items]
        mean_v = sum(vals) / len(vals)
        var_v = sum((v - mean_v) ** 2 for v in vals) / (len(vals) - 1) if len(vals) > 1 else 0.0
        return mean_v, var_v

    wf_cost_mean, wf_cost_var = compute_stats(workflow_metrics, "cost_usd")
    ag_cost_mean, ag_cost_var = compute_stats(agent_metrics, "cost_usd")

    wf_lat_mean, wf_lat_var = compute_stats(workflow_metrics, "latency_s")
    ag_lat_mean, ag_lat_var = compute_stats(agent_metrics, "latency_s")

    return {
        "workflow": {
            "mean_cost": round(wf_cost_mean, 5),
            "cost_variance": round(wf_cost_var, 8),
            "mean_latency": round(wf_lat_mean, 3),
            "latency_variance": round(wf_lat_var, 6),
        },
        "agent": {
            "mean_cost": round(ag_cost_mean, 5),
            "cost_variance": round(ag_cost_var, 8),
            "mean_latency": round(ag_lat_mean, 3),
            "latency_variance": round(ag_lat_var, 6),
        },
        "variance_ratio_agent_to_wf": round(ag_cost_var / (wf_cost_var + 1e-9), 2),
    }
