# Laboratorio M2 — Criterio de Solución, Buy vs Build y TCO (Curso 3)

## Objetivos del Laboratorio

1. **RA-2.1**: Clasificar y seleccionar la arquitectura técnica adecuada fundamentando la elección en el descarte explícito de alternativas con sus modos de fallo correspondientes (p. ej. obsolescencia de conocimiento en *fine-tuning* o latencia/coste en *long-context* no cacheable).
2. **RA-2.2**: Identificar al menos dos modos de fallo exclusivos de arquitecturas RAG (retrieval erróneo, conflicto entre fuentes, citación espuria) y asociar mitigaciones verificables, desmontando la falsa creencia de que RAG elimina las alucinaciones.
3. **RA-2.3**: Validar decisiones de arquitectura (`adr.md`) contra el estándar canónico MADR 3.x (*Markdown Architectural Decision Records*), exigiendo estado, contexto, decisión activa, opciones consideradas con pros/contras y consecuencias obligatorias tanto positivas como negativas.
4. **RA-2.4**: Modelar analíticamente el Coste Total de Propiedad (TCO) por consulta considerando tokens de entrada, salida, almacenamiento vectorial y llamadas a herramientas, demostrando sensibilidad monótona ante parámetros de escalado.

## Estructura de Entrega

- `solution.py`: Contiene `SolutionEvaluator`, `RagFailureModeAnalyzer`, `MadrAdrValidator` y `TcoCostModel`.
- `tests/test_m2_decision.py`: Pruebas de aceptación deterministas y validación de trampas conceptuales.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-3/m2-decision/tests/test_m2_decision.py
```
