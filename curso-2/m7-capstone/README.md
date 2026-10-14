# Laboratorio M7 — Capstone: Enterprise MCP Gateway (Curso 2)

## Objetivos del Capstone

1. Integrar un **Enterprise MCP Gateway** *production-ready* conforme al estándar `2026-07-28`.
2. Servir transporte **Streamable HTTP** *stateless* sin afinidad de sesión ni métodos obsoletos (`initialize`, `ping`, `Mcp-Session-Id`).
3. Soportar flujos de interacción humana/aprobación mediante **MRTR** (`resultType: "input_required"`).
4. Proteger los endpoints con **OAuth 2.1**, validación estricta de tokens y delegación *downstream* mediante **RFC 8693 Token Exchange**.
5. Defender la infraestructura con **Hash Pinning** contra *Tool Poisoning* y filtrado **Anti-SSRF**.
6. Orquestar operaciones de larga duración como tareas asíncronas (`tasks/get`).
7. Soportar parametrización sembrada por usuario vía `derive_seed` para garantizar la atestación desatendida del nivel **Practitioner**.

## Estructura de Entrega

- `solution.py`: Implementación completa de `EnterpriseMcpGateway`.
- `tests/test_m7_capstone_public.py`: Batería de pruebas de conformidad públicas.
- La suite oficial de certificación es privada: la ejecuta únicamente el workflow `certify.yml` (no se distribuye en esta plantilla).

## Ejecución de Pruebas

```bash
# Pruebas públicas locales del estudiante
uv run pytest -v curso-2/m7-capstone/tests/test_m7_capstone_public.py

```
