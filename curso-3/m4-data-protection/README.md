# Laboratorio M4 — Protección de Datos, PII y Gobernanza (Curso 3)

## Objetivos del Laboratorio

1. **RA-4.1**: Estructurar modelos formales de amenazas técnicas STRIDE (`threat_model.md`) y amenazas de privacidad LINDDUN (`privacy_model.md`), asociando mitigaciones arquitectónicas obligatorias a todas las amenazas de severidad alta.
2. **RA-4.2**: Clasificar rigurosamente las operaciones de sustitución reversible de PII mediante bóveda de claves como **seudonimización** bajo el RGPD (Art. 4.5 y Considerando 26), desmontando la peligrosa falacia jurídica de que sustituir nombres por tokens constituye "anonimización que sale del RGPD".
3. **RA-4.3**: Implementar la evaluación cuantitativa de pipelines de detección de PII (Presidio) sobre un *gold set* en español (`presidio_eval.py`), reportando *Precision* y *Recall* por tipo de entidad (NIF/NIE, nombres de personas compuestos, IBAN) y rechazando terminantemente promesas ficticias de "100% de recall".
4. **RA-4.4**: Articular el mapa de gobernanza corporativa integrando de forma complementaria RGPD (capa de datos), AI Act 2024/1689 (capa de producto regulado), ISO/IEC 42001 (capa de gestión organizacional) y NIST AI RMF 1.0 (capa de tratamiento de riesgos).

## Estructura de Entrega

- `solution.py`: Contiene `ThreatPrivacyModelValidator`, `LegalClassificationAnalyzer`, `PresidioEvaluator` y `GovernanceMapValidator`.
- `tests/test_m4_data_protection.py`: Pruebas de aceptación deterministas y validación de trampas conceptuales y regulatorias.

## Ejecución de Pruebas

```bash
uv run pytest -v curso-3/m4-data-protection/tests/test_m4_data_protection.py
```
