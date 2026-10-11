"""
Reference tests for Curso 3 M6 - Operaciones, Incidentes y Triage Forense.
Validates:
- RA-6.1: Incident protocol with command roles, severity and communication cadence (positive & negative).
- RA-6.2: Forensic trace diagnosis identifying root causal span vs symptom (positive & negative).
- RA-6.3: Blameless postmortem according to Google SRE standard rejecting personal blame (positive & negative).
- RA-6.4: Regression eval lifecycle failing deterministically before hotfix and passing after (positive & negative).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c3_m6_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

IncidentReportValidator = _mod.IncidentReportValidator
ForensicTraceAnalyzer = _mod.ForensicTraceAnalyzer
TraceSpan = _mod.TraceSpan
BlamelessPostmortemValidator = _mod.BlamelessPostmortemValidator
RegressionLifecycleManager = _mod.RegressionLifecycleManager


class TestRA61IncidentProtocol:
    """
    RA-6.1: Protocolo de incidentes con roles de mando (IC, Comunicaciones, Escriba) y cadencia.
    """

    def test_positive_valid_incident_report_with_roles_and_cadence(self) -> None:
        """
        [RA-6.1 POSITIVE] Confirma que un reporte de incidente con roles formales,
        severidad P1 y cadencia de actualización a clientes supera la validación.
        """
        validator = IncidentReportValidator()
        valid_report = {
            "severity": "P1",
            "roles": {
                "incident_commander": "Elena Morales (Lead FDE)",
                "communications_lead": "Marcos Diaz (SRE Manager)",
                "scribe": "Lucia Blanco (DevOps)",
            },
            "communication_cadence_minutes": 30,
            "customer_communication": "Estamos investigando un incremento en la latencia P95 del servicio de pólizas. Siguiente reporte en 30m.",
        }

        res = validator.validate_report(valid_report)
        assert res["status"] == "valid"
        assert res["severity"] == "P1"

    def test_negative_missing_incident_roles_or_cadence_fails(self) -> None:
        """
        [RA-6.1 NEGATIVE] Demuestra que un reporte informal sin roles ni cadencia
        es rechazado por no garantizar mando unificado.
        """
        validator = IncidentReportValidator()
        incomplete_report = {
            "severity": "P1",
            "roles": {"incident_commander": "Elena"},  # Falta coms y scribe
            "communication_cadence_minutes": 0,
            "customer_communication": "",
        }

        with pytest.raises(ValueError, match="missing required command role"):
            validator.validate_report(incomplete_report)


class TestRA62ForensicTraceRootCause:
    """
    RA-6.2: Diagnóstico forense distinguiendo la causa raíz del síntoma emergente.
    """

    def test_positive_correct_span_id_and_component_attributed(self) -> None:
        """
        [RA-6.2 POSITIVE] Confirma que el análisis forense identifica el span causal
        hoja donde se originó el error (500 en normalización de fechas).
        """
        analyzer = ForensicTraceAnalyzer()
        trace = [
            TraceSpan(
                span_id="span-root-gateway",
                name="POST /v1/chat/completions",
                component="litellm.proxy",
                status_code=500,
                error_message="Downstream service returned empty or corrupt context",
                parent_span_id=None,
                is_causal_root=False,  # Síntoma
            ),
            TraceSpan(
                span_id="span-tool-normalize",
                name="tool_call: date_normalize",
                component="tool.date_normalize",
                status_code=500,
                error_message="ValueError: Formato de fecha '29/02/2026' no valido para anio no bisiesto",
                parent_span_id="span-root-gateway",
                is_causal_root=True,  # Causa raíz real
            ),
        ]

        diagnosis = {
            "componente": "tool.date_normalize",
            "span_id": "span-tool-normalize",
            "categoria": "datos",
            "evidencia": "Span status=500; ValueError: Formato de fecha 29/02/2026 invalido.",
        }

        result = analyzer.evaluate_root_cause_diagnosis(trace, diagnosis)
        assert result["status"] == "verified"
        assert result["causal_span_id"] == "span-tool-normalize"

    def test_negative_attributing_to_symptom_span_fails(self) -> None:
        """
        [RA-6.2 NEGATIVE] Demuestra que atribuir la causa raíz al síntoma visible
        del gateway (en lugar del span que falló) es rechazado en la evaluación forense.
        """
        analyzer = ForensicTraceAnalyzer()
        trace = [
            TraceSpan(
                span_id="span-root-gateway",
                name="POST /v1/chat/completions",
                component="litellm.proxy",
                status_code=500,
                error_message="Gateway 500 error",
                parent_span_id=None,
                is_causal_root=False,
            ),
            TraceSpan(
                span_id="span-tool-normalize",
                name="tool_call",
                component="tool.date_normalize",
                status_code=500,
                error_message="ValueError",
                parent_span_id="span-root-gateway",
                is_causal_root=True,
            ),
        ]

        symptom_diagnosis = {
            "componente": "litellm.proxy",
            "span_id": "span-root-gateway",  # Síntoma!
            "categoria": "infra",
            "evidencia": "El proxy devolvio 500 al cliente.",
        }

        with pytest.raises(ValueError, match="is an emergent symptom, not the causal root"):
            analyzer.evaluate_root_cause_diagnosis(trace, symptom_diagnosis)


class TestRA63BlamelessPostmortem:
    """
    RA-6.3: Postmortem blameless sistémico conforme a Google SRE sin culpabilización personal.
    """

    def test_positive_systemic_blameless_postmortem_with_action_owners(self) -> None:
        """
        [RA-6.3 POSITIVE] Confirma que un postmortem enfocado en procesos sistémicos,
        con cronología y acciones con dueños definidos pasa la validación.
        """
        validator = BlamelessPostmortemValidator()
        valid_postmortem = {
            "titulo": "Postmortem Incidente INC-2026-088: Error en Normalizacion de Fechas",
            "fecha": "2026-10-10",
            "cronologia": [
                "10:14 UTC - Alerta P1: Tasa de 500 supera el 2% en endpoint de extraccion.",
                "10:20 UTC - IC asume mando e inicia puente de comunicaciones.",
                "10:35 UTC - Contencion: activacion de fallback a parser estandar.",
            ],
            "causa_raiz_sistemica": "La biblioteca de normalizacion carecia de validacion de anos bisiestos en la suite de pruebas unitarias y el pipeline de CI/CD no ejecutaba regresiones sinteticas de fechas limite.",
            "acciones_correctivas": [
                {
                    "descripcion": "Incorporar suite parametrizada de fechas limite en pruebas unitarias de la herramienta.",
                    "owner": "Equipo Backend Core",
                    "prioridad": "P0",
                },
                {
                    "descripcion": "Implementar circuit breaker con fallback automatico en fallos de parsing de herramientas.",
                    "owner": "Equipo Plataforma SRE",
                    "prioridad": "P1",
                },
            ],
        }

        res = validator.validate_postmortem(valid_postmortem)
        assert res["status"] == "valid"
        assert res["is_blameless"] is True

    def test_negative_individual_blame_violates_blameless_culture(self) -> None:
        """
        [RA-6.3 NEGATIVE] Demuestra que atribuir culpa personal o negligencia individual
        viola la cultura blameless y es bloqueado formalmente.
        """
        validator = BlamelessPostmortemValidator()
        blaming_postmortem = {
            "titulo": "Postmortem con Culpa",
            "fecha": "2026-10-10",
            "cronologia": ["Incidente iniciado."],
            "causa_raiz_sistemica": "El incidente ocurrio por descuido de un desarrollador novato que no presto atencion al commit.",
            "acciones_correctivas": [
                {"descripcion": "Reanudar", "owner": "Nadie", "prioridad": "P1"}
            ],
        }

        with pytest.raises(ValueError, match="violates Google SRE blameless culture"):
            validator.validate_postmortem(blaming_postmortem)


class TestRA64RegressionLifecycle:
    """
    RA-6.4: Regression eval ejecutable que falla antes del hotfix y pasa después.
    """

    def test_positive_regression_fails_before_hotfix_and_passes_after(self) -> None:
        """
        [RA-6.4 POSITIVE] Confirma que el ciclo de vida de regresión verifica
        que el test falla deterministamente ante el bug y pasa tras la corrección.
        """
        manager = RegressionLifecycleManager()

        class BuggyNormalizer:
            def normalize_date(self, d_str: str) -> str:
                # Bug: crashes on leap year Feb 29
                if "29/02/2026" in d_str:
                    raise ValueError("Año no bisiesto")
                return "2026-01-01"

        class PatchedNormalizer:
            def normalize_date(self, d_str: str) -> str:
                # Hotfix: gracefully handles invalid date with sanitized fallback
                if "29/02/2026" in d_str:
                    return "2026-02-28"  # Normalized clamp
                return "2026-01-01"

        def regression_test(system: Any) -> bool:
            res = system.normalize_date("29/02/2026")
            return res == "2026-02-28"

        verification = manager.verify_regression_lifecycle(
            test_fn=regression_test,
            buggy_system=BuggyNormalizer(),
            patched_system=PatchedNormalizer(),
        )

        assert verification["failed_before_hotfix"] is True
        assert verification["passed_after_hotfix"] is True

    def test_negative_test_that_passes_before_hotfix_is_rejected(self) -> None:
        """
        [RA-6.4 NEGATIVE] Demuestra que un test de regresión 'falso positivo'
        que ya pasa antes del arreglo es rechazado por no reproducir el defecto.
        """
        manager = RegressionLifecycleManager()

        class SystemAlwaysSame:
            def ping(self) -> bool:
                return True

        # Test does not reproduce any bug
        def trivial_test(sys: Any) -> bool:
            return sys.ping()

        with pytest.raises(ValueError, match="The test passed on the buggy system before the hotfix was applied"):
            manager.verify_regression_lifecycle(
                test_fn=trivial_test,
                buggy_system=SystemAlwaysSame(),
                patched_system=SystemAlwaysSame(),
            )
