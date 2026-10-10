# Laboratorio M4 — Clientes y Conformidad MCP (Curso 2)

## Objetivos del Laboratorio

1. Implementar un cliente MCP conforme a la revisión `2026-07-28` que inyecta metadatos canónicos en `_meta` en cada petición.
2. Gestionar la negociación de versiones mediante `server/discover` y rechazar servidores incompatibles de forma controlada (`IncompatibleServerVersionError`).
3. Implementar el despacho polimórfico de `resultType`, tratando la ausencia del discriminador como `"complete"` por compatibilidad hacia atrás.
4. Ejecutar una suite de pruebas de conformidad automatizada con aislamiento total de red sobre `pytest-socket`.

## Estructura de Entrega

- `solution.py`: Contiene `MCPClient`, `IncompatibleServerVersionError`, y `ConformanceRunner`.
- `tests/test_m4_clients_conformance.py`: Suite de tests deterministas sobre `pytest-socket`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-2/m4-clients-conformance/tests/test_m4_clients_conformance.py
```
