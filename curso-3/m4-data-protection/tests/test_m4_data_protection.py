"""
Reference tests for Curso 3 M4 - Protección de Datos, PII y Gobernanza.
Validates:
- RA-4.1: Threat modeling (STRIDE) and privacy modeling (LINDDUN) with mitigations (positive & negative).
- RA-4.2: Legal-technical classification of reversible tokenization as pseudonymization under GDPR (positive & negative).
- RA-4.3: Quantitative evaluation of Presidio on Spanish gold set rejecting 100% recall claims (positive & negative).
- RA-4.4: Enterprise governance map integration with complementary regulatory layers and ZDR (positive & negative).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c3_m4_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

ThreatPrivacyModelValidator = _mod.ThreatPrivacyModelValidator
ThreatItem = _mod.ThreatItem
LegalClassificationAnalyzer = _mod.LegalClassificationAnalyzer
PresidioEvaluator = _mod.PresidioEvaluator
GovernanceMapValidator = _mod.GovernanceMapValidator


class TestRA41StrideAndLinddunModeling:
    """
    RA-4.1: Modelado de amenazas STRIDE y privacidad LINDDUN con mitigaciones obligatorias.
    """

    def test_positive_complete_stride_and_linddun_with_mitigations(self) -> None:
        """
        [RA-4.1 POSITIVE] Confirma que los modelos STRIDE y LINDDUN con mitigaciones
        arquitectónicas para amenazas críticas y altas superan la validación.
        """
        validator = ThreatPrivacyModelValidator()
        stride_threats = [
            ThreatItem(
                category="spoofing",
                description="Suplantación de identidad del analista mediante token JWT manipulado.",
                severity="critical",
                mitigation="Verificación criptográfica de firma JWKS con algoritmo RS256/Ed25519 y validación estricta de audiencia.",
            ),
            ThreatItem(
                category="information_disclosure",
                description="Filtración de PII en logs de depuración del proxy de inferencia.",
                severity="high",
                mitigation="Enmascaramiento de payloads y ofuscación de tokens antes de la serialización en el collector OTel.",
            ),
            ThreatItem(
                category="denial_of_service",
                description="Agotamiento de cuota por bucle infinito de reintentos.",
                severity="medium",
                mitigation="Rate limiting y circuit breaker en LiteLLM.",
            ),
        ]
        linddun_threats = [
            ThreatItem(
                category="identifiability",
                description="Reidentificación del tomador de seguro a partir de NIF y fecha de siniestro.",
                severity="critical",
                mitigation="Sustitución determinista por pseudónimos en bóveda aislada y partición de accesos.",
            ),
            ThreatItem(
                category="linkability",
                description="Correlación de consultas cruzadas del mismo cliente en múltiples expedientes.",
                severity="high",
                mitigation="Rotación de identificadores de sesión efímeros desacoplados del ID maestro.",
            ),
            ThreatItem(
                category="disclosure_of_information",
                description="Exposición de datos de salud en el prompt context.",
                severity="medium",
                mitigation="Filtro NER presidio previo a la llamada LLM.",
            ),
        ]

        stride_res = validator.validate_stride(stride_threats)
        linddun_res = validator.validate_linddun(linddun_threats)
        assert stride_res["status"] == "valid"
        assert linddun_res["status"] == "valid"

    def test_negative_missing_mitigations_for_high_severity_threats_fails(self) -> None:
        """
        [RA-4.1 NEGATIVE] Demuestra que declarar amenazas de severidad crítica/alta
        sin mitigación técnica documentada es rechazado.
        """
        validator = ThreatPrivacyModelValidator()
        unmitigated_stride = [
            ThreatItem(
                category="elevation_of_privilege",
                description="Escalada de privilegios a administrador del gateway.",
                severity="critical",
                mitigation="",  # Vacío
            ),
            ThreatItem(category="tampering", description="Modificación de prompt", severity="low", mitigation="None"),
            ThreatItem(category="spoofing", description="Spoofing", severity="low", mitigation="None"),
        ]

        with pytest.raises(ValueError, match="requires an architectural mitigation"):
            validator.validate_stride(unmitigated_stride)


class TestRA42LegalClassificationPseudonymization:
    """
    RA-4.2: Clasificación de bóveda reversible como seudonimización bajo RGPD.
    """

    def test_positive_reversible_tokenization_classified_as_pseudonymization(self) -> None:
        """
        [RA-4.2 POSITIVE] Confirma que la sustitución reversible de PII con bóveda
        se clasifica correctamente como seudonimización sujeta a las garantías del RGPD.
        """
        analyzer = LegalClassificationAnalyzer()
        result = analyzer.classify_tokenization_operation(
            has_reversible_vault=True,
            classification_claim="seudonimizacion",
            justification="Al conservarse la tabla de mapeo cifrada para reidentificación autorizada, "
            "los datos siguen siendo identificables indirectamente según RGPD Considerando 26.",
        )

        assert result["legal_status"] == "pseudonymized_data"
        assert result["gdpr_applies"] is True
        assert result["requires_dpia"] is True
        assert result["is_anonymous"] is False

    def test_negative_reversible_tokenization_claimed_as_anonymous_fails(self) -> None:
        """
        [RA-4.2 NEGATIVE] Demuestra que afirmar que la tokenización reversible es 'anonimización
        que sale del RGPD' es rechazado como grave falsedad jurídica.
        """
        analyzer = LegalClassificationAnalyzer()
        with pytest.raises(ValueError, match="strictly PSEUDONYMIZATION under GDPR Art. 4"):
            analyzer.classify_tokenization_operation(
                has_reversible_vault=True,
                classification_claim="anonimizacion completa",
                justification="Como cambiamos el nombre por [PERSON_1], el dato queda fuera del RGPD.",
            )


class TestRA43PresidioQuantitativeEvaluation:
    """
    RA-4.3: Evaluación cuantitativa de Presidio sobre gold set español por entidad.
    """

    def test_positive_entity_level_precision_and_recall_computation(self) -> None:
        """
        [RA-4.3 POSITIVE] Confirma que el evaluador computa métricas de Precision y Recall
        desglosadas por cada entidad (NIF_NIE, PERSONA_COMPUESTA, IBAN).
        """
        evaluator = PresidioEvaluator()
        gold_data = [
            {
                "id": "doc-01",
                "text": "El asegurado Juan Carlos Pérez con NIF 12345678Z abonó la prima.",
                "entities": [
                    {"type": "PERSONA_COMPUESTA", "start": 13, "end": 30},
                    {"type": "NIF_NIE", "start": 39, "end": 48},
                ],
            },
            {
                "id": "doc-02",
                "text": "Transferencia desde cuenta ES9121000418450200051332 de María Santos.",
                "entities": [
                    {"type": "IBAN", "start": 27, "end": 51},
                    {"type": "PERSONA_COMPUESTA", "start": 55, "end": 67},
                ],
            },
        ]
        predicted_data = [
            {
                "id": "doc-01",
                "entities": [
                    {"type": "PERSONA_COMPUESTA", "start": 13, "end": 30},  # TP
                    {"type": "NIF_NIE", "start": 39, "end": 48},  # TP
                ],
            },
            {
                "id": "doc-02",
                "entities": [
                    {"type": "IBAN", "start": 27, "end": 51},  # TP
                    # PERSONA_COMPUESTA missed -> FN
                ],
            },
        ]

        metrics = evaluator.evaluate_gold_set(gold_data, predicted_data)
        assert metrics["NIF_NIE"].recall == 1.0
        assert metrics["NIF_NIE"].precision == 1.0
        assert metrics["PERSONA_COMPUESTA"].recall == 0.5  # 1 TP, 1 FN
        assert metrics["IBAN"].recall == 1.0

    def test_negative_unrealistic_100_percent_recall_promise_fails(self) -> None:
        """
        [RA-4.3 NEGATIVE] Demuestra que prometer '100% de recall en detección de PII'
        es bloqueado como afirmación estadísticamente falaz.
        """
        evaluator = PresidioEvaluator()
        unrealistic_claims = [
            "Nuestro sistema Presidio garantiza 100% de recall en todas las pólizas."
        ]
        with pytest.raises(ValueError, match="Promising 100% recall or zero false negatives is rejected"):
            evaluator.validate_claims(unrealistic_claims)


class TestRA44GovernanceMapIntegration:
    """
    RA-4.4: Mapa de gobernanza integrando RGPD, AI Act, ISO 42001 y NIST AI RMF.
    """

    def test_positive_complementary_layers_and_zdr_with_exceptions(self) -> None:
        """
        [RA-4.4 POSITIVE] Confirma validación exitosa de un mapa de gobernanza
        que integra las 4 capas complementarias y documenta acuerdos ZDR con excepciones.
        """
        validator = GovernanceMapValidator()
        gov_doc = {
            "data_protection": {
                "framework": "RGPD 2016/679",
                "controles": ["Art. 6 Base legitimadora", "Art. 35 DPIA obligatoria", "Art. 28 Encargado del tratamiento"],
            },
            "ai_regulation": {
                "framework": "EU AI Act 2024/1689",
                "clasificacion": "Sistema de alto riesgo (Anexo III - empleo y servicios financieros)",
                "calendario": "Obligaciones aplicables por fases trimestrales",
            },
            "management_system": {
                "framework": "ISO/IEC 42001:2023",
                "alcance": "Sistema de Gestion de Inteligencia Artificial (SGIA) corporativo",
            },
            "risk_framework": {
                "framework": "NIST AI RMF 1.0",
                "funciones": ["GOVERN", "MAP", "MEASURE", "MANAGE"],
            },
            "framework_relationship": "Las cuatro normativas operan en capas complementarias y sinergicas.",
            "zero_data_retention": {
                "has_agreement": True,
                "documented_exceptions": [
                    "Retencion de logs de abuso por 30 dias salvo firma de Addendum BAA enterprise.",
                    "Cero re-entrenamiento sobre datos de clientes garantizado por contrato.",
                ],
            },
        }

        result = validator.validate_governance_map(gov_doc)
        assert result["status"] == "valid"
        assert result["layers_validated"] == 4

    def test_negative_treating_frameworks_as_mutually_exclusive_fails(self) -> None:
        """
        [RA-4.4 NEGATIVE] Demuestra que tratar los marcos como excluyentes o sustitutos
        ('ISO 42001 reemplaza a RGPD') genera rechazo formal.
        """
        validator = GovernanceMapValidator()
        exclusive_doc = {
            "data_protection": {},
            "ai_regulation": {},
            "management_system": {},
            "risk_framework": {},
            "framework_relationship": "La certificacion ISO 42001 reemplaza y anula las exigencias del RGPD.",
            "zero_data_retention": {"has_agreement": True, "documented_exceptions": ["None"]},
        }

        with pytest.raises(ValueError, match="Governance frameworks operate in complementary layers"):
            validator.validate_governance_map(exclusive_doc)
