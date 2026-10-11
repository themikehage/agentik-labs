"""
Reference tests for Curso 3 M1 - Rol FDE y Discovery.
Validates:
- RA-1.1: Prioritizing highest-risk discovery findings with textual evidence (positive & negative).
- RA-1.2: Stakeholder and process maps with explicit assumptions and exceptions (positive & negative).
- RA-1.3: RFC schema validation enforcing numeric metric thresholds and non-goals (positive & negative).
- RA-1.4: Data readiness evaluation across 5 dimensions and decision mapping (positive & negative).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c3_m1_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

DiscoveryFinding = _mod.DiscoveryFinding
DiscoveryAnalyzer = _mod.DiscoveryAnalyzer
StakeholderProcessMapper = _mod.StakeholderProcessMapper
RfcSchemaValidator = _mod.RfcSchemaValidator
DataReadinessEvaluator = _mod.DataReadinessEvaluator


class TestRA11DiscoveryRiskRanking:
    """
    RA-1.1: Identificación del hallazgo de mayor riesgo citando evidencia textual sustentada.
    """

    def test_positive_selects_highest_risk_structural_finding_with_evidence(self) -> None:
        """
        [RA-1.1 POSITIVE] Confirma que ante múltiples hallazgos de discovery,
        se selecciona el hallazgo crítico de datos con evidencia textual verificable.
        """
        analyzer = DiscoveryAnalyzer()
        findings = [
            DiscoveryFinding(
                id="FND-01",
                area="UI/UX",
                summary="Pantalla de gestión tiene diseño antiguo de 2018.",
                evidence="Entrevista analista: 'El fondo gris es feo pero funciona.'",
                risk_severity="low",
                is_cosmetic=True,
            ),
            DiscoveryFinding(
                id="FND-02",
                area="Integración de Datos",
                summary="Pólizas maestras residen en SFTP no documentado con PII no cifrada.",
                evidence="Auditoría IT: 'El dump semanal carece de cifrado en reposo y se sobrescribe sin histórico.'",
                risk_severity="critical",
                is_cosmetic=False,
            ),
            DiscoveryFinding(
                id="FND-03",
                area="Procesos",
                summary="Usuarios tardan 4 clics en descargar reportes.",
                evidence="Observación de campo: 'Toman 15 segundos adicionales por consulta.'",
                risk_severity="medium",
                is_cosmetic=False,
            ),
        ]

        highest, evidence = analyzer.identify_highest_risk_finding(findings)
        assert highest.id == "FND-02"
        assert highest.risk_severity == "critical"
        assert "dump semanal carece de cifrado" in evidence

    def test_negative_cosmetic_visible_finding_rejected(self) -> None:
        """
        [RA-1.1 NEGATIVE] Demuestra que priorizar un hallazgo visible pero cosmético
        por sobre los riesgos estructurales del sistema es rechazado.
        """
        analyzer = DiscoveryAnalyzer()
        cosmetic_only = [
            DiscoveryFinding(
                id="FND-COSMETIC-01",
                area="Frontend",
                summary="El logotipo de la barra superior está desalineado por 3px.",
                evidence="Captura de pantalla: desalineación en pantallas ultrawide.",
                risk_severity="low",
                is_cosmetic=True,
            )
        ]

        with pytest.raises(ValueError, match="All findings were marked as cosmetic"):
            analyzer.identify_highest_risk_finding(cosmetic_only)


class TestRA12StakeholderAndProcessMap:
    """
    RA-1.2: Estructuración de stakeholders.json y process_map.json con supuestos y excepciones.
    """

    def test_positive_valid_stakeholder_and_process_maps(self) -> None:
        """
        [RA-1.2 POSITIVE] Confirma validación exitosa de mapas que contienen decisores,
        afectados, supuestos explícitos y excepciones de flujo.
        """
        mapper = StakeholderProcessMapper()
        stakeholders_data = {
            "stakeholders": [
                {
                    "name": "Elena Morales",
                    "role_type": "decisor",
                    "department": "Operaciones Siniestros",
                    "supuesto": "Tiene potestad presupuestaria directa sobre el piloto.",
                },
                {
                    "name": "Carlos Ruiz",
                    "role_type": "afectado",
                    "department": "Analistas Nivel 1",
                    "supuesto": "Su métrica de incentivos no se penalizará durante la curva de aprendizaje.",
                },
            ]
        }
        process_data = {
            "process_name": "Tramitación de Póliza",
            "steps": [
                {"step_number": 1, "action": "Recepción de PDF vía SFTP", "actor": "Sistema Ingesta"},
                {"step_number": 2, "action": "Validación de cobertura", "actor": "Analista N1"},
            ],
            "exceptions": [
                "Póliza con daño total exige intervención presencial de perito judicial."
            ],
            "assumptions": [
                "El 95% de los siniestros ingresan en formato digital legible."
            ],
        }

        res_s = mapper.validate_stakeholder_map(stakeholders_data)
        res_p = mapper.validate_process_map(process_data)
        assert len(res_s["stakeholders"]) == 2
        assert len(res_p["exceptions"]) == 1

    def test_negative_process_map_omits_exceptions_fails(self) -> None:
        """
        [RA-1.2 NEGATIVE] Demuestra que omitir excepciones operativas en el process map
        falla la validación por ignorar las desviaciones del flujo real.
        """
        mapper = StakeholderProcessMapper()
        invalid_process = {
            "process_name": "Flujo Feliz",
            "steps": [
                {"step_number": 1, "action": "Paso 1", "actor": "Sistema"},
                {"step_number": 2, "action": "Paso 2", "actor": "Sistema"},
            ],
            "exceptions": [],
            "assumptions": ["Todo funciona bien."],
        }
        with pytest.raises(ValueError, match="at least one process exception"):
            mapper.validate_process_map(invalid_process)

    def test_negative_stakeholder_map_omits_assumptions_fails(self) -> None:
        """
        [RA-1.2 NEGATIVE] Demuestra que un mapa de interesados sin supuestos explícitos falla.
        """
        mapper = StakeholderProcessMapper()
        invalid_stakeholders = {
            "stakeholders": [
                {"name": "Directora", "role_type": "decisor", "supuesto": ""},
                {"name": "Operario", "role_type": "afectado", "supuesto": ""},
            ]
        }
        with pytest.raises(ValueError, match="explicit assumption"):
            mapper.validate_stakeholder_map(invalid_stakeholders)


class TestRA13RfcSchemaValidation:
    """
    RA-1.3: Validación de rfc.yaml contra esquema estricto (invariantes, métricas numéricas, non-goals).
    """

    def test_positive_valid_rfc_with_all_sections_and_numeric_thresholds(self) -> None:
        """
        [RA-1.3 POSITIVE] Confirma que un RFC con invariantes, dependencias, métricas con
        umbrales numéricos explícitos y non-goals supera el validador formal.
        """
        validator = RfcSchemaValidator()
        valid_rfc = {
            "titulo": "RFC-042: Asistente de Extracción de Pólizas",
            "invariantes": [
                "Cero almacenamiento persistente de PII fuera de la bóveda corporativa.",
                "Tiempos de respuesta P95 inferiores a 3.0 segundos.",
            ],
            "dependencias_datos": [
                "API CRM v2.1 para consulta de identificadores.",
                "Bucket S3 corporativo con lectura de pólizas.",
            ],
            "metricas": [
                {
                    "nombre": "tasa_extraccion_campos_criticos",
                    "umbral_numerico": 0.95,
                    "unidad": "ratio",
                },
                {
                    "nombre": "latencia_p95_segundos",
                    "umbral_numerico": 3.0,
                    "unidad": "segundos",
                },
            ],
            "non_goals": [
                "No emitir dictámenes jurídicos vinculantes.",
                "No procesar documentos manuscritos escaneados en baja resolución (<150dpi).",
            ],
            "supuestos": [
                "El volumen de consultas no superará 10 peticiones concurrentes en piloto.",
            ],
        }

        res = validator.validate(valid_rfc)
        assert res["titulo"].startswith("RFC-042")
        assert len(res["invariantes"]) == 2

    def test_negative_qualitative_metrics_without_numeric_threshold_fail(self) -> None:
        """
        [RA-1.3 NEGATIVE] Demuestra que métricas cualitativas ambiguas ('mejorar UX')
        sin umbral numérico son rechazadas deterministamente por el validador de esquema.
        """
        validator = RfcSchemaValidator()
        ambiguous_rfc = {
            "titulo": "RFC Ambiguo",
            "invariantes": ["Invariante 1"],
            "dependencias_datos": ["Dep 1"],
            "metricas": [
                {
                    "nombre": "mejorar_experiencia_usuario",
                    "descripcion": "Lograr que los empleados estén más contentos y trabajen rápido.",
                    "unidad": "cualitativa",
                }
            ],
            "non_goals": ["Non goal 1"],
            "supuestos": ["Supuesto 1"],
        }

        with pytest.raises(ValueError, match="numerical threshold"):
            validator.validate(ambiguous_rfc)


class TestRA14DataReadinessEvaluation:
    """
    RA-1.4: Evaluación de data_readiness.json en 5 dimensiones cardinales.
    """

    def test_positive_five_dimensions_classify_sources_accurately(self) -> None:
        """
        [RA-1.4 POSITIVE] Confirma que el evaluador clasifica fuentes entre
        'incluir', 'remediar' y 'excluir' basado en reglas de cinco dimensiones.
        """
        evaluator = DataReadinessEvaluator()
        inventory = {
            "sources": [
                {
                    "name": "crm_clientes_api",
                    "existe": True,
                    "acceso": "api",
                    "calidad": 0.95,
                    "gobernanza": "contrato",
                    "latencia_min": 1,
                },
                {
                    "name": "siniestros_manual_excel",
                    "existe": True,
                    "acceso": "manual",
                    "calidad": 0.70,
                    "gobernanza": "pii",
                    "latencia_min": 120,
                },
                {
                    "name": "historico_cintas_inaccesible",
                    "existe": False,
                    "acceso": "none",
                    "calidad": 0.20,
                    "gobernanza": "desconocida",
                    "latencia_min": 10000,
                },
            ]
        }

        result = evaluator.evaluate_inventory(inventory)
        decisions = [s["decision"] for s in result["sources"]]
        assert decisions == ["incluir", "remediar", "excluir"]

    def test_negative_missing_governance_or_latency_dimension_fails(self) -> None:
        """
        [RA-1.4 NEGATIVE] Demuestra que omitir dimensiones obligatorias como
        gobernanza o latencia genera error de validación.
        """
        evaluator = DataReadinessEvaluator()
        incomplete_src = {
            "name": "fuente_incompleta",
            "existe": True,
            "acceso": "api",
            "calidad": 0.85,
            # Falta gobernanza y latencia_min
        }

        with pytest.raises(ValueError, match="missing dimension 'gobernanza'"):
            evaluator.evaluate_source(incomplete_src)
