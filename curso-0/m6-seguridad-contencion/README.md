# Laboratorio M6 — Seguridad y Contención (Curso 0)

## Objetivos del Laboratorio

1. Mapear escenarios de riesgo enterprise contra los identificadores oficiales de OWASP Top 10 for LLM Applications 2025 (LLM01 a LLM10), distinguiendo explícitamente LLM06 (*Excessive Agency*) de LLM10 (*Unbounded Consumption*).
2. Evaluar cuantitativamente las defensas léxicas (regex y delimitadores XML), demostrando que reducen frecuencia pero nunca eliminan la inyección (TPR < 100%).
3. Romper la "Trifecta Letal" de Simón Willison mediante contención de arquitectura: bloquear el canal de *egress* para garantizar que una inyección indirecta no pueda exfiltrar datos privados.
4. Validar las políticas de ejecución segura en contenedores (`HardenedSandbox`) con aislamiento estricto (`--network none`, `--read-only`, `--cap-drop ALL`, usuario no root UID 10001 y bloqueo de metadatos `169.254.169.254`).

## Estructura de Entrega

- `solution.py`: Contiene `OWASP2025Catalog`, `LexicalDefenseEvaluator`, `LethalTrifectaArchitect` y `HardenedSandboxPolicy`.
- `tests/test_m6_containment.py`: Batería de pruebas deterministas públicas contra `labkit`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-0/m6-seguridad-contencion/tests/test_m6_containment.py
```
