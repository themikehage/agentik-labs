# Laboratorio M1 — Especificación y Primitivas MCP (Curso 2)

## Objetivos del Laboratorio

1. Implementar un servidor MCP conforme a la revisión `2026-07-28` que procesa peticiones *stateless* sin *handshake* ni *liveness ping*.
2. Exigir `io.modelcontextprotocol/clientCapabilities` en `_meta` en cada petición y rechazar con `-32602` si falta.
3. Exponer el método `server/discover` con versiones soportadas y responder con error `-32022` ante versiones no soportadas.
4. Implementar el patrón **MRTR** (Model-Requested Tool Resumption) con discriminador polimórfico `resultType: "input_required"`.
5. Validar la obsolescencia y migración de capacidades deprecadas (Roots, Sampling, Logging).

## Estructura de Entrega

- `solution.py`: Contiene `MCPServer` y `classify_legacy_features`.
- `tests/test_m1_spec_primitives.py`: Suite de tests deterministas sobre `pytest-socket`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-2/m1-spec-primitives/tests/test_m1_spec_primitives.py
```
