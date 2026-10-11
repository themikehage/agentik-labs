# Laboratorio M7: Capstone Multiagent Orchestrator & Suite Oculta

## Objetivos de Aprendizaje (Resultados de Aprendizaje)
- **RA-7.1**: Validación formal de `DESIGN.md` contra esquema estricto (núcleo de 7 pilares, elección de 2 extensiones, métricas numéricas y consecuencias con signo `+` y `-`).
- **RA-7.2**: Integración de los 7 pilares del núcleo (topología con agregación invariante, contexto presupuestado, harness gobernado, checkpointing durable, outbox idempotente, suspensión HITL y environment graders).
- **RA-7.3**: Verificación unitaria e independiente de las 2 extensiones seleccionadas (RAG contextual híbrido con filtro por tenant + Memoria jerárquica con TTL).
- **RA-7.4**: Fiabilidad demostrada mediante el límite inferior del IC 95% de `pass^k` sobre ≥100 corridas superando el umbral declarado (≥ 0.85).
- **RA-7.5**: Contención en frontera inter-agente midiendo TPR y FPR.

## Ejecución de Tests
```bash
# Tests públicos
uv run pytest -v curso-1/m7-capstone/tests/test_c1_m7_capstone_public.py

# Suite oculta oficial de certificación
uv run pytest -v curso-1/m7-capstone/tests/hidden/test_c1_m7_capstone_hidden.py
```
