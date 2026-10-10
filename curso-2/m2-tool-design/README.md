# Laboratorio M2 — Diseño de Herramientas y Esquemas MCP (Curso 2)

## Objetivos del Laboratorio

1. Diseñar esquemas de herramientas estrictos con validación de `inputSchema` (`additionalProperties: false`) y `outputSchema`.
2. Producir `structuredContent` validado por el servidor contra su `outputSchema`, bloqueando dereferenciación de `$ref` de red externo.
3. Construir un `ToolCatalogProfiler` con `OfflineTokenizer` que mida con rigor científico el impacto en tokens de la divulgación progresiva.
4. Distinguir semánticamente los errores de ejecución (`isError: true` accionable) de los errores de protocolo JSON-RPC (`-32601`).

## Estructura de Entrega

- `solution.py`: Contiene `ToolRegistry`, `ToolCatalogProfiler`, y los esquemas de herramientas.
- `tests/test_m2_tool_design.py`: Suite de tests deterministas sobre `pytest-socket`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-2/m2-tool-design/tests/test_m2_tool_design.py
```
