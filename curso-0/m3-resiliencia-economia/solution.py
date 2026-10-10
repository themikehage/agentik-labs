from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from labkit.clock import Clock, RealClock


class PermanentClientError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code


class TransientProviderError(Exception):
    def __init__(self, status_code: int, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.retry_after_s = retry_after_s


class BudgetExceededError(Exception):
    pass


@dataclass
class RetryAttemptTrace:
    attempt: int
    delay_slept_s: float
    reason: str


class ResilientCaller:
    NON_RETRYABLE_CODES = {400, 401, 403, 404, 422}

    def __init__(self, clock: Clock | None = None) -> None:
        self.clock: Clock = clock or RealClock()

    def execute_with_retry(
        self,
        operation: Callable[[], Any],
        max_retries: int = 3,
        base_backoff_s: float = 0.5,
        max_backoff_s: float = 10.0,
        fixed_jitter_s: float = 0.1,
    ) -> tuple[Any, list[RetryAttemptTrace]]:
        traces: list[RetryAttemptTrace] = []
        attempt = 0

        while True:
            try:
                result = operation()
                return result, traces
            except PermanentClientError as err:
                raise err
            except TransientProviderError as err:
                if attempt >= max_retries:
                    raise err

                attempt += 1
                if err.retry_after_s is not None and err.retry_after_s > 0:
                    delay = err.retry_after_s
                    reason = f"Retry-After header ({delay}s)"
                else:
                    delay = min(max_backoff_s, base_backoff_s * (2 ** (attempt - 1)) + fixed_jitter_s)
                    reason = f"Exponential backoff attempt {attempt}"

                self.clock.sleep(delay)
                traces.append(RetryAttemptTrace(attempt=attempt, delay_slept_s=delay, reason=reason))


@dataclass
class FallbackResponse:
    content: Any
    is_degraded: bool
    provider_used: str
    failure_count_primary: int


class FallbackRouter:
    def __init__(
        self,
        primary_fn: Callable[[], Any],
        fallback_fn: Callable[[], Any],
        failure_threshold: int = 2,
    ) -> None:
        self.primary_fn = primary_fn
        self.fallback_fn = fallback_fn
        self.failure_threshold = failure_threshold
        self._consecutive_failures = 0

    def invoke(self) -> FallbackResponse:
        try:
            res = self.primary_fn()
            self._consecutive_failures = 0
            return FallbackResponse(
                content=res,
                is_degraded=False,
                provider_used="primary",
                failure_count_primary=0,
            )
        except Exception:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold:
                fallback_res = self.fallback_fn()
                return FallbackResponse(
                    content=fallback_res,
                    is_degraded=True,
                    provider_used="fallback",
                    failure_count_primary=self._consecutive_failures,
                )
            raise


class SharedTokenBucket:
    def __init__(
        self,
        capacity: float,
        refill_rate_per_sec: float,
        clock: Clock | None = None,
    ) -> None:
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate = float(refill_rate_per_sec)
        self.clock: Clock = clock or RealClock()
        self.last_refill = self.clock.now()

    def consume(self, amount: float = 1.0) -> bool:
        now = self.clock.now()
        elapsed = now - self.last_refill
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class EconomicCircuitBreaker:
    def __init__(
        self,
        budget_limit_usd: float,
        clock: Clock | None = None,
    ) -> None:
        self.budget_limit_usd = float(budget_limit_usd)
        self.clock: Clock = clock or RealClock()
        self._spend_by_tenant: dict[str, float] = {}
        self._tripped_tenants: set[str] = set()

    def record_spend(self, tenant_id: str, amount_usd: float) -> None:
        current = self._spend_by_tenant.get(tenant_id, 0.0)
        new_total = round(current + amount_usd, 6)
        self._spend_by_tenant[tenant_id] = new_total
        if new_total >= self.budget_limit_usd:
            self._tripped_tenants.add(tenant_id)

    def is_tripped(self, tenant_id: str) -> bool:
        return (
            tenant_id in self._tripped_tenants
            or self._spend_by_tenant.get(tenant_id, 0.0) >= self.budget_limit_usd
        )

    def execute_within_budget(
        self,
        tenant_id: str,
        estimated_cost_usd: float,
        action: Callable[[], Any],
    ) -> Any:
        current = self._spend_by_tenant.get(tenant_id, 0.0)
        if current + estimated_cost_usd > self.budget_limit_usd:
            self._tripped_tenants.add(tenant_id)
            raise BudgetExceededError(
                f"Economic circuit breaker tripped for tenant '{tenant_id}'. "
                f"Current spend: ${current:.4f}, Limit: ${self.budget_limit_usd:.4f}"
            )
        result = action()
        self.record_spend(tenant_id, estimated_cost_usd)
        return result


class CostAttributionEngine:
    def __init__(self, versioned_catalog: dict[str, Any]) -> None:
        if "version" not in versioned_catalog or "models" not in versioned_catalog:
            raise ValueError("Catalog must be versioned and contain 'models' definition.")
        self.catalog = versioned_catalog
        self.version = versioned_catalog["version"]
        self.models = versioned_catalog["models"]

    def calculate_query_cost(
        self,
        tenant_id: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
    ) -> dict[str, Any]:
        if model_id not in self.models:
            raise KeyError(f"Model '{model_id}' not found in pricing catalog version {self.version}")

        rates = self.models[model_id]
        in_cost = (input_tokens / 1_000_000.0) * rates["input_usd_per_m"]
        out_cost = (output_tokens / 1_000_000.0) * rates["output_usd_per_m"]
        cache_cost = (cache_read_tokens / 1_000_000.0) * rates.get("cache_read_usd_per_m", 0.0)
        total = in_cost + out_cost + cache_cost

        return {
            "tenant_id": tenant_id,
            "model_id": model_id,
            "catalog_version": self.version,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "total_cost_usd": round(total, 6),
            "breakdown": {
                "input_usd": round(in_cost, 6),
                "output_usd": round(out_cost, 6),
                "cache_read_usd": round(cache_cost, 6),
            },
        }
