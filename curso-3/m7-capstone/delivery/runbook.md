# Operational Runbook — Enterprise Insurance Platform

## 1. Procedimientos Operativos

### Procedimiento A: Conmutación por Fallo (Failover) de Proveedor LLM
1. Si la tasa de errores 5xx del pool primario (`openai/gpt-4o-mini`) supera el 5% en una ventana móvil de 3 minutos, el circuit breaker de LiteLLM Proxy conmuta automáticamente al pool secundario (`anthropic/claude-3-haiku`).
2. Comprobar métricas en Prometheus: `sum(rate(litellm_proxy_failed_requests[1m])) / sum(rate(litellm_proxy_total_requests[1m]))`.
3. Para forzar conmutación manual: `curl -X POST http://gateway.internal:4000/routing/failover -d '{"force_pool": "secondary"}'`.

### Procedimiento B: Rotación de Claves Maestras KMS
1. Las claves de cifrado en reposo de la bóveda de seudonimización se rotan automáticamente cada 90 días mediante AWS KMS / HashiCorp Vault.
2. Para rotación manual sin tiempo de caída: generar nuevo Key Version en KMS, re-encriptar claves de datos con Envelope Encryption y actualizar variable `KMS_KEY_ALIAS_PROD`.

## 2. Contactos y Cadena de Escalado

| Rol | Contacto Principal | Canal de Emergencia |
|---|---|---|
| Incident Commander (IC) | Elena Morales (Lead FDE) | Slack: #incident-bridge / Tel: +34-600-001 |
| SRE / Infra On-Call | Marcos Díaz (Plataforma) | PagerDuty: Esc-Team-SRE |
| DPO / Compliance Lead | Dra. Sofía Valdés | dpo@seguros-corp.example |

## 3. Umbrales de Escalado y Severidades

- **P1 (Crítico)**: Caída total del gateway o fuga confirmada de PII no seudonimizada hacia proveedor externo. Escalar en < 5 minutos.
- **P2 (Alto)**: Tasa de error de inferencia > 5% o conmutación prolongada a pool secundario > 30 minutos. Escalar en < 15 minutos.
- **P3 (Medio)**: Presupuesto de clave virtual agotado en unidad operativa. Notificar al responsable financiero en < 2 horas.
