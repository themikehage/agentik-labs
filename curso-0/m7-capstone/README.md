# Laboratorio M7 — Capstone: Microservicio de Inferencia Enterprise (Curso 0)

## Objetivos del Capstone

1. Integrar un microservicio de inferencia empresarial con soporte de *streaming* SSE, perfilado de latencia (TTFT, ITL P50/P95) con `VirtualClock` y serialización de prompts *cache-friendly*.
2. Implementar una validación desacoplada en tres capas (Sintaxis → Esquema → Semántica de Negocio) protegiendo el sistema contra alucinaciones cuantitativas.
3. Emitir observabilidad OTel GenAI conforme a la semconv vigente con cálculo de costes estrictamente en el *pipeline* observador.
4. Ejecutar herramientas en contenedores aislados (`HardenedSandbox`) sin red (`--network none`, `--cap-drop ALL`, usuario no root) con confirmación humana obligatoria en operaciones destructivas o irreversibles.
5. Validar la calidad del servicio mediante suites de evals evaluadas por el límite inferior del intervalo de confianza al 95% por *bootstrap*.
6. Documentar las decisiones y presupuestos cuantitativos en `DESIGN.md` validado por esquema.
7. Superar la suite de atestación oficial para desbloquear la credencial *Practitioner* en `certify.yml`.

## Estructura de Entrega

- `README.md`: Enunciado y objetivos.
- `DESIGN.md`: Documento de arquitectura, decisiones y presupuestos cuantitativos.
- `solution.py`: Implementación de `EnterpriseInferenceService` y validador de diseño.
- `tests/test_c0_m7_capstone_public.py`: Pruebas de aceptación públicas.
- La suite oficial de certificación es privada: la ejecuta únicamente el workflow `certify.yml` (no se distribuye en esta plantilla).

## Ejecución de Pruebas

```bash
uv run pytest -v curso-0/m7-capstone/tests/test_c0_m7_capstone_public.py
```
