from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


class RegressionBreachError(Exception):
    pass


@dataclass(frozen=True)
class RailBudget:
    rail_name: str
    rail_type: str  # "deterministic" or "self_check_llm"
    latency_budget_ms: float


class GuardrailsConfigValidator:
    def validate_rails_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        input_rails = config.get("input_rails", [])
        output_rails = config.get("output_rails", [])

        if not input_rails or not isinstance(input_rails, list):
            raise ValueError("Configuration must declare at least one input rail.")
        if not output_rails or not isinstance(output_rails, list):
            raise ValueError("Configuration must declare at least one output rail.")

        budgets = config.get("budgets", [])
        if not budgets or not isinstance(budgets, list):
            raise ValueError("Configuration must declare explicit latency budgets per rail.")

        # Check budget latency differentiation
        has_self_check = False
        has_deterministic = False

        for b in budgets:
            rail_type = b.get("rail_type", "").lower()
            latency = float(b.get("latency_budget_ms", 0))

            if rail_type == "deterministic":
                has_deterministic = True
                if latency > 50.0:
                    raise ValueError(f"Deterministic rail '{b.get('rail_name')}' budget ({latency}ms) is abnormally high for in-memory checks.")
            elif rail_type == "self_check_llm":
                has_self_check = True
                if latency < 100.0:
                    raise ValueError(
                        f"Latency budget error: Self-check rail '{b.get('rail_name')}' is allocated {latency}ms. "
                        "Self-check rails invoke LLM inference and require at least 150-500ms; assuming <15ms is a fallacy."
                    )

        if not (has_deterministic and has_self_check):
            raise ValueError("Enterprise configuration requires both deterministic and self-check LLM rail budgets.")

        return {
            "status": "valid",
            "input_rails_count": len(input_rails),
            "output_rails_count": len(output_rails),
        }


@dataclass
class EvaluationMetricWithCI:
    metric_name: str
    rate: float
    ci_lower: float
    ci_upper: float
    sample_size: int


class GuardrailEvaluator:
    PROHIBITED_CLAIMS = (
        "bloqueo del 100%",
        "100% de bloqueo",
        "bloqueo total",
        "zero jailbreaks",
        "100% jailbreak blocking",
        "cero ataques",
    )

    def validate_claims(self, claims: list[str]) -> None:
        for c in claims:
            c_low = c.lower()
            for pattern in self.PROHIBITED_CLAIMS:
                if pattern in c_low:
                    raise ValueError(
                        f"Claim '{c}' is technically misleading: Guardrails are probabilistic classifiers. "
                        "Promising 100% jailbreak blocking is factually impossible and ignores the TPR/FPR trade-off curve."
                    )

    def _calculate_wilson_ci(self, successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
        if total <= 0:
            return 0.0, 0.0
        p = successes / float(total)
        denominator = 1.0 + (z**2 / total)
        centre_adjusted_probability = p + (z**2 / (2 * total))
        adjusted_standard_deviation = math.sqrt((p * (1 - p) / total) + (z**2 / (4 * total**2)))
        lower = (centre_adjusted_probability - z * adjusted_standard_deviation) / denominator
        upper = (centre_adjusted_probability + z * adjusted_standard_deviation) / denominator
        return max(0.0, round(lower, 4)), min(1.0, round(upper, 4))

    def evaluate_adversarial_dataset(
        self,
        dataset: list[dict[str, Any]],
        predictions: list[dict[str, Any]],
    ) -> dict[str, EvaluationMetricWithCI]:
        pred_map = {p["id"]: p.get("is_blocked", False) for p in predictions}

        tp = 0  # Adversarial and blocked
        fn = 0  # Adversarial and not blocked
        fp = 0  # Benign and blocked (false alarm)
        tn = 0  # Benign and not blocked

        for item in dataset:
            iid = item["id"]
            is_adv = bool(item.get("is_adversarial", False))
            blocked = pred_map.get(iid, False)

            if is_adv:
                if blocked:
                    tp += 1
                else:
                    fn += 1
            else:
                if blocked:
                    fp += 1
                else:
                    tn += 1

        total_positives = tp + fn
        total_negatives = fp + tn

        tpr = tp / float(total_positives) if total_positives > 0 else 0.0
        fpr = fp / float(total_negatives) if total_negatives > 0 else 0.0

        tpr_ci_low, tpr_ci_high = self._calculate_wilson_ci(tp, total_positives)
        fpr_ci_low, fpr_ci_high = self._calculate_wilson_ci(fp, total_negatives)

        return {
            "TPR": EvaluationMetricWithCI(
                metric_name="True Positive Rate (Sensitivity)",
                rate=round(tpr, 4),
                ci_lower=tpr_ci_low,
                ci_upper=tpr_ci_high,
                sample_size=total_positives,
            ),
            "FPR": EvaluationMetricWithCI(
                metric_name="False Positive Rate (Fallout)",
                rate=round(fpr, 4),
                ci_lower=fpr_ci_low,
                ci_upper=fpr_ci_high,
                sample_size=total_negatives,
            ),
        }


class SloSpecValidator:
    def validate_specification(self, spec: dict[str, Any]) -> dict[str, Any]:
        required = ("sli", "slo", "sla", "error_budget_policy")
        for r in required:
            if r not in spec:
                raise ValueError(f"SLO specification missing required section '{r}'.")

        sli = spec["sli"]
        slo = spec["slo"]
        sla = spec["sla"]
        policy = spec["error_budget_policy"]

        if not sli.get("name") or not sli.get("metric_expression"):
            raise ValueError("SLI must define 'name' and an observable 'metric_expression'.")

        slo_target = float(slo.get("target_threshold", 0))
        sla_target = float(sla.get("contractual_commitment", 0))

        if not (0.80 <= slo_target <= 1.0):
            raise ValueError(f"SLO target threshold ({slo_target}) must be a valid percentage/ratio.")

        # SRE Principle: SLA must be lower than internal SLO to protect the organization
        if sla_target >= slo_target:
            raise ValueError(
                f"SLA commitment ({sla_target}) cannot be greater than or equal to internal SLO ({slo_target}). "
                "SLO is an aggressive internal objective; SLA is a conservative contractual threshold with penalties."
            )

        if not sla.get("penalty_clauses"):
            raise ValueError("SLA must declare legal or financial penalty clauses upon breach.")

        if not policy.get("action_on_exhaustion"):
            raise ValueError("Error budget policy must declare an explicit action when budget is exhausted.")

        return {
            "status": "valid",
            "sli_name": sli["name"],
            "slo_target": slo_target,
            "sla_target": sla_target,
            "error_budget_percentage": round((1.0 - slo_target) * 100, 2),
        }


class AcceptanceGate:
    def evaluate_gate(
        self,
        golden_set_score: float,
        min_threshold: float,
        regression_evals: list[dict[str, Any]],
    ) -> dict[str, Any]:
        broken_regressions: list[str] = []
        for reg in regression_evals:
            if not reg.get("passed", False):
                broken_regressions.append(reg.get("case_name", "unnamed_case"))

        if broken_regressions:
            raise RegressionBreachError(
                f"Acceptance Gate BLOCKED: Deployment broke {len(broken_regressions)} historical regression evals: "
                + ", ".join(broken_regressions)
            )

        if golden_set_score < min_threshold:
            raise ValueError(
                f"Acceptance Gate BLOCKED: Golden set score ({golden_set_score:.4f}) is below minimum threshold ({min_threshold:.4f})."
            )

        return {
            "gate_status": "APPROVED",
            "golden_set_score": golden_set_score,
            "regressions_clean": True,
        }
