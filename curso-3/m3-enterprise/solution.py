from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class BudgetExceededError(Exception):
    pass


class UnboundedKeyError(Exception):
    pass


class NetworkPolicyViolationError(Exception):
    pass


@dataclass
class VirtualKeyConfig:
    key_id: str
    name: str
    max_budget: float | None
    current_spend: float = 0.0
    has_hard_budget: bool = True


class LiteLLMProxyGateway:
    def __init__(self, database_url: str | None = None) -> None:
        if not database_url or not database_url.strip():
            raise ValueError(
                "LiteLLM Proxy requires a persistent relational database backend (database_url) "
                "for hard budget enforcement and transaction persistence."
            )
        self.database_url = database_url
        self.keys: dict[str, VirtualKeyConfig] = {}

    def add_key(self, key: VirtualKeyConfig) -> None:
        self.keys[key.key_id] = key

    def route_request(
        self,
        key_id: str,
        estimated_cost: float,
        enforce_hard_cap: bool = True,
    ) -> dict[str, Any]:
        key = self.keys.get(key_id)
        if not key:
            raise KeyError(f"Virtual key '{key_id}' not found.")

        if enforce_hard_cap and (not key.has_hard_budget or key.max_budget is None):
            raise UnboundedKeyError(
                f"Virtual key '{key_id}' lacks a hard budget cap ('max_budget'). "
                "Enterprise policy requires deterministic expenditure ceilings."
            )

        if key.has_hard_budget and key.max_budget is not None:
            if (key.current_spend + estimated_cost) > key.max_budget:
                raise BudgetExceededError(
                    f"Hard budget exceeded for key '{key_id}': max budget is ${key.max_budget:.2f}, "
                    f"current spend ${key.current_spend:.2f}, attempted cost ${estimated_cost:.2f}."
                )

        key.current_spend = round(key.current_spend + estimated_cost, 4)
        return {
            "status": "routed",
            "key_id": key_id,
            "current_spend": key.current_spend,
            "remaining_budget": round((key.max_budget - key.current_spend) if key.max_budget else 0.0, 4),
        }


class OidcIdentityPropagator:
    def extract_claims(self, jwt_payload: dict[str, Any]) -> dict[str, str]:
        sub = str(jwt_payload.get("sub", "")).strip()
        email = str(jwt_payload.get("email", jwt_payload.get("preferred_username", ""))).strip()
        tenant = str(jwt_payload.get("tenant_id", jwt_payload.get("iss", "default"))).strip()

        if not sub:
            raise ValueError("OIDC token missing 'sub' subject claim.")

        return {
            "user_id": sub,
            "user_email": email or f"{sub}@tenant.agentik.im",
            "tenant_id": tenant,
        }

    def build_downstream_headers(
        self,
        jwt_payload: dict[str, Any],
        service_api_key: str,
        propagate_end_user: bool = True,
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {service_api_key}",
        }

        if propagate_end_user:
            claims = self.extract_claims(jwt_payload)
            headers["X-End-User-Id"] = claims["user_id"]
            headers["X-End-User-Email"] = claims["user_email"]
            headers["X-Audit-Tenant-Id"] = claims["tenant_id"]

        return headers

    def validate_attribution_headers(self, headers: dict[str, str]) -> bool:
        if not headers.get("Authorization"):
            raise ValueError("Missing application Authorization header.")

        if not headers.get("X-End-User-Id"):
            raise ValueError(
                "Audit failure: Downstream request propagates only application credentials "
                "without end-user identity attribution ('X-End-User-Id')."
            )

        return True


class NetworkPolicyValidator:
    def validate_infrastructure_plan(self, plan: dict[str, Any]) -> bool:
        resources = plan.get("resources", [])
        violations: list[str] = []

        for res in resources:
            name = res.get("name", "unnamed_resource")
            props = res.get("properties", {})

            # 1. No Public IPs
            if props.get("public_ip") is True or props.get("associate_public_ip_address") is True:
                violations.append(f"Resource '{name}' associates a public IP address.")

            # 2. No open egress to 0.0.0.0/0
            egress = props.get("egress_rules", [])
            for rule in egress:
                cidr = rule.get("cidr_block", "")
                if cidr in ("0.0.0.0/0", "::/0"):
                    violations.append(f"Resource '{name}' contains unrestricted egress to '{cidr}'.")

            # 3. Private Link / VPC Endpoints for LLM services
            if props.get("target_service") == "llm_api":
                if not props.get("uses_vpc_endpoint", False) and not props.get("uses_privatelink", False):
                    violations.append(f"LLM API client resource '{name}' is not routed via VPC Endpoint/PrivateLink.")

        if violations:
            raise NetworkPolicyViolationError(
                f"Policy-as-Code rejected network plan with {len(violations)} security violations: "
                + "; ".join(violations)
            )

        return True


class SupplyChainAuditor:
    def audit_document(self, doc: dict[str, Any]) -> dict[str, Any]:
        image_ref = str(doc.get("image_reference", ""))
        sbom_format = str(doc.get("sbom_format", "")).upper()
        rotation = str(doc.get("key_rotation_procedure", ""))
        narrative = str(doc.get("compliance_narrative", "")).lower()

        # Check for SOC 2 antipattern / fallacy
        if "log es compatible con soc 2" in narrative or "compatible con soc 2" in narrative or "compatible con soc2" in narrative:
            raise ValueError(
                "Calling an operational log file 'compatible con SOC 2' is a conceptual fallacy. "
                "A log file is audit evidence for criteria (CC6/CC7), but SOC 2 is an organizational audit report."
            )

        # Check image digest pinning
        if not re.search(r"@sha256:[a-fA-F0-9]{64}", image_ref):
            raise ValueError(
                f"Gateway image reference '{image_ref}' must be pinned by an immutable SHA-256 digest, not a mutable tag."
            )

        # Check SBOM format
        if sbom_format not in ("SPDX", "CYCLONEDX"):
            raise ValueError(f"Invalid or missing SBOM format '{sbom_format}'. Must be SPDX or CycloneDX.")

        # Check rotation procedure
        if len(rotation.strip()) < 15 or "rotacion" not in rotation.lower():
            raise ValueError("Supply chain audit requires a documented master key rotation procedure.")

        return {
            "status": "compliant",
            "image_pinned": True,
            "sbom_format": sbom_format,
        }
