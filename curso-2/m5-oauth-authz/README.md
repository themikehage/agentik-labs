# Laboratorio M5 — Autorización OAuth 2.1 y Token Exchange MCP (Curso 2)

## Objetivos del Laboratorio

1. Implementar el flujo de autorización OAuth 2.1 con **PKCE** obligatorio (`code_challenge_method: "S256"`).
2. Construir un validador estricto de tokens que verifique `iss`, `aud`, y tiempo de expiración contra `VirtualClock`.
3. Emitir desafíos semánticos `insufficient_scope` con cabeceras `WWW-Authenticate` cuando los permisos del token no alcancen la operación solicitada.
4. Implementar el patrón de **Token Exchange (RFC 8693)** para llamadas a servicios *downstream*, eliminando por completo el antipatrón de *token passthrough*.

## Estructura de Entrega

- `solution.py`: Contiene `OAuthAuthorizationServer`, `TokenValidator`, y `DownstreamTokenExchanger`.
- `tests/test_m5_oauth_authz.py`: Suite de tests deterministas sobre `pytest-socket`.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-2/m5-oauth-authz/tests/test_m5_oauth_authz.py
```
