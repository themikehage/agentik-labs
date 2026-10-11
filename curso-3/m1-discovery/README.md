# Laboratorio M1 — Rol FDE, Stakeholders y RFC Verificable (Curso 3)

## Objetivos del Laboratorio

1. **RA-1.1**: Diferenciar y priorizar el hallazgo de mayor riesgo sistémico para el proyecto ante múltiples evidencias de *discovery*, sustentando la elección con citas textuales y descartando hallazgos superficiales o cosméticos.
2. **RA-1.2**: Estructurar mapas de interesados (`stakeholders.json`) con roles clave (decisor y afectado) y supuestos explícitos, y mapas de proceso (`process_map.json`) con pasos secuenciales y gestión de excepciones.
3. **RA-1.3**: Validar especificaciones funcionales (`rfc.yaml`) contra un esquema estricto que exija invariantes, dependencias de datos, métricas con umbrales numéricos, *non-goals* y supuestos, impidiendo la aprobación de métricas cualitativas ambiguas.
4. **RA-1.4**: Evaluar fuentes de datos corporativas (`data_readiness.json`) en cinco dimensiones cardinales (existencia, acceso, calidad, gobernanza y latencia) y computar decisiones trazables (`incluir`, `remediar`, `excluir`).

## Estructura de Entrega

- `solution.py`: Implementación de referencia de `DiscoveryAnalyzer`, `StakeholderProcessMapper`, `RfcSchemaValidator` y `DataReadinessEvaluator`.
- `tests/test_m1_discovery.py`: Suite de validación determinista que comprueba criterios positivos y trampas conceptuales.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-3/m1-discovery/tests/test_m1_discovery.py
```
