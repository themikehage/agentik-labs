# Laboratorio M1 — De Workflows a Agentes (Curso 1)

## Objetivos del Laboratorio

1. **RA-1.1**: Clasificar tareas complejas en los patrones canónicos de Anthropic (`prompt chaining`, `routing`, `parallelization`, `orchestrator-workers`, `evaluator-optimizer`, `autonomous_agent`), rechazando clasificaciones erróneas como paralelizar tareas con dependencias causales estrictas.
2. **RA-1.2**: Estructurar matrices de decisión arquitectónica fundamentando el descarte de agentes autónomos ante requisitos de determinismo, latencia y predictibilidad presupuestaria.
3. **RA-1.3**: Computar el modelo de costes y distribución estocástica de pasos con Intervalo de Confianza al 95% sobre simulaciones sembradas, descartando multiplicadores estáticos fijos.
4. **RA-1.4**: Ejecutar un arnés ReAct minimal con múltiples condiciones de parada independientes (postcondición externa observable, techo de pasos y presupuesto de tokens/coste).
5. **RA-1.5**: Contrastar empíricamente perfiles de latencia, coste y dispersión entre workflows deterministas y agentes exploratorios bajo idénticas condiciones.

## Estructura de Entrega

- `solution.py`: Implementación de `WorkflowPatternClassifier`, `ArchitectureDecisionMatrix`, `AgentCostDistributionModel` y `MinimalReActHarness`.
- `decision_matrix.json`: Registro estructurado de criterios de selección y descarte.
- `tests/test_m1_workflows_agents.py`: Suite determinista de pruebas de aceptación y verificación negativa de falacias conceptuales.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-1/m1-workflows-agents/tests/test_m1_workflows_agents.py
```
