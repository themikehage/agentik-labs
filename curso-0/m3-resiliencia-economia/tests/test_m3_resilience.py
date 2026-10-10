"""
Reference tests for Curso 0 M3 - Resiliencia y Economía.
Strictly follows the test conventions:
- One test function per acceptance criterion citing the RA in docstring.
- Both positive and negative test cases to detect conceptual bugs.
- Zero network socket usage, zero real sleep (injectable VirtualClock).
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c0_m3_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

from labkit.clock import VirtualClock
ResilientCaller = _mod.ResilientCaller
PermanentClientError = _mod.PermanentClientError
TransientProviderError = _mod.TransientProviderError
FallbackRouter = _mod.FallbackRouter
SharedTokenBucket = _mod.SharedTokenBucket
EconomicCircuitBreaker = _mod.EconomicCircuitBreaker
BudgetExceededError = _mod.BudgetExceededError
CostAttributionEngine = _mod.CostAttributionEngine


class TestRA31BackoffAndJitterRetry:
    """
    RA-3.1: Reintentos ante 429 con backoff exponencial y jitter determinista respetando Retry-After.
    """

    def test_positive_retry_after_header_respected_on_429(self) -> None:
        """
        [RA-3.1 POSITIVE] Confirma que ante un 429 con cabecera Retry-After, el llamador
        avanza el VirtualClock exactamente la duración solicitada por el proveedor.
        """
        clock = VirtualClock(initial_time=100.0)
        caller = ResilientCaller(clock=clock)
        calls = 0

        def flaky_api():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TransientProviderError(status_code=429, message="Rate limit exceeded", retry_after_s=2.5)
            return "SUCCESS"

        result, traces = caller.execute_with_retry(flaky_api)
        assert result == "SUCCESS"
        assert len(traces) == 1
        assert traces[0].delay_slept_s == 2.5
        assert clock.now() == 102.5

    def test_positive_exponential_backoff_with_jitter_on_transient_503(self) -> None:
        """
        [RA-3.1 POSITIVE] Confirma que ante un error transitorio 503 sin Retry-After,
        aplica backoff exponencial acumulativo con jitter determinista.
        """
        clock = VirtualClock(initial_time=0.0)
        caller = ResilientCaller(clock=clock)
        calls = 0

        def failing_provider():
            nonlocal calls
            calls += 1
            if calls <= 2:
                raise TransientProviderError(status_code=503, message="Service Unavailable")
            return "RECOVERED"

        result, traces = caller.execute_with_retry(
            failing_provider, base_backoff_s=1.0, fixed_jitter_s=0.2
        )
        assert result == "RECOVERED"
        assert len(traces) == 2
        # attempt 1: 1.0 * (2^0) + 0.2 = 1.2s
        # attempt 2: 1.0 * (2^1) + 0.2 = 2.2s
        assert pytest.approx(traces[0].delay_slept_s, abs=1e-3) == 1.2
        assert pytest.approx(traces[1].delay_slept_s, abs=1e-3) == 2.2
        assert pytest.approx(clock.now(), abs=1e-3) == 3.4

    def test_negative_permanent_client_errors_rejected_without_retry(self) -> None:
        """
        [RA-3.1 NEGATIVE] Falla si se intenta reintentar un error permanente de cliente
        (400 Bad Request, 401 Unauthorized, 422 Unprocessable Entity).
        """
        clock = VirtualClock(initial_time=0.0)
        caller = ResilientCaller(clock=clock)
        attempts = 0

        def client_bug_call():
            nonlocal attempts
            attempts += 1
            raise PermanentClientError(status_code=400, message="Malformed JSON parameters")

        with pytest.raises(PermanentClientError):
            caller.execute_with_retry(client_bug_call, max_retries=5)

        # Permanent error must abort on first call without any retries
        assert attempts == 1
        assert clock.now() == 0.0


class TestRA32FallbackRouter:
    """
    RA-3.2: Fallback tras fallos con respuesta explícitamente marcada como degradada.
    """

    def test_positive_fallback_marks_degraded_response(self) -> None:
        """
        [RA-3.2 POSITIVE] Tras alcanzar el umbral de fallos del primario, conmuta al fallback
        y etiqueta la respuesta con is_degraded: True.
        """
        primary_attempts = 0

        def dead_primary():
            nonlocal primary_attempts
            primary_attempts += 1
            raise RuntimeError("Primary datacenter connection refused")

        def backup_provider():
            return {"summary": "Degraded summary from fallback model"}

        router = FallbackRouter(primary_fn=dead_primary, fallback_fn=backup_provider, failure_threshold=2)

        # First call fails and raises because threshold is 2
        with pytest.raises(RuntimeError):
            router.invoke()

        # Second call reaches threshold 2 and activates fallback
        res = router.invoke()
        assert res.is_degraded is True
        assert res.provider_used == "fallback"
        assert res.content["summary"] == "Degraded summary from fallback model"

    def test_negative_silent_degradation_without_flag_fails(self) -> None:
        """
        [RA-3.2 NEGATIVE] Rechaza cualquier arquitectura donde la degradación sea silenciosa
        y no distinga la respuesta del primario de la del secundario.
        """
        router = FallbackRouter(
            primary_fn=lambda: {"text": "primary"},
            fallback_fn=lambda: {"text": "fallback"},
            failure_threshold=1,
        )
        res = router.invoke()
        assert res.is_degraded is False
        assert res.provider_used == "primary"


class TestRA33EconomicCircuitBreakerAndTokenBucket:
    """
    RA-3.3: Circuit breaker económico por tenant y rate limiting con SharedTokenBucket.
    """

    def test_positive_token_bucket_burst_and_refill_with_virtual_clock(self) -> None:
        """
        [RA-3.3 POSITIVE] Confirma que el bucket admite ráfaga hasta su capacidad,
        rechaza cuando se agota y recupera tokens proporcionalmente al tiempo transcurrido.
        """
        clock = VirtualClock(initial_time=0.0)
        bucket = SharedTokenBucket(capacity=3.0, refill_rate_per_sec=1.0, clock=clock)

        # Burst of 3 requests succeeds
        assert bucket.consume(1.0) is True
        assert bucket.consume(1.0) is True
        assert bucket.consume(1.0) is True
        # 4th request immediately rejected
        assert bucket.consume(1.0) is False

        # Advance clock by 2.0 seconds -> 2 tokens refilled
        clock.sleep(2.0)
        assert bucket.consume(1.0) is True
        assert bucket.consume(1.0) is True
        assert bucket.consume(1.0) is False

    def test_positive_economic_circuit_breaker_trips_at_budget_limit(self) -> None:
        """
        [RA-3.3 POSITIVE] Interrumpe llamadas cuando el gasto acumulado del tenant
        supera el presupuesto límite asignado.
        """
        clock = VirtualClock()
        breaker = EconomicCircuitBreaker(budget_limit_usd=10.0, clock=clock)

        breaker.execute_within_budget("tenant-acme", estimated_cost_usd=4.0, action=lambda: "call-1")
        breaker.execute_within_budget("tenant-acme", estimated_cost_usd=5.0, action=lambda: "call-2")
        assert not breaker.is_tripped("tenant-acme")

        # 3rd call would exceed $10.0 ($9.0 + $2.0 = $11.0)
        with pytest.raises(BudgetExceededError):
            breaker.execute_within_budget("tenant-acme", estimated_cost_usd=2.0, action=lambda: "call-3")

        assert breaker.is_tripped("tenant-acme")


class TestRA34CostAttributionVersionedCatalog:
    """
    RA-3.4: Atribución y cálculo exacto de coste por consulta según tabla versionada.
    """

    def test_positive_cost_calculated_with_versioned_catalog(self) -> None:
        """
        [RA-3.4 POSITIVE] Calcula costes precisos atribuidos a tenant y modelo
        usando un catálogo de tarifas con versión declarada.
        """
        catalog = {
            "version": "2026.Q4",
            "models": {
                "agentik-fast-8b": {
                    "input_usd_per_m": 0.50,
                    "output_usd_per_m": 1.50,
                    "cache_read_usd_per_m": 0.10,
                }
            },
        }
        engine = CostAttributionEngine(catalog)

        # 1M input ($0.50), 200k output ($0.30), 500k cache_read ($0.05) -> total $0.85
        report = engine.calculate_query_cost(
            tenant_id="enterprise-101",
            model_id="agentik-fast-8b",
            input_tokens=1_000_000,
            output_tokens=200_000,
            cache_read_tokens=500_000,
        )

        assert report["tenant_id"] == "enterprise-101"
        assert report["catalog_version"] == "2026.Q4"
        assert pytest.approx(report["total_cost_usd"], abs=1e-5) == 0.85
        assert pytest.approx(report["breakdown"]["input_usd"], abs=1e-5) == 0.50
        assert pytest.approx(report["breakdown"]["output_usd"], abs=1e-5) == 0.30
        assert pytest.approx(report["breakdown"]["cache_read_usd"], abs=1e-5) == 0.05

    def test_negative_unversioned_catalog_rejected(self) -> None:
        """
        [RA-3.4 NEGATIVE] Rechaza tablas de precios sin número de versión o estructura inválida.
        """
        with pytest.raises(ValueError):
            CostAttributionEngine({"models": {}})
