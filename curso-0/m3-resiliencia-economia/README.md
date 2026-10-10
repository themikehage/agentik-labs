# Laboratorio M3 — Resiliencia y Economía (Curso 0)

## Objetivos del Laboratorio

1. Implementar reintentos deterministas ante errores transitorios (`429`, `503`) con *backoff* exponencial y *jitter*, respetando la cabecera `Retry-After` mediante `VirtualClock`.
2. Evitar la amplificación de carga prohibiendo estrictamente el reintento de errores permanentes de cliente (`400`, `401`, `422`).
3. Construir un router de *fallback* ante caídas del proveedor primario con marcado explícito e ineludible de degradación (`is_degraded: True`).
4. Implementar un *circuit breaker* económico por tenant y un *rate limiter* basado en `TokenBucket`.
5. Atribuir costes exactos por consulta y tenant utilizando catálogos de precios versionados.

## Estructura de Entrega

- `solution.py`: Contiene `ResilientCaller`, `FallbackRouter`, `SharedTokenBucket`, `EconomicCircuitBreaker` y `CostAttributionEngine`.
- `tests/test_m3_resilience.py`: Batería de pruebas deterministas públicas contra `labkit`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-0/m3-resiliencia-economia/tests/test_m3_resilience.py
```
