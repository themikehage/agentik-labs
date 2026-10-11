# Laboratorio M2 — Context Engineering, RAG y Memoria Agéntica (Curso 1)

## Objetivos del Laboratorio

1. **RA-2.1**: Gobernar el presupuesto de contexto asignando cuotas estrictas de tokens por nodo mediante inyección Just-In-Time (JIT) y purga de resultados de herramientas obsoletos (*tool result clearing*).
2. **RA-2.2**: Diseñar un compactador determinista de contexto que conserve invariantes críticas (prefijo de directivas inmutable con hash SHA-256 idéntico y variables de estado íntegras), impidiendo truncados no controlados.
3. **RA-2.3**: Implementar un pipeline de recuperación híbrida (BM25 + Dense con fusión RRF $1/(k+\text{rank})$ y reranking), evaluando `recall@k`, `MRR` y `nDCG` sobre un golden set sembrado, con filtrado multi-tenant obligatorio como precondición de búsqueda.
4. **RA-2.4**: Administrar una jerarquía de memoria desacoplada (working, episódica, semántica) con aislamiento estricto por tenant, caducidad temporal (TTL) y rechazo determinista de inyecciones de directivas maliciosas (*memory poisoning*).
5. **RA-2.5**: Conducir diagnóstico forense de degradación de respuestas distinguiendo con precisión fallos de atención (*lost-in-the-middle*), saturación de presupuesto o déficit de recall en retrieval.

## Estructura de Entrega

- `solution.py`: Contiene `ContextBudgetGovernor`, `DeterministicContextCompactor`, `HybridRrfRetriever`, `HierarchicalMemoryStore` y `ContextDegradationDiagnoser`.
- `tests/test_m2_context_rag_memory.py`: Pruebas de aceptación y verificación de trampas conceptuales.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-1/m2-context-rag-memory/tests/test_m2_context_rag_memory.py
```
