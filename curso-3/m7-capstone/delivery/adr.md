# ADR-099: Arquitectura de Entrega Enterprise y Gateway LiteLLM

## Estado
aceptado

## Contexto
El cliente asegurador procesa siniestros con datos confidenciales de pólizas y necesita integrar modelos LLM reduciendo el riesgo de filtración de PII, garantizando techos presupuestarios duros por unidad de negocio y asegurando disponibilidad ante caídas de proveedores externos.

## Decision
Desplegamos una arquitectura desacoplada basada en LiteLLM Proxy con persistencia PostgreSQL para cuotas duras y pool de respaldo con failover automático, precedido por un pipeline de seudonimización reversible Presidio y filtrado de guardrails con presupuestos de latencia diferenciados.

## Opciones consideradas
- Opcion A: Gateway LiteLLM con bóveda Postgres y NeMo Guardrails
  - Pros: Presupuestos duros garantizados, failover transparente, protección contra prompt injection y trazabilidad OIDC.
  - Contras: Sobrecarga operativa de base de datos relacional y ~15ms de latencia adicional por petición.
- Opcion B: Invocación directa a APIs de proveedores desde microservicios
  - Pros: Simplicidad inicial sin componentes intermedios de red.
  - Contras: Imposibilidad de aplicar techos de gasto globales, riesgo de filtración de PII y ausencia de auditoría de usuario final.

## Consecuencias
- Positivas:
  - Control de gasto garantizado al 100% mediante corte determinista por clave virtual.
  - Mitigación de riesgos RGPD mediante canalización y tokenización controlada.
  - Resiliencia operacional con failover automatizado a pool secundario ante errores 5xx del primario.
- Negativas:
  - Introduce un salto de red adicional y dependencia crítica de la disponibilidad de la base de datos de cuotas.
  - Los self-check rails de evaluación añaden 200-400ms de latencia en la ruta de procesamiento.
