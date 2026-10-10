# Laboratorio M1 — Fundamentos de Inferencia y Latencia (Curso 0)

## Objetivos del Laboratorio

1. Implementar un `LatencyProfiler` determinista para flujos de inferencia en *streaming* usando el reloj inyectable de `labkit`.
2. Medir con precisión matemática el **Time To First Token (TTFT)** y la distribución de **Inter-Token Latency (ITL)** (P50, P95).
3. Evaluar el impacto de la tokenización BPE offline en diferentes idiomas (Español vs Inglés) y estructuras de datos (JSON vs texto plano).
4. Comprender las causas reales del no determinismo a nivel de infraestructura (*batching* concurrente en GPU vs muestreo estocástico).

## Estructura de Entrega

- `solution.py`: Contiene `LatencyProfiler`, `TokenizationReport`, y el análisis de no determinismo.
- `tests/test_m1_inference.py`: Batería de pruebas deterministas públicas contra `labkit`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-0/m1-inferencia/tests/test_m1_inference.py
```
