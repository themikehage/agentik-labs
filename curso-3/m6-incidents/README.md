# Laboratorio M6 — Operaciones, Incidentes y Triage Forense (Curso 3)

## Objetivos del Laboratorio

1. **RA-6.1**: Implementar el protocolo de respuesta ante incidentes críticos (`incident_report.md`), formalizando la estructura de mando (Incident Commander, Comunicaciones, Escriba), declarando severidad y fijando la cadencia de comunicación a clientes.
2. **RA-6.2**: Conducir análisis forense sistemático sobre trazas distribuidas y registros de auditoría (`root_cause.json`), correlacionando `span_id`, componente y categoría causante, distinguiendo deterministamente la causa raíz del síntoma emergente.
3. **RA-6.3**: Validar postmortems bajo cultura *blameless* (`postmortem.md`) conforme al estándar Google SRE, enfocados en fallos de procesos y salvaguardas sistémicas con dueños de acción definidos y descartando cualquier culpabilización individual.
4. **RA-6.4**: Demostrar el ciclo de vida de *regression evals* ejecutables, verificando que la prueba falla deterministamente ante la versión con defecto y pasa con éxito tras la aplicación del *hotfix*, cerrando definitivamente el ciclo del incidente.

## Estructura de Entrega

- `solution.py`: Contiene `IncidentReportValidator`, `ForensicTraceAnalyzer`, `BlamelessPostmortemValidator` y `RegressionLifecycleManager`.
- `tests/test_m6_incidents.py`: Batería de pruebas de respuesta a incidentes, análisis forense de spans y regresión.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-3/m6-incidents/tests/test_m6_incidents.py
```
