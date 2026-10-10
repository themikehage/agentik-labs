"""
Reference tests for Curso 0 M1 - Fundamentos de Inferencia y Latencia.
Strictly follows the test conventions:
- One test function per acceptance criterion citing the RA in docstring.
- Both positive and negative test cases to detect conceptual bugs.
- Zero network socket usage, zero real sleep (injectable VirtualClock).
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

_lab_dir = Path(__file__).resolve().parent.parent
if str(_lab_dir) not in sys.path:
    sys.path.insert(0, str(_lab_dir))

from labkit.clock import VirtualClock
from labkit.tokenizer import OfflineTokenizer
from solution import (
    LatencyProfiler,
    generate_tokenization_report,
    explain_non_determinism,
)


def _simulate_stream_generator(clock: VirtualClock, ttft_s: float, itl_delays: list[float]):
    # Generator that simulates streaming deltas while advancing VirtualClock
    clock.sleep(ttft_s)
    yield "First"
    for delay in itl_delays:
        clock.sleep(delay)
        yield "token"


class TestRA11StreamingMetrics:
    """
    RA-1.1: El estudiante debe medir TTFT y TPOT distinguiendo prefill de decode.
    """

    def test_positive_ttft_and_tpot_calculation(self) -> None:
        """
        [RA-1.1 POSITIVE] Confirma que contra un flujo con latencias programadas,
        el profiler asigna TTFT al primer token, TPOT a la media de intervalos decode,
        y etiqueta correctamente las fases.
        """
        clock = VirtualClock(initial_time=100.0)
        profiler = LatencyProfiler(clock=clock)

        # 0.5s TTFT, then 3 intervals of 0.1s, 0.2s, 0.3s (mean 0.2s)
        gen = _simulate_stream_generator(clock, ttft_s=0.5, itl_delays=[0.1, 0.2, 0.3])
        result = profiler.profile_stream(gen)

        assert pytest.approx(result.ttft_seconds, rel=1e-3) == 0.5
        assert pytest.approx(result.tpot_seconds, rel=1e-3) == 0.2
        assert pytest.approx(result.total_e2e_seconds, rel=1e-3) == 1.1
        assert result.token_count == 4

        # Verify phase labeling
        assert result.phases[0]["phase"] == "prefill"
        assert result.phases[0]["metric"] == "TTFT"
        for p in result.phases[1:]:
            assert p["phase"] == "decode"
            assert p["metric"] == "ITL"

    def test_negative_confusing_ttft_with_mean_itl(self) -> None:
        """
        [RA-1.1 NEGATIVE] Detecta el error conceptual de promediar el TTFT
        dentro de la latencia entre tokens (confundir TTFT con TPOT).
        """
        clock = VirtualClock(initial_time=0.0)
        profiler = LatencyProfiler(clock=clock)

        # High TTFT (2.0s) and fast ITL (0.05s)
        gen = _simulate_stream_generator(clock, ttft_s=2.0, itl_delays=[0.05, 0.05])
        result = profiler.profile_stream(gen)

        # If someone mistakenly reports mean of all intervals as TTFT, this fails
        flawed_average = (2.0 + 0.05 + 0.05) / 3
        assert result.ttft_seconds != pytest.approx(flawed_average, rel=1e-2)
        assert result.ttft_seconds > result.tpot_seconds


class TestRA12OfflineTokenization:
    """
    RA-1.2: El estudiante debe analizar los costes de tokenización BPE offline.
    """

    def test_positive_spanish_and_json_token_inflation(self) -> None:
        """
        [RA-1.2 POSITIVE] Confirma que la tokenización BPE genera mayor conteo de tokens
        en español que en inglés para el mismo contenido semántico, y que JSON consume
        más tokens que prosa debido a delimitadores sintácticos.
        """
        tokenizer = OfflineTokenizer()
        report = generate_tokenization_report(tokenizer)

        assert report["spanish"]["token_count"] > report["english"]["token_count"]
        assert report["spanish_inflation_ratio"] > 1.0
        assert report["json"]["token_count"] > report["prose"]["token_count"]

    def test_negative_word_count_assumption_fails(self) -> None:
        """
        [RA-1.2 NEGATIVE] Falla si se asume erróneamente que 1 palabra equivale a 1 token.
        """
        tokenizer = OfflineTokenizer()
        report = generate_tokenization_report(tokenizer)

        # Word count is not equal to token count
        assert report["spanish"]["word_count"] != report["spanish"]["token_count"]
        assert report["english"]["word_count"] != report["english"]["token_count"]


class TestRA13NonDeterminismFoundations:
    """
    RA-1.3: El estudiante debe identificar las fuentes de no determinismo en inferencia GPU.
    """

    def test_positive_batching_non_associativity_cited(self) -> None:
        """
        [RA-1.3 POSITIVE] Verifica que el análisis técnico cite el batching continuo
        y la no asociatividad aritmética de reducción en coma flotante en GPU.
        """
        explanation = explain_non_determinism()

        assert explanation["temperature_zero_guarantee"] is False
        assert "batching" in explanation["primary_root_cause"]
        assert "floating point" in explanation["mechanism"].lower() or "non-associative" in explanation["mechanism"].lower()

    def test_negative_temperature_zero_guarantee_rejected(self) -> None:
        """
        [RA-1.3 NEGATIVE] Rechaza cualquier afirmación ingenua de determinismo bit-exacto
        únicamente mediante temperature=0.
        """
        explanation = explain_non_determinism()
        assert not explanation["temperature_zero_guarantee"]


class TestRA14TailLatencyPercentiles:
    """
    RA-1.4: El estudiante debe reportar percentiles de cola (P50, P95) de ITL.
    """

    def test_positive_p50_and_p95_percentiles_with_jitter(self) -> None:
        """
        [RA-1.4 POSITIVE] Reporta P50 y P95 con precisión sobre una distribución
        de ITL con jitter asimétrico en la cola.
        """
        clock = VirtualClock(initial_time=0.0)
        profiler = LatencyProfiler(clock=clock)

        # 10 intervals: 9 fast (0.01s) and 1 tail spike (0.50s)
        itls = [0.01] * 9 + [0.50]
        gen = _simulate_stream_generator(clock, ttft_s=0.1, itl_delays=itls)
        result = profiler.profile_stream(gen)

        assert pytest.approx(result.itl_p50_seconds, abs=0.02) == 0.01
        assert result.itl_p95_seconds > 0.20  # Tail latency captures the spike

    def test_negative_mean_fails_to_represent_tail_latency(self) -> None:
        """
        [RA-1.4 NEGATIVE] Demuestra que la media aritmética oculta la degradación de cola
        que el P95 expone claramente.
        """
        clock = VirtualClock(initial_time=0.0)
        profiler = LatencyProfiler(clock=clock)

        itls = [0.01] * 9 + [0.50]
        gen = _simulate_stream_generator(clock, ttft_s=0.1, itl_delays=itls)
        result = profiler.profile_stream(gen)

        assert result.tpot_seconds < result.itl_p95_seconds
