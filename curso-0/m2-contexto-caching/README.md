# Laboratorio M2 — Contexto, Caching y Contratos (Curso 0)

## Objetivos del Laboratorio

1. Diseñar estructuras de prompt *cache-friendly* serializadas byte a byte con prefijo inmutable y variables volátiles al final.
2. Modelar el punto de equilibrio (*break-even*) económico de prompt caching considerando recargo de escritura y descuento de lectura sobre tablas de precios versionadas.
3. Implementar un validador de tres capas desacopladas (Sintaxis → Esquema → Semántica de Negocio) que prevenga alucinaciones estructurales.
4. Ejecutar el ciclo de herramientas `tool_use` → `tool_result` validando argumentos antes de la invocación sin fugas de excepciones no controladas.

## Estructura de Entrega

- `solution.py`: Contiene `PromptCacheSerializer`, `PromptCacheEconomics`, `ThreeLayerValidator` y `ToolExecutionEngine`.
- `tests/test_m2_contracts.py`: Batería de pruebas deterministas públicas contra `labkit`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-0/m2-contexto-caching/tests/test_m2_contracts.py
```
