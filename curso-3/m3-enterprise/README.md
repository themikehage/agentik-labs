# Laboratorio M3 — Integración Enterprise, Proxy y Red (Curso 3)

## Objetivos del Laboratorio

1. **RA-3.1**: Configurar un gateway de inferencia enterprise (LiteLLM Proxy) con almacenamiento relacional persistente y presupuestos duros (`max_budget`) por clave virtual, validando el bloqueo determinista inmediato al sobrepasar el límite asignado.
2. **RA-3.2**: Implementar el motor de propagación de identidad OIDC (`oidc_propagation.py`) para reenviar la atribución de usuario final (`sub`, email, tenant) en cabeceras de auditoría hacia los servicios internos, impidiendo la anonimización de consultas detrás de una única clave de aplicación.
3. **RA-3.3**: Aplicar validación de red mediante *Policy-as-Code*, rechazando planes de infraestructura que contengan IPs públicas, egress irrestricto hacia `0.0.0.0/0` o endpoints abiertos que no pasen por enlaces privados (PrivateLink / VPC Endpoints).
4. **RA-3.4**: Auditar la documentación de cadena de suministro (`supply_chain.md`), validando la fijación estricta de imágenes por *hash* SHA-256, el registro de SBOM y la política de rotación de claves maestras, detectando y rechazando el antipatrón de calificar un archivo de log como "compatible con SOC 2".

## Estructura de Entrega

- `solution.py`: Contiene `LiteLLMProxyGateway`, `OidcIdentityPropagator`, `NetworkPolicyValidator` y `SupplyChainAuditor`.
- `tests/test_m3_enterprise.py`: Suite de validación determinista que comprueba presupuestos duros, identidad y red.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-3/m3-enterprise/tests/test_m3_enterprise.py
```
