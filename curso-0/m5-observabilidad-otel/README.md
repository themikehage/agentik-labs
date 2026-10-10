# Laboratorio M5 — Observabilidad OTel GenAI (Curso 0)

## Objetivos del Laboratorio

1. Instrumentar clientes de inferencia con la convención semántica vigente de OpenTelemetry GenAI (`gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`).
2. Desterrar atributos obsoletos como `gen_ai.system` y prohibir la inclusión de costes monetarios en los atributos de span.
3. Emitir spans con discriminación estricta de tokens de entrada, salida y tokens servidos desde caché (`gen_ai.usage.cache_read.input_tokens`).
4. Calcular el coste monetario exclusivamente en el backend/pipeline de observabilidad.
5. Aplicar políticas de privacidad *opt-in* para el contenido de prompts y redacción rigurosa de PII/credenciales.

## Estructura de Entrega

- `solution.py`: Contiene `OTelGenAISpan`, `OTelGenAITracer`, `InMemorySpanExporter`, `PipelineCostCalculator` y `PIISanitizer`.
- `tests/test_m5_otel_genai.py`: Batería de pruebas deterministas públicas contra `labkit`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-0/m5-observabilidad-otel/tests/test_m5_otel_genai.py
```
