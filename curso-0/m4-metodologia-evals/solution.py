from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class EvalTask:
    task_id: str
    prompt: str
    category: str
    expected_outcome: dict[str, Any]


class EvaluationDataset:
    def __init__(self, tasks: list[EvalTask]) -> None:
        self.validate_dataset(tasks)
        self.tasks = tasks

    @staticmethod
    def validate_dataset(tasks: list[EvalTask]) -> None:
        if len(tasks) < 20 or len(tasks) > 50:
            raise ValueError(
                f"Dataset size must be between 20 and 50 tasks, received {len(tasks)}"
            )

        categories = [t.category for t in tasks]
        valid_cats = {"capability", "regression"}
        if any(cat not in valid_cats for cat in categories):
            raise ValueError("All tasks must be categorized strictly as 'capability' or 'regression'")

        capability_count = sum(1 for c in categories if c == "capability")
        ratio = capability_count / float(len(tasks))
        if ratio < 0.35 or ratio > 0.65:
            raise ValueError(
                f"Dataset must be balanced between capability and regression. "
                f"Capability ratio: {ratio:.2f} (must be between 0.35 and 0.65)"
            )

    @property
    def capability_count(self) -> int:
        return sum(1 for t in self.tasks if t.category == "capability")

    @property
    def regression_count(self) -> int:
        return sum(1 for t in self.tasks if t.category == "regression")


class OutcomeGrader:
    @staticmethod
    def grade(
        transcript: str,
        actual_environment: dict[str, Any],
        expected_outcome: dict[str, Any],
    ) -> dict[str, Any]:
        transcript_claims_success = any(
            marker in transcript.lower()
            for marker in [
                "success",
                "completed",
                "created",
                "executed",
                "done",
                "task finished",
            ]
        )

        outcome_matches = True
        missing_keys: list[str] = []
        mismatched_keys: list[str] = []

        for key, expected_val in expected_outcome.items():
            if key not in actual_environment:
                outcome_matches = False
                missing_keys.append(key)
            elif actual_environment[key] != expected_val:
                outcome_matches = False
                mismatched_keys.append(key)

        simulation_only = transcript_claims_success and not outcome_matches

        return {
            "passed": outcome_matches,
            "outcome_matches": outcome_matches,
            "transcript_claims_success": transcript_claims_success,
            "simulation_only": simulation_only,
            "missing_keys": missing_keys,
            "mismatched_keys": mismatched_keys,
        }


class UnbiasedPassMetrics:
    @staticmethod
    def pass_at_k(n: int, c: int, k: int) -> float:
        if n < k or k <= 0:
            return 0.0
        if n - c < k:
            return 1.0
        return 1.0 - (math.comb(n - c, k) / math.comb(n, k))

    @staticmethod
    def pass_hat_k(n: int, c: int, k: int) -> float:
        if n < k or c < k or k <= 0:
            return 0.0
        return math.comb(c, k) / math.comb(n, k)

    @staticmethod
    def naive_empirical_pass_hat_k(n: int, c: int, k: int) -> float:
        if n <= 0:
            return 0.0
        p = c / float(n)
        return p ** k


class BootstrapPairedComparator:
    @staticmethod
    def compare(
        scores_a: Sequence[float],
        scores_b: Sequence[float],
        num_bootstrap_samples: int = 1000,
        confidence_level: float = 0.95,
        seed: int = 42,
    ) -> dict[str, Any]:
        if len(scores_a) != len(scores_b):
            raise ValueError("Paired comparison requires identical sample lengths")
        if not scores_a:
            raise ValueError("Score samples cannot be empty")

        rng = random.Random(seed)
        n = len(scores_a)
        deltas = [b - a for a, b in zip(scores_a, scores_b)]
        mean_delta = sum(deltas) / float(n)

        bootstrap_means: list[float] = []
        for _ in range(num_bootstrap_samples):
            resampled_deltas = [deltas[rng.randrange(n)] for _ in range(n)]
            bootstrap_means.append(sum(resampled_deltas) / float(n))

        bootstrap_means.sort()
        alpha = 1.0 - confidence_level
        low_idx = int(math.floor((alpha / 2.0) * num_bootstrap_samples))
        high_idx = int(math.ceil((1.0 - alpha / 2.0) * num_bootstrap_samples)) - 1
        low_idx = max(0, min(num_bootstrap_samples - 1, low_idx))
        high_idx = max(0, min(num_bootstrap_samples - 1, high_idx))

        ci_lower = bootstrap_means[low_idx]
        ci_upper = bootstrap_means[high_idx]

        is_significant = ci_lower > 0.0

        return {
            "mean_delta": round(mean_delta, 4),
            "ci_lower_95": round(ci_lower, 4),
            "ci_upper_95": round(ci_upper, 4),
            "is_statistically_significant": is_significant,
            "winner": "version_b" if is_significant else ("version_a" if ci_upper < 0.0 else "inconclusive"),
        }
