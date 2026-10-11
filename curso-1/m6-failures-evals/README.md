# Laboratorio M6: Fallos, Seguridad y Evals de Agentes

## Objetivos de Aprendizaje (Resultados de Aprendizaje)
- **RA-6.1**: Clasificación sistémica de incidentes según la taxonomía MAST (`mast_classify.json`) distinguiendo causas de especificación (`SPECIFICATION`), coordinación (`COORDINATION`) y verificación (`VERIFICATION`).
- **RA-6.2**: Tratamiento crítico y honesto de benchmarks de recuperación (OrchestraBench) citando expresamente sus caveats metodológicos.
- **RA-6.3**: Post-condition graders que evalúan el estado observable en el entorno para detectar fallos silenciosos.
- **RA-6.4**: Evaluación de contención y seguridad inter-agente midiendo TPR y FPR sobre dataset de inyecciones y tool poisoning.
- **RA-6.5**: Arnés de evals de agentes reportando los 4 ejes (trayectoria, herramientas, resultado final, coste) y consistencia estricta `pass^k` con intervalo de confianza al 95%.

## Ejecución de Tests
```bash
uv run pytest -v curso-1/m6-failures-evals/tests/test_m6_failures_evals.py
```
