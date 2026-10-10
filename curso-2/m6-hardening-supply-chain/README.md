# Laboratorio M6 — Hardening, Anti-SSRF y Cadena de Suministro MCP (Curso 2)

## Objetivos del Laboratorio

1. Implementar fijación de definiciones de herramientas (*Tool Pinning*) con verificación criptográfica SHA-256 para prevenir ataques de *Tool Poisoning* y *Rug-Pull*.
2. Construir un motor de políticas de red **Anti-SSRF** que bloquee llamadas a localhost, redes privadas RFC 1918, link-local (169.254.169.254) y esquemas inseguros.
3. Sanitizar y delimitar entradas para neutralizar inyecciones indirectas de prompt en contenido de herramientas.
4. Validar el aislamiento estricto de ejecución en `HardenedSandbox` (`--network none`, `--read-only`, `--cap-drop ALL`, `--user 10001`).

## Estructura de Entrega

- `solution.py`: Contiene `ToolPolicyEngine`, `AntiSsrfValidator`, `PromptSanitizer`, y el orquestador de sandbox.
- `tests/test_m6_hardening.py`: Suite de tests deterministas sobre `pytest-socket`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-2/m6-hardening-supply-chain/tests/test_m6_hardening.py
```
