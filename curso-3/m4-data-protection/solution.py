from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ThreatItem:
    category: str
    description: str
    severity: str
    mitigation: str


class ThreatPrivacyModelValidator:
    VALID_STRIDE = {
        "spoofing",
        "tampering",
        "repudiation",
        "information_disclosure",
        "denial_of_service",
        "elevation_of_privilege",
    }

    VALID_LINDDUN = {
        "linkability",
        "identifiability",
        "non_repudiation",
        "detectability",
        "disclosure_of_information",
        "unawareness",
        "non_compliance",
    }

    def validate_stride(self, threats: list[ThreatItem]) -> dict[str, Any]:
        if len(threats) < 3:
            raise ValueError("STRIDE model requires at least 3 threat assessments.")

        for t in threats:
            cat = t.category.lower().replace(" ", "_")
            if cat not in self.VALID_STRIDE:
                raise ValueError(f"Invalid STRIDE category '{t.category}'.")

            if t.severity.lower() in ("critical", "high"):
                if not t.mitigation or len(t.mitigation.strip()) < 15:
                    raise ValueError(
                        f"High/Critical threat '{t.category}' requires an architectural mitigation (≥15 chars)."
                    )

        return {"status": "valid", "count": len(threats)}

    def validate_linddun(self, privacy_threats: list[ThreatItem]) -> dict[str, Any]:
        if len(privacy_threats) < 3:
            raise ValueError("LINDDUN model requires at least 3 privacy threat assessments.")

        for t in privacy_threats:
            cat = t.category.lower().replace(" ", "_")
            if cat not in self.VALID_LINDDUN:
                raise ValueError(f"Invalid LINDDUN category '{t.category}'.")

            if t.severity.lower() in ("critical", "high"):
                if not t.mitigation or len(t.mitigation.strip()) < 15:
                    raise ValueError(
                        f"High/Critical privacy threat '{t.category}' requires a verified privacy safeguard."
                    )

        return {"status": "valid", "count": len(privacy_threats)}


class LegalClassificationAnalyzer:
    FORBIDDEN_FALLACIES = (
        "anonimizacion",
        "anonimización",
        "anónimo",
        "anonimo",
        "sale del rgpd",
        "fuera del rgpd",
        "no aplica el rgpd",
        "exits gdpr",
    )

    def classify_tokenization_operation(
        self,
        has_reversible_vault: bool,
        classification_claim: str,
        justification: str,
    ) -> dict[str, Any]:
        claim_lower = classification_claim.lower()
        just_lower = justification.lower()

        if has_reversible_vault:
            for term in self.FORBIDDEN_FALLACIES:
                if term in claim_lower or term in just_lower:
                    raise ValueError(
                        "Technical & Legal Misclassification: Reversible tokenization with a stored mapping vault "
                        "is strictly PSEUDONYMIZATION under GDPR Art. 4(5) and Recital 26. "
                        "Data remains personal data, and GDPR obligations (legal basis, DPIA, security) continue to apply."
                    )

        return {
            "legal_status": "pseudonymized_data",
            "gdpr_applies": True,
            "requires_dpia": True,
            "requires_legal_basis": True,
            "is_anonymous": False,
        }


@dataclass
class PresidioEntityMetric:
    entity_type: str
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    support: int


class PresidioEvaluator:
    UNREALISTIC_CLAIMS = (
        "100% de recall",
        "100% recall",
        "recall del 100%",
        "cero falsos negativos",
        "enmascara el 100%",
        "bloqueo del 100%",
        "100% pii redaction",
    )

    def validate_claims(self, claims: list[str]) -> None:
        for c in claims:
            c_low = c.lower()
            for pattern in self.UNREALISTIC_CLAIMS:
                if pattern in c_low:
                    raise ValueError(
                        f"Claim '{c}' is factually misleading: Named Entity Recognition is statistical "
                        "and probabilistic. Promising 100% recall or zero false negatives is rejected."
                    )

    def evaluate_gold_set(
        self,
        gold_samples: list[dict[str, Any]],
        predictions: list[dict[str, Any]],
    ) -> dict[str, PresidioEntityMetric]:
        counts: dict[str, dict[str, int]] = {}

        # Initialize counts
        for sample in gold_samples:
            for ent in sample.get("entities", []):
                etype = ent.get("type", "UNKNOWN")
                if etype not in counts:
                    counts[etype] = {"tp": 0, "fp": 0, "fn": 0, "support": 0}
                counts[etype]["support"] += 1

        for pred in predictions:
            for ent in pred.get("entities", []):
                etype = ent.get("type", "UNKNOWN")
                if etype not in counts:
                    counts[etype] = {"tp": 0, "fp": 0, "fn": 0, "support": 0}

        # Compare predictions with gold set
        pred_map = {p["id"]: {(e["type"], e["start"], e["end"]) for e in p.get("entities", [])} for p in predictions}
        gold_map = {g["id"]: {(e["type"], e["start"], e["end"]) for e in g.get("entities", [])} for g in gold_samples}

        for sid, g_ents in gold_map.items():
            p_ents = pred_map.get(sid, set())

            # True Positives: match in both
            for e in g_ents:
                etype = e[0]
                if e in p_ents:
                    counts[etype]["tp"] += 1
                else:
                    counts[etype]["fn"] += 1

            # False Positives: in prediction but not in gold
            for e in p_ents:
                etype = e[0]
                if e not in g_ents:
                    counts[etype]["fp"] += 1

        metrics: dict[str, PresidioEntityMetric] = {}
        for etype, data in counts.items():
            tp = data["tp"]
            fp = data["fp"]
            fn = data["fn"]
            support = data["support"]

            prec = tp / float(tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / float(tp + fn) if (tp + fn) > 0 else 0.0

            metrics[etype] = PresidioEntityMetric(
                entity_type=etype,
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                precision=round(prec, 4),
                recall=round(rec, 4),
                support=support,
            )

        return metrics


class GovernanceMapValidator:
    def validate_governance_map(self, doc: dict[str, Any]) -> dict[str, Any]:
        required_layers = ("data_protection", "ai_regulation", "management_system", "risk_framework")
        for layer in required_layers:
            if layer not in doc:
                raise ValueError(f"Missing governance layer: '{layer}'.")

        gdpr = doc["data_protection"]
        ai_act = doc["ai_regulation"]
        iso = doc["management_system"]
        nist = doc["risk_framework"]

        # Check for mutual exclusivity fallacy
        narrative = str(doc.get("framework_relationship", "")).lower()
        if "excluyente" in narrative or "reemplaza" in narrative or "anula" in narrative:
            raise ValueError(
                "Governance frameworks operate in complementary layers: "
                "GDPR governs personal data, EU AI Act governs system market entry, "
                "ISO 42001 governs organizational management, and NIST AI RMF governs risk treatment."
            )

        zdr = doc.get("zero_data_retention", {})
        if not zdr.get("has_agreement") or not zdr.get("documented_exceptions"):
            raise ValueError(
                "Zero Data Retention (ZDR) must document contractual terms and explicit provider exceptions "
                "(e.g. abuse monitoring windows or server-side caching)."
            )

        return {
            "status": "valid",
            "layers_validated": 4,
            "zdr_active": True,
        }
