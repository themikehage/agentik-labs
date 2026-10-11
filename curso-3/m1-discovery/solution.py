from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DiscoveryFinding:
    id: str
    area: str
    summary: str
    evidence: str
    risk_severity: str  # "critical", "high", "medium", "low"
    is_cosmetic: bool = False


class DiscoveryAnalyzer:
    _SEVERITY_WEIGHTS = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    def identify_highest_risk_finding(
        self, findings: list[DiscoveryFinding]
    ) -> tuple[DiscoveryFinding, str]:
        if not findings:
            raise ValueError("Discovery findings list cannot be empty.")

        # Non-cosmetic structural findings prioritized by severity
        structural_findings = [f for f in findings if not f.is_cosmetic]
        if not structural_findings:
            raise ValueError("All findings were marked as cosmetic; at least one structural finding is required.")

        highest = max(
            structural_findings,
            key=lambda f: (self._SEVERITY_WEIGHTS.get(f.risk_severity, 0), len(f.evidence)),
        )

        if not highest.evidence or len(highest.evidence.strip()) < 10:
            raise ValueError(f"Finding {highest.id} lacks substantiated textual evidence.")

        return highest, highest.evidence


class StakeholderProcessMapper:
    def validate_stakeholder_map(self, data: dict[str, Any]) -> dict[str, Any]:
        stakeholders = data.get("stakeholders", [])
        if not isinstance(stakeholders, list) or len(stakeholders) < 2:
            raise ValueError("Stakeholder map must contain a list of at least 2 stakeholders.")

        has_decisor = False
        has_afectado = False

        for s in stakeholders:
            role = s.get("role_type", "").lower()
            assumption = s.get("supuesto", "") or s.get("assumption", "")

            if not assumption or len(str(assumption).strip()) < 5:
                raise ValueError(f"Stakeholder {s.get('name', 'unknown')} must include an explicit assumption ('supuesto').")

            if role == "decisor":
                has_decisor = True
            elif role == "afectado":
                has_afectado = True

        if not has_decisor:
            raise ValueError("Stakeholder map must contain at least one decision-maker ('decisor').")
        if not has_afectado:
            raise ValueError("Stakeholder map must contain at least one affected stakeholder ('afectado').")

        return data

    def validate_process_map(self, data: dict[str, Any]) -> dict[str, Any]:
        steps = data.get("steps", [])
        exceptions = data.get("exceptions", [])
        assumptions = data.get("assumptions", [])

        if not isinstance(steps, list) or len(steps) < 2:
            raise ValueError("Process map must contain at least 2 sequential steps.")

        if not isinstance(exceptions, list) or len(exceptions) < 1:
            raise ValueError("Process map must explicitly declare at least one process exception.")

        for exc in exceptions:
            if not str(exc).strip():
                raise ValueError("Process exception cannot be empty.")

        if not isinstance(assumptions, list) or len(assumptions) < 1:
            raise ValueError("Process map must declare at least one explicit assumption.")

        return data


class RfcSchemaValidator:
    REQUIRED_KEYS = (
        "titulo",
        "invariantes",
        "dependencias_datos",
        "metricas",
        "non_goals",
        "supuestos",
    )

    def validate(self, rfc: dict[str, Any]) -> dict[str, Any]:
        for key in self.REQUIRED_KEYS:
            if key not in rfc:
                raise ValueError(f"Missing required RFC section: '{key}'.")

        if not str(rfc["titulo"]).strip():
            raise ValueError("RFC 'titulo' must be non-empty.")

        for list_key in ("invariantes", "dependencias_datos", "non_goals", "supuestos"):
            val = rfc[list_key]
            if not isinstance(val, list) or len(val) < 1:
                raise ValueError(f"RFC '{list_key}' must be a non-empty list of items.")
            for item in val:
                if not str(item).strip():
                    raise ValueError(f"RFC '{list_key}' cannot contain empty strings.")

        metricas = rfc["metricas"]
        if not isinstance(metricas, list) or len(metricas) < 1:
            raise ValueError("RFC 'metricas' must be a non-empty list of measurable criteria.")

        for m in metricas:
            if not isinstance(m, dict):
                raise ValueError("Each item in 'metricas' must be a dictionary.")

            name = m.get("nombre")
            if not name or not str(name).strip():
                raise ValueError("Metric must have a valid 'nombre'.")

            threshold = m.get("umbral_numerico")
            if threshold is None or not isinstance(threshold, (int, float)):
                raise ValueError(
                    f"Metric '{name}' lacks a valid numerical threshold ('umbral_numerico'). "
                    "Qualitative descriptions without quantifiable thresholds are strictly rejected."
                )

            unit = m.get("unidad")
            if not unit or not str(unit).strip():
                raise ValueError(f"Metric '{name}' must declare a physical/logical 'unidad'.")

        return rfc


@dataclass
class DataSourceDimension:
    name: str
    existe: bool
    acceso: str
    calidad: float
    gobernanza: str
    latencia_min: float
    decision: str


class DataReadinessEvaluator:
    VALID_DIMENSIONS = ("existe", "acceso", "calidad", "gobernanza", "latencia_min")
    VALID_DECISIONS = ("incluir", "remediar", "excluir")

    def evaluate_source(self, src: dict[str, Any]) -> str:
        for dim in self.VALID_DIMENSIONS:
            if dim not in src:
                raise ValueError(f"Data source '{src.get('name', 'unnamed')}' is missing dimension '{dim}'.")

        existe = bool(src["existe"])
        acceso = str(src["acceso"]).lower()
        calidad = float(src["calidad"])
        gobernanza = str(src["gobernanza"]).lower()
        latencia_min = float(src["latencia_min"])

        if not (0.0 <= calidad <= 1.0):
            raise ValueError("Calidad must be a float between 0.0 and 1.0.")

        if not existe or acceso in ("none", "bloqueado") or calidad < 0.5 or latencia_min > 2880:
            return "excluir"

        if calidad < 0.85 or acceso == "manual" or gobernanza in ("pii", "restringido"):
            return "remediar"

        return "incluir"

    def evaluate_inventory(self, inventory: dict[str, Any]) -> dict[str, Any]:
        sources = inventory.get("sources", [])
        if not isinstance(sources, list) or len(sources) < 1:
            raise ValueError("Inventory must contain a non-empty list of 'sources'.")

        evaluated = []
        for s in sources:
            decision = self.evaluate_source(s)
            item = dict(s)
            item["decision"] = decision
            evaluated.append(item)

        return {"sources": evaluated}
