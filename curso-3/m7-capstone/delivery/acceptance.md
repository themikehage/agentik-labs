# Plan de Aceptación y Evaluación con Golden Set

## 1. Criterio de Aceptación y Racionalidad de Riesgo

El pase de la plataforma a producción exige la validación empírica sobre el *Golden Set* de siniestros corporativos (N = 250 expedientes auditados). Ningún umbral se evalúa como cifra puntual arbitraria; cada criterio se contrasta contra el límite inferior del Intervalo de Confianza (IC) del 95% para discriminar mejoras reales de fluctuaciones estocásticas.

## 2. Métricas y Umbrales con Intervalo de Confianza

| SLI / Criterio | Muestra (N) | Valor Puntual | IC 95% (Wilson / Normal) | Umbral Mínimo Aceptable | Justificación por Riesgo |
|---|---|---|---|---|---|
| **Detección PII NIF/NIE (Presidio)** | 250 | 0.952 | [0.918, 0.973] | ≥ 0.900 (en límite inf.) | Sanciones RGPD de hasta 20M EUR por fuga de identificadores directos. |
| **TPR Guardrails Adversariales** | 200 | 0.885 | [0.833, 0.922] | ≥ 0.800 (en límite inf.) | Prevención de jailbreak y manipulación de dictámenes automáticos. |
| **FPR Guardrails (Falsas Alarmas)** | 300 | 0.033 | [0.018, 0.060] | ≤ 0.050 (en límite sup.) | Falsos bloqueos degradan la productividad del analista pericial. |
| **Latencia P95 Inferencia (seg)** | 1000 | 2.45 s | [2.30, 2.60] | ≤ 3.00 s | SLO contractual con unidades operativas de siniestros. |

## 3. Aprobación del Gate de Regresión

El sistema no se desplegará si cualquiera de las pruebas de regresión históricas (`eval_fecha_bisiesto_siniestro`, `eval_poliza_nif_con_guion`) falla, garantizando que los incidentes pasados no se reintroduzcan en la versión candidata.
