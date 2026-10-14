# Laboratorio M7 — Capstone: Enterprise Delivery Package (Curso 3)

## Objetivos del Laboratorio

1. **RA-7.1**: Integrar los componentes técnicos del sistema operativo: LiteLLM Proxy con presupuestos duros y *failover* automatizado, canalización de PII con medición de precisión/recall por entidad en Presidio, NeMo Guardrails con TPR/FPR acotados sobre dataset adversarial, y validación de red privada.
2. **RA-7.2**: Generar el expediente documental auditable en `delivery/`, validando que cada artefacto (`rfc.yaml`, `adr.md`, `threat_model.md`, `runbook.md`, `acceptance.md`) cumple estrictamente su esquema formal de campos obligatorios.
3. **RA-7.3**: Evaluar umbrales de aceptación con Intervalos de Confianza (IC al 95%) derivados empíricamente y justificados por análisis de riesgo financiero y regulatorio (RGPD / AI Act).
4. **RA-7.4**: Superar la suite de atestación oficial (suite privada de `certify.yml`), demostrando resistencia a manipulaciones adversariales y reproducibilidad estricta bajo la siembra por usuario `derive_seed(user_id, "c3-m7-capstone")`.

## Estructura de Entrega

- `solution.py`: Implementación integrada de `EnterpriseDeliverySystem` y `EnterprisePackageValidator`.
- `delivery/`:
  - `rfc.yaml`: Especificación funcional verificable con umbrales numéricos.
  - `adr.md`: Registro de decisión arquitectónica bajo formato MADR 3.x.
  - `threat_model.md`: Modelado STRIDE y LINDDUN con mitigaciones de alta severidad.
  - `runbook.md`: Procedimientos operativos, alertas, contactos y rotación KMS.
  - `acceptance.md`: Plan de aceptación con *golden set*, SLIs y umbrales con IC.
- `tests/test_c3_m7_capstone_public.py`: Pruebas de aceptación públicas del capstone.
- La suite oficial de certificación es privada: la ejecuta únicamente el workflow `certify.yml` (no se distribuye en esta plantilla).

## Ejecución de Pruebas

```bash
# Pruebas públicas
uv run pytest -v curso-3/m7-capstone/tests/test_c3_m7_capstone_public.py

```
