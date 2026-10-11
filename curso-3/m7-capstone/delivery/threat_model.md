# Threat & Privacy Model — Enterprise Insurance Platform

## STRIDE Threat Analysis

### 1. Spoofing
- **Amenaza**: Inyección de tokens JWT falsificados para suplantar la identidad de analistas de siniestros.
- **Severidad**: Crítica
- **Mitigacion**: Validación criptográfica estricta de firma RS256/Ed25519 contra JWKS oficial de GitHub/IdP corporativo y verificación de audiencia `agentik-attestation`.

### 2. Tampering
- **Amenaza**: Alteración maliciosa de instrucciones del sistema en el gateway para desviar liquidaciones.
- **Severidad**: Alta
- **Mitigacion**: Fijación criptográfica por hash SHA-256 de todas las plantillas de prompt y esquemas JSON con validación en runtime.

### 3. Repudiation
- **Amenaza**: Un operador aprueba una indemnización anómala y niega haber ejecutado la consulta al LLM.
- **Severidad**: Alta
- **Mitigacion**: Propagación obligatoria de cabeceras de atribución OIDC (`X-End-User-Id`, `X-Audit-Tenant-Id`) registradas en logs inmutables con retención auditada.

### 4. Information Disclosure
- **Amenaza**: Exposición inadvertida de NIFs, números de cuenta o datos de salud hacia APIs externas.
- **Severidad**: Crítica
- **Mitigacion**: Pipeline de detección y seudonimización con Presidio y encriptación en reposo en bóveda de claves dedicada.

### 5. Denial of Service
- **Amenaza**: Sobrecarga de peticiones concurrentes agotando la cuota mensual de inferencia en minutos.
- **Severidad**: Alta
- **Mitigacion**: Techos presupuestarios duros (`max_budget`) por clave virtual en LiteLLM Proxy con circuit breaker y rate limit por tenant.

### 6. Elevation of Privilege
- **Amenaza**: Acceso a endpoints administrativos de gestión de claves sin autorización de rol.
- **Severidad**: Crítica
- **Mitigacion**: Control de acceso basado en roles (RBAC) y aislamiento de red en endpoints VPC privados sin acceso público.

---

## LINDDUN Privacy Analysis

### 1. Linkability
- **Amenaza**: Asociación de múltiples siniestros aparentemente no relacionados con el mismo individuo.
- **Severidad**: Alta
- **Mitigacion**: Generación de tokens efímeros no deterministas y separación física de esquemas relacionales.

### 2. Identifiability
- **Amenaza**: Reidentificación de partes implicadas a partir de combinaciones de código postal y fechas.
- **Severidad**: Crítica
- **Mitigacion**: Seudonimización rigurosa bajo RGPD Art. 4(5) y generalización de rangos temporales.

### 3. Disclosure of Information
- **Amenaza**: Filtración de datos de categoría especial (salud) en respuestas de evaluación.
- **Severidad**: Crítica
- **Mitigacion**: Guardrails de salida con inspección semántica y regex bloqueante para identificadores directos.
