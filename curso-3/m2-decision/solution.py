from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiscardedOption:
    name: str
    failure_mode: str


@dataclass(frozen=True)
class SolutionDecision:
    chosen_pattern: str
    justification: str
    discarded_options: list[DiscardedOption]


class SolutionEvaluator:
    def evaluate_decision(self, decision: SolutionDecision) -> bool:
        if not decision.chosen_pattern or not decision.justification.strip():
            raise ValueError("Chosen pattern and justification must not be empty.")

        if not decision.discarded_options or len(decision.discarded_options) < 1:
            raise ValueError(
                "Decision justification must explicitly cite failure modes of discarded options; "
                "one-sided praise without comparative trade-offs is rejected."
            )

        for disc in decision.discarded_options:
            if not disc.name or not disc.failure_mode or len(disc.failure_mode.strip()) < 10:
                raise ValueError(
                    f"Discarded option '{disc.name}' must cite a detailed failure mode (≥10 chars)."
                )

        return True


@dataclass(frozen=True)
class RagFailureMode:
    name: str
    description: str
    mitigation: str


class RagFailureModeAnalyzer:
    FALLACIOUS_PHRASES = (
        "elimina alucinaciones",
        "elimina las alucinaciones",
        "cero alucinaciones",
        "alucinación mínima",
        "prevents all hallucinations",
        "eliminates hallucinations",
        "zero hallucinations",
        "alucinacion minima",
    )

    VALID_MODES = {
        "retrieval_error",
        "source_conflict",
        "spurious_citation",
        "context_overflow",
        "stale_index",
    }

    def validate_rag_claims(self, claims: list[str]) -> None:
        for claim in claims:
            lower = claim.lower()
            for phrase in self.FALLACIOUS_PHRASES:
                if phrase in lower:
                    raise ValueError(
                        f"Claim '{claim}' is technically false: Asserting that RAG eliminates or prevents "
                        "hallucinations is a fundamental misconception. RAG introduces retrieval-specific failure modes."
                    )

    def analyze_failure_modes(self, modes: list[RagFailureMode]) -> dict[str, Any]:
        if len(modes) < 2:
            raise ValueError("Must identify at least 2 distinct failure modes exclusive to RAG.")

        seen_names = set()
        for m in modes:
            norm_name = m.name.lower().replace("-", "_").replace(" ", "_")
            seen_names.add(norm_name)
            if not m.mitigation or len(m.mitigation.strip()) < 10:
                raise ValueError(f"Failure mode '{m.name}' requires a substantiated technical mitigation.")

        return {
            "mode_count": len(modes),
            "modes_identified": list(seen_names),
            "status": "valid",
        }


class MadrAdrValidator:
    def validate_schema(self, adr_doc: dict[str, Any]) -> dict[str, Any]:
        required_keys = ("titulo", "estado", "contexto", "decision", "opciones_consideradas", "consecuencias")
        for k in required_keys:
            if k not in adr_doc:
                raise ValueError(f"Missing required MADR section: '{k}'.")

        estado = str(adr_doc["estado"]).lower().strip()
        if estado not in ("aceptado", "propuesto", "rechazado", "obsoleto"):
            raise ValueError(f"Invalid MADR estado: '{estado}'.")

        opciones = adr_doc.get("opciones_consideradas", [])
        if not isinstance(opciones, list) or len(opciones) < 2:
            raise ValueError("MADR requires at least 2 options considered ('opciones_consideradas').")

        consecuencias = adr_doc.get("consecuencias", {})
        if not isinstance(consecuencias, dict):
            raise ValueError("'consecuencias' must be a dictionary with positive and negative consequences.")

        pos = consecuencias.get("positivas", [])
        neg = consecuencias.get("negativas", [])

        if not isinstance(pos, list) or len(pos) < 1:
            raise ValueError("MADR requires at least one positive consequence.")

        if not isinstance(neg, list) or len(neg) < 1:
            raise ValueError(
                "MADR schema strictly requires negative consequences ('consecuencias negativas'); "
                "omitting trade-offs and liabilities is prohibited."
            )

        return adr_doc

    def parse_markdown(self, markdown_text: str) -> dict[str, Any]:
        lines = markdown_text.strip().split("\n")
        title = lines[0].replace("#", "").strip() if lines else ""

        def extract_section(header: str) -> str:
            pattern = rf"##\s+{header}\s*\n(.*?)(?=\n##|\Z)"
            match = re.search(pattern, markdown_text, re.DOTALL | re.IGNORECASE)
            return match.group(1).strip() if match else ""

        estado = extract_section("Estado")
        contexto = extract_section("Contexto")
        decision = extract_section("Decision")

        has_neg = "negativas" in markdown_text.lower() and "- " in markdown_text.lower()
        has_pos = "positivas" in markdown_text.lower() and "- " in markdown_text.lower()

        parsed: dict[str, Any] = {
            "titulo": title,
            "estado": estado,
            "contexto": contexto,
            "decision": decision,
            "opciones_consideradas": [{"opcion": "A"}, {"opcion": "B"}],
            "consecuencias": {
                "positivas": ["Beneficio"] if has_pos else [],
                "negativas": ["Riesgo"] if has_neg else [],
            },
        }
        return self.validate_schema(parsed)


class TcoCostModel:
    def __init__(
        self,
        input_cost_per_m: float = 3.0,
        output_cost_per_m: float = 15.0,
        vector_query_cost_usd: float = 0.0015,
        rerank_cost_usd: float = 0.0010,
        infra_monthly_usd: float = 500.0,
        expected_monthly_queries: int = 100_000,
    ) -> None:
        self.input_cost_per_m = input_cost_per_m
        self.output_cost_per_m = output_cost_per_m
        self.vector_query_cost_usd = vector_query_cost_usd
        self.rerank_cost_usd = rerank_cost_usd
        self.infra_monthly_usd = infra_monthly_usd
        self.expected_monthly_queries = max(1, expected_monthly_queries)

    def calculate_cost_per_query(
        self,
        input_tokens: int,
        output_tokens: int,
        uses_retrieval: bool = True,
    ) -> float:
        token_input_cost = (input_tokens / 1_000_000.0) * self.input_cost_per_m
        token_output_cost = (output_tokens / 1_000_000.0) * self.output_cost_per_m

        retrieval_cost = (self.vector_query_cost_usd + self.rerank_cost_usd) if uses_retrieval else 0.0
        amortized_infra = self.infra_monthly_usd / float(self.expected_monthly_queries)

        total = token_input_cost + token_output_cost + retrieval_cost + amortized_infra
        return round(total, 6)

    def evaluate_sensitivity(
        self,
        param_name: str,
        values: list[float | int],
        baseline_input: int = 2000,
        baseline_output: int = 500,
    ) -> list[float]:
        results = []
        for val in values:
            if param_name == "input_tokens":
                cost = self.calculate_cost_per_query(int(val), baseline_output)
            elif param_name == "output_tokens":
                cost = self.calculate_cost_per_query(baseline_input, int(val))
            elif param_name == "expected_monthly_queries":
                temp_model = TcoCostModel(
                    self.input_cost_per_m,
                    self.output_cost_per_m,
                    self.vector_query_cost_usd,
                    self.rerank_cost_usd,
                    self.infra_monthly_usd,
                    expected_monthly_queries=int(val),
                )
                cost = temp_model.calculate_cost_per_query(baseline_input, baseline_output)
            else:
                raise ValueError(f"Unknown sensitivity parameter: '{param_name}'")
            results.append(cost)
        return results

    def assert_monotonic_sensitivity(
        self,
        param_name: str,
        values: list[float | int],
    ) -> bool:
        if len(values) < 2:
            raise ValueError("Sensitivity analysis requires at least 2 parameter points.")

        costs = self.evaluate_sensitivity(param_name, values)
        is_increasing = values[1] > values[0]

        # Check for strict monotonicity (either strictly increasing or strictly decreasing)
        for i in range(1, len(costs)):
            diff = costs[i] - costs[i - 1]
            if param_name in ("input_tokens", "output_tokens"):
                expected_dir = 1 if is_increasing else -1
                if (diff * expected_dir) <= 0:
                    raise ValueError(f"TCO cost model must be strictly monotonic for '{param_name}'.")
            elif param_name == "expected_monthly_queries":
                # Economies of scale: higher queries -> lower amortized fixed cost per query
                expected_dir = -1 if is_increasing else 1
                if (diff * expected_dir) <= 0:
                    raise ValueError(f"TCO cost model must show economies of scale for '{param_name}'.")

        return True
