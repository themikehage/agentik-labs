# Laboratorio M5 — Guardrails y SLOs (Curso 3)

## Objetivos del Laboratorio

1. **RA-5.1**: Configurar arquitecturas de salvaguarda (NeMo Guardrails / Colang) con flujos de entrada y salida, declarando presupuestos de latencia diferenciados por tipo (milisegundos para comprobaciones deterministas; cientos de milisegundos para *self-check rails* basados en LLM), descartando el mito de que todos los rails corren en "< 15 ms".
2. **RA-5.2**: Medir empíricamente el rendimiento de los guardrails sobre datasets adversariales (`guardrail_eval.py`), reportando *True Positive Rate* (TPR) y *False Positive Rate* (FPR) acotado con Intervalo de Confianza (IC 95%), desterrando la afirmación irreal de "bloqueo del 100% de jailbreaks".
3. **RA-5.3**: Especificar formalmente compromisos de servicio (`slo.yaml`), separando inequívocamente SLI (medida observable), SLO (objetivo interno) y SLA (compromiso contractual con penalización) y asociando una política ejecutable de congelación por *error budget*.
4. **RA-5.4**: Ejecutar un *gate* de aceptación y regresión (`acceptance.md`) que compare métricas contra el *golden set* del cliente y bloquee el pase a producción si se produce una regresión en casos de prueba históricos.

## Estructura de Entrega

- `solution.py`: Contiene `GuardrailsConfigValidator`, `GuardrailEvaluator`, `SloSpecValidator` y `AcceptanceGate`.
- `tests/test_m5_guardrails.py`: Batería de pruebas deterministas y verificación de trampas conceptuales de latencia y SLA.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-3/m5-guardrails/tests/test_m5_guardrails.py
```
