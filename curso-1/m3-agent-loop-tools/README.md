# Laboratorio M3 — Bucle del Agente y Herramientas (Curso 1)

## Objetivos del Laboratorio

1. **RA-3.1**: Implementar un arnés de control para agentes con condiciones de parada desacopladas e independientes (éxito verificado por postcondición externa, corte de presupuesto y techo de pasos), garantizando que no se cuelgue ante fallos permanentes de herramientas.
2. **RA-3.2**: Escribir especificaciones formales de herramientas con contratos de tipos, precondiciones obligatorias y directivas explícitas de exclusión mutua ("cuándo NO usarla") para asegurar selección disjunta sin ambigüedad.
3. **RA-3.3**: Transformar errores y excepciones no controladas en respuestas de herramientas estructuradas y accionables para el LLM (causa, sugerencia de corrección y código de error tipado), erradicando la fuga de stack traces crudos.
4. **RA-3.4**: Configurar techos duros de presupuesto monitorizando tokens, llamadas de herramientas y reloj virtual inyectable con `VirtualClock` sin incurrir en `sleep` bloqueante.
5. **RA-3.5**: Detectar de forma determinista la ausencia de progreso y la oscilación en bucle (*loop guards* sobre secuencias A-B-A-B) y clasificar la causa de parada real mediante un diagnosticador formal.

## Estructura de Entrega

- `solution.py`: Contiene `GovernedAgentHarness`, `ToolSpecificationRegistry`, `ActionableErrorTransformer`, `HardBudgetManager` y `LoopGuardDetector`.
- `tests/test_m3_agent_loop_tools.py`: Batería de pruebas deterministas contra fallos de herramientas, presupuestos y bucles oscilantes.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-1/m3-agent-loop-tools/tests/test_m3_agent_loop_tools.py
```
