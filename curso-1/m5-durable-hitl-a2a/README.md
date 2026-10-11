# Laboratorio M5: Estado Durable, HITL y A2A

## Objetivos de Aprendizaje (Resultados de Aprendizaje)
- **RA-5.1**: Persistencia y reanudación desde checkpoints verificando coincidencia exacta del hash de estado tras simulación de interrupción/caída.
- **RA-5.2**: Idempotencia estricta de efectos secundarios no reversibles (correos, pagos, mutaciones) mediante claves estables de deduplicación derivadas de `(task_id, step_id)` y patrón outbox.
- **RA-5.3**: Human-in-the-Loop asíncrono con suspensión de ejecución y reanudación guiada por eventos sin sockets ni hilos bloqueados.
- **RA-5.4**: Clean-slate handoff transportando exclusivamente payloads estructurados de progreso y estado hacia subagentes sin transferir el historial bruto de conversación.
- **RA-5.5**: Protocolo A2A con validación de Agent Card y máquina de estados formal del ciclo de vida de tareas (`submitted`, `working`, `input-required`, `completed`, `failed`).

## Ejecución de Tests
```bash
uv run pytest -v curso-1/m5-durable-hitl-a2a/tests/test_m5_durable_hitl_a2a.py
```
