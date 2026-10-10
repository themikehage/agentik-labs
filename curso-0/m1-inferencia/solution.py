from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence
from labkit.clock import Clock, RealClock
from labkit.llm import LLMStreamChunk
from labkit.tokenizer import OfflineTokenizer


@dataclass
class LatencyProfileResult:
    ttft_seconds: float
    tpot_seconds: float
    itl_p50_seconds: float
    itl_p95_seconds: float
    total_e2e_seconds: float
    token_count: int
    phases: list[dict[str, Any]] = field(default_factory=list)


def _calculate_percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (percentile / 100.0) * (len(sorted_values) - 1)
    low_idx = int(math.floor(rank))
    high_idx = int(math.ceil(rank))
    weight = rank - low_idx
    return sorted_values[low_idx] * (1.0 - weight) + sorted_values[high_idx] * weight


class LatencyProfiler:
    """Profiles streaming inference metrics with clock injection."""

    def __init__(self, clock: Clock | None = None) -> None:
        self.clock: Clock = clock or RealClock()

    def profile_stream(self, stream_chunks: Iterable[LLMStreamChunk | str]) -> LatencyProfileResult:
        start_time = self.clock.now()
        first_token_time: float | None = None
        last_chunk_time: float = start_time

        itl_intervals: list[float] = []
        phases: list[dict[str, Any]] = []
        token_count = 0

        for chunk in stream_chunks:
            current_time = self.clock.now()
            token_count += 1

            if first_token_time is None:
                first_token_time = current_time
                ttft = current_time - start_time
                phases.append({
                    "phase": "prefill",
                    "metric": "TTFT",
                    "duration_seconds": ttft,
                    "token_index": 1,
                })
            else:
                interval = current_time - last_chunk_time
                itl_intervals.append(interval)
                phases.append({
                    "phase": "decode",
                    "metric": "ITL",
                    "duration_seconds": interval,
                    "token_index": token_count,
                })

            last_chunk_time = current_time

        end_time = self.clock.now()
        total_e2e = end_time - start_time

        if first_token_time is None:
            ttft = total_e2e
        else:
            ttft = first_token_time - start_time

        if itl_intervals:
            tpot = sum(itl_intervals) / len(itl_intervals)
            sorted_itls = sorted(itl_intervals)
            p50 = _calculate_percentile(sorted_itls, 50.0)
            p95 = _calculate_percentile(sorted_itls, 95.0)
        else:
            tpot = 0.0
            p50 = 0.0
            p95 = 0.0

        return LatencyProfileResult(
            ttft_seconds=ttft,
            tpot_seconds=tpot,
            itl_p50_seconds=p50,
            itl_p95_seconds=p95,
            total_e2e_seconds=total_e2e,
            token_count=token_count,
            phases=phases,
        )


def generate_tokenization_report(tokenizer: OfflineTokenizer) -> dict[str, Any]:
    text_en = "Artificial intelligence and multi-agent systems are transforming software engineering in 2026."
    text_es = "La inteligencia artificial y los sistemas multiagente están transformando la ingeniería de software en 2026."

    json_payload = '{"status": "ok", "agent_id": "m1-worker", "tokens_processed": 1420, "is_verified": true}'
    prose_equivalent = "status is ok, agent id is m1-worker, tokens processed is 1420, and is verified is true."

    tokens_en = tokenizer.count_tokens(text_en)
    tokens_es = tokenizer.count_tokens(text_es)
    tokens_json = tokenizer.count_tokens(json_payload)
    tokens_prose = tokenizer.count_tokens(prose_equivalent)

    return {
        "english": {"text": text_en, "token_count": tokens_en, "word_count": len(text_en.split())},
        "spanish": {"text": text_es, "token_count": tokens_es, "word_count": len(text_es.split())},
        "json": {"text": json_payload, "token_count": tokens_json},
        "prose": {"text": prose_equivalent, "token_count": tokens_prose},
        "spanish_inflation_ratio": tokens_es / max(1, tokens_en),
    }


def explain_non_determinism() -> dict[str, Any]:
    return {
        "temperature_zero_guarantee": False,
        "primary_root_cause": "continuous_batching_concurrency",
        "mechanism": (
            "Concurrent continuous batching groups dynamic requests together on GPU streaming multiprocessors. "
            "Because floating point addition is non-associative in parallel reduction kernels, changing the other "
            "prompts sharing the batch alters rounding errors, causing token divergences even when temperature=0."
        ),
        "seed_guarantee": "best-effort across distributed inference engines",
    }
