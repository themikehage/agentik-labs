# Laboratorio M3 — Transportes y Asincronía MCP (Curso 2)

## Objetivos del Laboratorio

1. Implementar un gateway con transporte **Streamable HTTP** *stateless* que procesa peticiones concurrentes sin afinidad de sesión (`Mcp-Session-Id` eliminado).
2. Manejar multiplexación de peticiones concurrentes garantizando que las respuestas mapeen estrictamente al `id` del requerimiento JSON-RPC.
3. Asegurar la idempotencia en operaciones de mutación mediante la cabecera `Idempotency-Key`.
4. Diseñar el ciclo de vida de operaciones de larga duración como tareas asíncronas (`tasks/get`, `tasks/update`), rechazando el método deprecado/inexistente `tasks/result`.

## Estructura de Entrega

- `solution.py`: Contiene `StreamableHttpGateway`, `IdempotencyStore`, y `TaskManager`.
- `tests/test_m3_transports.py`: Suite de tests deterministas sobre `pytest-socket`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-2/m3-transports/tests/test_m3_transports.py
```
