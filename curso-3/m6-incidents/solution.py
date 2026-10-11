from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TraceSpan:
    span_id: str
    name: str
    component: str
    status_code: int
    error_message: str | None
    parent_span_id: str | None
    is_causal_root: bool = False


class IncidentReportValidator:
    REQUIRED_ROLES = ("incident_commander", "communications_lead", "scribe")

    def validate_report(self, report: dict[str, Any]) -> dict[str, Any]:
        roles = report.get("roles", {})
        for r in self.REQUIRED_ROLES:
            val = roles.get(r)
            if not val or not str(val).strip():
                raise ValueError(f"Incident report missing required command role: '{r}'.")

        sev = str(report.get("severity", "")).upper()
        if sev not in ("P1", "P2", "P3", "SEV-1", "SEV-2", "SEV-3"):
            raise ValueError(f"Invalid incident severity level: '{sev}'.")

        cadence = report.get("communication_cadence_minutes")
        if not isinstance(cadence, (int, float)) or cadence <= 0:
            raise ValueError("Incident report must define an explicit communication cadence in minutes (>0).")

        comm = str(report.get("customer_communication", "")).strip()
        if len(comm) < 15:
            raise ValueError("Incident report must include an initial customer communication draft (≥15 chars).")

        return {
            "status": "valid",
            "severity": sev,
            "roles_assigned": list(self.REQUIRED_ROLES),
        }


class ForensicTraceAnalyzer:
    def evaluate_root_cause_diagnosis(
        self,
        trace_spans: list[TraceSpan],
        diagnosis: dict[str, Any],
    ) -> dict[str, Any]:
        req_fields = ("componente", "span_id", "categoria", "evidencia")
        for f in req_fields:
            if f not in diagnosis:
                raise ValueError(f"Root cause diagnosis missing field '{f}'.")

        cat = str(diagnosis["categoria"]).lower()
        if cat not in ("infra", "datos", "semantica"):
            raise ValueError(f"Invalid root cause category '{cat}'. Must be 'infra', 'datos', or 'semantica'.")

        target_span_id = str(diagnosis["span_id"]).strip()
        causal_span = next((s for s in trace_spans if s.is_causal_root), None)
        symptom_spans = [s for s in trace_spans if not s.is_causal_root and s.status_code >= 400]

        if not causal_span:
            raise ValueError("Trace contains no planted causal root span.")

        # If user pointed to symptom instead of causal root span
        if target_span_id != causal_span.span_id:
            symptom_match = next((s for s in symptom_spans if s.span_id == target_span_id), None)
            if symptom_match:
                raise ValueError(
                    f"Forensic attribution error: Span '{target_span_id}' ({symptom_match.component}) is an emergent symptom, "
                    f"not the causal root. Real failure occurred in '{causal_span.span_id}' ({causal_span.component})."
                )
            raise ValueError(f"Span '{target_span_id}' is not the causal span.")

        return {
            "status": "verified",
            "causal_span_id": causal_span.span_id,
            "component": causal_span.component,
        }


class BlamelessPostmortemValidator:
    FORBIDDEN_BLAME_PHRASES = (
        "error del desarrollador",
        "descuido de",
        "desarrollador cometio",
        "culpa de",
        "negligencia de",
        "developer error",
        "fault of",
        "human negligence",
        "accidental mistake by",
    )

    def validate_postmortem(self, doc: dict[str, Any]) -> dict[str, Any]:
        required = ("titulo", "fecha", "cronologia", "causa_raiz_sistemica", "acciones_correctivas")
        for r in required:
            if r not in doc:
                raise ValueError(f"Postmortem missing required section '{r}'.")

        narrative = (
            str(doc["causa_raiz_sistemica"])
            + " "
            + " ".join(str(step) for step in doc.get("cronologia", []))
        ).lower()

        # Check for individual finger-pointing
        for phrase in self.FORBIDDEN_BLAME_PHRASES:
            if phrase in narrative:
                raise ValueError(
                    "Postmortem violates Google SRE blameless culture: Personal blame and finger-pointing "
                    "are strictly prohibited. Focus must be on systemic process safeguards, missing tests, and automation gaps."
                )

        acciones = doc.get("acciones_correctivas", [])
        if not isinstance(acciones, list) or len(acciones) < 1:
            raise ValueError("Postmortem must contain at least one corrective action item.")

        for a in acciones:
            if not isinstance(a, dict):
                raise ValueError("Corrective actions must be structured dictionaries.")
            if not a.get("descripcion") or not a.get("owner") or not a.get("prioridad"):
                raise ValueError("Each corrective action item must have 'descripcion', 'owner', and 'prioridad'.")

        return {
            "status": "valid",
            "is_blameless": True,
            "actions_count": len(acciones),
        }


class RegressionLifecycleManager:
    def verify_regression_lifecycle(
        self,
        test_fn: Callable[[Any], bool],
        buggy_system: Any,
        patched_system: Any,
    ) -> dict[str, bool]:
        # 1. Test MUST fail before hotfix
        try:
            passed_on_buggy = test_fn(buggy_system)
        except Exception:
            passed_on_buggy = False

        if passed_on_buggy:
            raise ValueError(
                "Regression test validation failed: The test passed on the buggy system before the hotfix was applied. "
                "A valid regression test MUST deterministically fail against the defect."
            )

        # 2. Test MUST pass after hotfix
        try:
            passed_on_patched = test_fn(patched_system)
        except Exception as err:
            raise ValueError(
                f"Regression test validation failed: The test failed on the patched system after hotfix: {err}"
            )

        if not passed_on_patched:
            raise ValueError("Regression test validation failed: Test returned False on patched system.")

        return {
            "failed_before_hotfix": True,
            "passed_after_hotfix": True,
            "lifecycle_verified": True,
        }
