from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class BudgetExceededError(Exception):
    pass


class FailoverActiveError(Exception):
    pass


@dataclass
class VirtualKey:
    key_id: str
    tenant: str
    max_budget_usd: float
    current_spend_usd: float = 0.0


@dataclass
class DeliverySystemMetrics:
    total_requests: int = 0
    successful_requests: int = 0
    failover_requests: int = 0
    blocked_by_guardrails: int = 0
    redacted_pii_entities: int = 0


class EnterpriseDeliverySystem:
    def __init__(
        self,
        primary_model: str = "openai/gpt-4o-mini",
        secondary_model: str = "anthropic/claude-3-haiku",
        simulate_primary_failure: bool = False,
    ) -> None:
        self.primary_model = primary_model
        self.secondary_model = secondary_model
        self.simulate_primary_failure = simulate_primary_failure
        self.virtual_keys: dict[str, VirtualKey] = {}
        self.pii_vault: dict[str, str] = {}
        self.metrics = DeliverySystemMetrics()

    def register_virtual_key(self, key_id: str, tenant: str, max_budget_usd: float) -> None:
        self.virtual_keys[key_id] = VirtualKey(
            key_id=key_id,
            tenant=tenant,
            max_budget_usd=max_budget_usd,
        )

    def _redact_pii(self, text: str) -> tuple[str, int]:
        count = 0
        redacted = text

        # Regex for Spanish NIF/NIE (8 digits + 1 letter or X/Y/Z + 7 digits + 1 letter)
        nif_pattern = r"\b[0-9XYZxyz][0-9]{7}[A-Za-z]\b"
        for match in re.findall(nif_pattern, redacted):
            token = f"[NIF_{len(self.pii_vault) + 1}]"
            self.pii_vault[token] = match
            redacted = redacted.replace(match, token)
            count += 1

        # Regex for common email
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        for match in re.findall(email_pattern, redacted):
            token = f"[EMAIL_{len(self.pii_vault) + 1}]"
            self.pii_vault[token] = match
            redacted = redacted.replace(match, token)
            count += 1

        return redacted, count

    def _evaluate_guardrails(self, text: str) -> tuple[bool, str | None]:
        # Adversarial pattern block
        jailbreaks = ["ignore previous instructions", "ignora todas las instrucciones", "system override mode"]
        text_lower = text.lower()
        for jb in jailbreaks:
            if jb in text_lower:
                return False, f"Prompt injection / jailbreak detected: '{jb}'"
        return True, None

    def process_request(
        self,
        virtual_key_id: str,
        user_jwt: dict[str, Any],
        prompt: str,
        cost_usd: float = 0.002,
    ) -> dict[str, Any]:
        self.metrics.total_requests += 1

        # 1. Hard Budget enforcement
        key = self.virtual_keys.get(virtual_key_id)
        if not key:
            raise KeyError(f"Virtual key '{virtual_key_id}' not found.")

        if (key.current_spend_usd + cost_usd) > key.max_budget_usd:
            raise BudgetExceededError(
                f"Virtual key '{virtual_key_id}' hard budget cap exceeded: "
                f"${key.current_spend_usd:.3f} + ${cost_usd:.3f} > ${key.max_budget_usd:.3f}."
            )

        # 2. Input Guardrails
        is_safe, block_reason = self._evaluate_guardrails(prompt)
        if not is_safe:
            self.metrics.blocked_by_guardrails += 1
            return {
                "status": "blocked",
                "reason": block_reason,
                "sanitized_prompt": prompt,
                "model_used": None,
                "failover_triggered": False,
            }

        # 3. PII Redaction Pipeline
        sanitized_prompt, redacted_count = self._redact_pii(prompt)
        self.metrics.redacted_pii_entities += redacted_count

        # 4. Identity Extraction & Downstream Headers
        user_id = str(user_jwt.get("sub", "anon_user"))
        tenant_id = str(user_jwt.get("tenant_id", key.tenant))
        attribution_headers = {
            "Authorization": f"Bearer {virtual_key_id}",
            "X-End-User-Id": user_id,
            "X-Audit-Tenant-Id": tenant_id,
        }

        # 5. Model Routing & Automated Failover
        failover_active = False
        if self.simulate_primary_failure:
            model_used = self.secondary_model
            failover_active = True
            self.metrics.failover_requests += 1
        else:
            model_used = self.primary_model

        # Update budget
        key.current_spend_usd = round(key.current_spend_usd + cost_usd, 4)
        self.metrics.successful_requests += 1

        response_content = f"Dictamen pericial procesado sobre documento saneado: {sanitized_prompt[:60]}..."

        return {
            "status": "success",
            "model_used": model_used,
            "failover_triggered": failover_active,
            "sanitized_prompt": sanitized_prompt,
            "response": response_content,
            "attribution_headers": attribution_headers,
            "spend_usd": key.current_spend_usd,
            "redacted_entities_count": redacted_count,
        }


class EnterprisePackageValidator:
    def validate_delivery_package(self, delivery_dir: Path) -> dict[str, Any]:
        required_files = ("rfc.yaml", "adr.md", "threat_model.md", "runbook.md", "acceptance.md")
        for fname in required_files:
            fpath = delivery_dir / fname
            if not fpath.exists():
                raise FileNotFoundError(f"Missing required delivery document: '{fname}'.")

        # 1. RFC validation
        rfc_text = (delivery_dir / "rfc.yaml").read_text(encoding="utf-8")
        for section in ("titulo:", "invariantes:", "dependencias_datos:", "metricas:", "non_goals:", "supuestos:"):
            if section not in rfc_text:
                raise ValueError(f"rfc.yaml missing mandatory section '{section}'.")
        if "umbral_numerico:" not in rfc_text:
            raise ValueError("rfc.yaml must specify numeric thresholds ('umbral_numerico').")

        # 2. ADR validation
        adr_text = (delivery_dir / "adr.md").read_text(encoding="utf-8")
        for section in ("## Estado", "## Contexto", "## Decision", "## Opciones consideradas", "## Consecuencias"):
            if section not in adr_text:
                raise ValueError(f"adr.md missing mandatory MADR section '{section}'.")
        if "Negativas:" not in adr_text and "negativas:" not in adr_text:
            raise ValueError("adr.md strictly requires negative consequences.")

        # 3. Threat model validation
        threat_text = (delivery_dir / "threat_model.md").read_text(encoding="utf-8")
        if "STRIDE" not in threat_text or "LINDDUN" not in threat_text:
            raise ValueError("threat_model.md must cover both STRIDE and LINDDUN models.")
        threat_lower = threat_text.lower()
        if "mitigacion" not in threat_lower and "mitigación" not in threat_lower:
            raise ValueError("threat_model.md must provide explicit mitigations.")

        # 4. Runbook validation
        runbook_text = (delivery_dir / "runbook.md").read_text(encoding="utf-8")
        if "Procedimiento" not in runbook_text or "Escalado" not in runbook_text:
            raise ValueError("runbook.md must specify procedures and escalation thresholds.")

        # 5. Acceptance plan validation
        acceptance_text = (delivery_dir / "acceptance.md").read_text(encoding="utf-8")
        if "Golden Set" not in acceptance_text:
            raise ValueError("acceptance.md must define acceptance against a Golden Set.")
        if "IC 95%" not in acceptance_text and "Intervalo de Confianza" not in acceptance_text:
            raise ValueError("acceptance.md must provide 95% Confidence Intervals for thresholds.")

        return {
            "status": "APPROVED",
            "files_validated": list(required_files),
        }
