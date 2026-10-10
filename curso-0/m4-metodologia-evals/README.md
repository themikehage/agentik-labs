# Laboratorio M4 — Metodología de Evals (Curso 0)

## Objetivos del Laboratorio

1. Construir un dataset de evaluación de 20 a 50 tareas con balance metodológico declarado entre capacidades (*capability*) y regresiones (*regression*).
2. Desarrollar un *grader* de *outcome* observable que evalúe el estado real de la infraestructura (archivos, base de datos) y suspenda sistemas que simulen en el texto haber completado la acción (*transcript fraud*).
3. Calcular de forma programática e insesgada las métricas `pass@k` (recuperación) y `pass^k` (consistencia en flujos desatendidos) sobre `SimClient`.
4. Comparar versiones de agentes mediante pruebas pareadas e intervalos de confianza al 95% obtenidos por *bootstrap*, evitando decisiones basadas únicamente en diferencias de medias muestrales ruidosas.

## Estructura de Entrega

- `solution.py`: Contiene `EvaluationDataset`, `OutcomeGrader`, `UnbiasedPassMetrics` y `BootstrapPairedComparator`.
- `tests/test_m4_evals.py`: Batería de pruebas deterministas públicas contra `labkit`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-0/m4-metodologia-evals/tests/test_m4_evals.py
```
