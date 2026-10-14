# STUB: implement the capstone here. See README.md. Run: uv run pytest curso-3/m7-capstone/tests
"""C3-M7 capstone: enterprise delivery system and package validator (student stub)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class BudgetExceededError(Exception):
    """Raised when a request would exceed a virtual key's hard budget cap.

    The message must contain "hard budget cap exceeded".
    """


class FailoverActiveError(Exception):
    """Raised when failover routing is active and cannot serve the request."""


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
    """Gateway with budgets, guardrails, PII redaction and model failover."""

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
        """Register a virtual key with a hard budget for a tenant."""
        raise NotImplementedError("Implement virtual key registration")

    def process_request(
        self,
        virtual_key_id: str,
        user_jwt: dict[str, Any],
        prompt: str,
        cost_usd: float = 0.002,
    ) -> dict[str, Any]:
        """Process one request through the delivery pipeline and update metrics.

        Pipeline: hard budget check (unknown key raises KeyError; overspend raises
        BudgetExceededError), input guardrails (blocked prompts return status
        "blocked" with a reason and no model), PII redaction, attribution headers
        (end-user and tenant identity), and primary/secondary model routing.

        Success returns status "success" plus model_used, failover_triggered,
        sanitized_prompt, response, attribution_headers, spend_usd and
        redacted_entities_count.
        """
        raise NotImplementedError("Implement the request pipeline")


class EnterprisePackageValidator:
    """Validates the documentation package under delivery/."""

    def validate_delivery_package(self, delivery_dir: Path) -> dict[str, Any]:
        """Check that rfc.yaml, adr.md, threat_model.md, runbook.md and acceptance.md
        exist and satisfy the formal schema described in README.md.

        Missing files raise FileNotFoundError. Schema violations raise ValueError
        with messages naming the file and the missing element, e.g.
        "rfc.yaml missing mandatory section '<name>'". On success return
        {"status": "APPROVED", "files_validated": list[str]}.
        """
        raise NotImplementedError("Implement delivery package validation")
