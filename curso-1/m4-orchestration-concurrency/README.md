# Laboratorio M4: Orquestación y Concurrencia

## Objetivos de Aprendizaje (Resultados de Aprendizaje)
- **RA-4.1**: Selección de topología justificada por esquema (`topology_choice.json`) diferenciando partición determinista (`split-and-merge`), descomposición dinámica (`orchestrator-workers`) y consenso (`voting`).
- **RA-4.2**: Canales y reducers conmutativos e invariantes al orden de llegada de escrituras concurrentes en superpasos.
- **RA-4.3**: Coordinación externa mediante Control de Concurrencia Optimista (OCC) con versionado estricto sobre recursos compartidos.
- **RA-4.4**: Bucle generador-evaluador con cotas duras de corrección, diagnóstico explícito de convergencia y esquemas disjuntos por nodo.
- **RA-4.5**: Diagnóstico forense de divergencia identificando la causa raíz (reducer no determinista vs contención en OCC/locks).

## Ejecución de Tests
```bash
uv run pytest -v curso-1/m4-orchestration-concurrency/tests/test_m4_orchestration_concurrency.py
```
