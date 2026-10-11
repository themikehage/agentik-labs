"""
Reference tests for Curso 3 M3 - Integración Enterprise, Proxy y Red.
Validates:
- RA-3.1: LiteLLM Proxy hard budget caps with deterministic cutoff (positive & negative).
- RA-3.2: OIDC end-user identity propagation downstream with audit attribution (positive & negative).
- RA-3.3: Network Policy-as-Code rejecting public IPs and 0.0.0.0/0 egress (positive & negative).
- RA-3.4: Supply chain image pinning, SBOM and SOC 2 log fallacy rejection (positive & negative).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c3_m3_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

LiteLLMProxyGateway = _mod.LiteLLMProxyGateway
VirtualKeyConfig = _mod.VirtualKeyConfig
BudgetExceededError = _mod.BudgetExceededError
UnboundedKeyError = _mod.UnboundedKeyError
OidcIdentityPropagator = _mod.OidcIdentityPropagator
NetworkPolicyValidator = _mod.NetworkPolicyValidator
NetworkPolicyViolationError = _mod.NetworkPolicyViolationError
SupplyChainAuditor = _mod.SupplyChainAuditor


class TestRA31HardBudgetVirtualKeys:
    """
    RA-3.1: Configuración de proxy con presupuestos duros por clave virtual.
    """

    def test_positive_hard_budget_enforces_limit_and_routes_within_cap(self) -> None:
        """
        [RA-3.1 POSITIVE] Confirma que una clave virtual con max_budget enruta
        peticiones mientras haya saldo y corta de inmediato al agotarse.
        """
        gateway = LiteLLMProxyGateway(database_url="postgresql://user:pass@db.internal:5432/litellm")
        key = VirtualKeyConfig(
            key_id="sk-finance-dept",
            name="Finance Operations",
            max_budget=10.0,
            has_hard_budget=True,
        )
        gateway.add_key(key)

        # First request succeeds
        res1 = gateway.route_request("sk-finance-dept", estimated_cost=4.50)
        assert res1["status"] == "routed"
        assert res1["current_spend"] == 4.50

        # Second request succeeds
        res2 = gateway.route_request("sk-finance-dept", estimated_cost=5.00)
        assert res2["status"] == "routed"
        assert res2["current_spend"] == 9.50

        # Third request exceeds budget (9.50 + 1.00 = 10.50 > 10.00) -> Cutoff!
        with pytest.raises(BudgetExceededError, match="Hard budget exceeded"):
            gateway.route_request("sk-finance-dept", estimated_cost=1.00)

    def test_negative_unbounded_virtual_key_rejected(self) -> None:
        """
        [RA-3.1 NEGATIVE] Demuestra que una clave virtual sin presupuesto duro
        es rechazada por violar la política enterprise de techos de gasto.
        """
        gateway = LiteLLMProxyGateway(database_url="postgresql://user:pass@db.internal:5432/litellm")
        unbounded_key = VirtualKeyConfig(
            key_id="sk-unbounded",
            name="Uncontrolled Spend",
            max_budget=None,
            has_hard_budget=False,
        )
        gateway.add_key(unbounded_key)

        with pytest.raises(UnboundedKeyError, match="lacks a hard budget cap"):
            gateway.route_request("sk-unbounded", estimated_cost=1.0)

    def test_negative_missing_db_backend_fails(self) -> None:
        """
        [RA-3.1 NEGATIVE] Confirma que inicializar el proxy sin base de datos
        persistente falla por impedir la auditoría y persistencia de gasto.
        """
        with pytest.raises(ValueError, match="requires a persistent relational database backend"):
            LiteLLMProxyGateway(database_url="")


class TestRA32OidcIdentityPropagation:
    """
    RA-3.2: Propagación de identidad del usuario final extraída de token OIDC.
    """

    def test_positive_propagates_end_user_claims_alongside_service_key(self) -> None:
        """
        [RA-3.2 POSITIVE] Confirma que los claims OIDC del usuario final se inyectan
        en cabeceras de atribución downstream junto a la credencial del servicio.
        """
        propagator = OidcIdentityPropagator()
        token_claims = {
            "sub": "usr_99812_analyst",
            "email": "carlos.ruiz@santander.example",
            "tenant_id": "seguros-iberia",
            "iss": "https://auth.santander.example",
        }
        app_service_key = "vkey_gateway_app_prod"

        headers = propagator.build_downstream_headers(
            jwt_payload=token_claims,
            service_api_key=app_service_key,
            propagate_end_user=True,
        )

        assert headers["Authorization"] == "Bearer vkey_gateway_app_prod"
        assert headers["X-End-User-Id"] == "usr_99812_analyst"
        assert headers["X-End-User-Email"] == "carlos.ruiz@santander.example"
        assert headers["X-Audit-Tenant-Id"] == "seguros-iberia"
        assert propagator.validate_attribution_headers(headers) is True

    def test_negative_propagating_only_service_key_fails_validation(self) -> None:
        """
        [RA-3.2 NEGATIVE] Demuestra que omitir la atribución del usuario final y propagar
        solamente la clave de servicio falla la validación de auditoría forense.
        """
        propagator = OidcIdentityPropagator()
        token_claims = {"sub": "usr_99812_analyst"}

        # Propagating only service key
        service_only_headers = propagator.build_downstream_headers(
            jwt_payload=token_claims,
            service_api_key="vkey_gateway_app_prod",
            propagate_end_user=False,
        )

        with pytest.raises(ValueError, match="Downstream request propagates only application credentials"):
            propagator.validate_attribution_headers(service_only_headers)


class TestRA33NetworkPolicyAsCode:
    """
    RA-3.3: Verificación de política de red que rechaza IPs públicas y egress 0.0.0.0/0.
    """

    def test_positive_strictly_private_network_plan_accepted(self) -> None:
        """
        [RA-3.3 POSITIVE] Confirma que un plan con enlaces privados VPC Endpoint
        y sin direcciones IP públicas supera el validador de seguridad.
        """
        validator = NetworkPolicyValidator()
        private_plan = {
            "resources": [
                {
                    "name": "vpc_endpoint_litellm",
                    "properties": {
                        "public_ip": False,
                        "uses_privatelink": True,
                        "target_service": "llm_api",
                        "egress_rules": [
                            {"cidr_block": "10.0.0.0/16", "port": 443}
                        ],
                    },
                }
            ]
        }
        assert validator.validate_infrastructure_plan(private_plan) is True

    def test_negative_rejects_public_ip_and_unrestricted_egress(self) -> None:
        """
        [RA-3.3 NEGATIVE] Demuestra que un plan con IP pública asignada y egress
        abierto hacia 0.0.0.0/0 es rechazado deterministamente por Policy-as-Code.
        """
        validator = NetworkPolicyValidator()
        insecure_plan = {
            "resources": [
                {
                    "name": "gateway_instance",
                    "properties": {
                        "associate_public_ip_address": True,
                        "egress_rules": [
                            {"cidr_block": "0.0.0.0/0", "port": 443}
                        ],
                        "target_service": "llm_api",
                        "uses_vpc_endpoint": False,
                    },
                }
            ]
        }

        with pytest.raises(NetworkPolicyViolationError, match="security violations"):
            validator.validate_infrastructure_plan(insecure_plan)


class TestRA34SupplyChainAuditing:
    """
    RA-3.4: Auditoría de cadena de suministro (digest SHA-256, SBOM y rotación).
    """

    def test_positive_digest_pinned_image_and_sbom_accepted(self) -> None:
        """
        [RA-3.4 POSITIVE] Confirma aceptación de documentación con imagen fijada
        por digest SHA-256 inmutable, SBOM SPDX y protocolo de rotación.
        """
        auditor = SupplyChainAuditor()
        valid_doc = {
            "image_reference": "ghcr.io/berriai/litellm@sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "sbom_format": "SPDX",
            "key_rotation_procedure": "Procedimiento de rotacion automatica cada 90 dias con KMS envelope.",
            "compliance_narrative": "Los logs operacionales son evidencia auditable para los criterios CC6 y CC7.",
        }

        result = auditor.audit_document(valid_doc)
        assert result["status"] == "compliant"
        assert result["image_pinned"] is True

    def test_negative_calling_log_file_soc2_compliant_fails(self) -> None:
        """
        [RA-3.4 NEGATIVE] Demuestra que llamar 'compatible con SOC 2' a un archivo
        de log es rechazado como falacia conceptual.
        """
        auditor = SupplyChainAuditor()
        fallacious_doc = {
            "image_reference": "ghcr.io/berriai/litellm@sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "sbom_format": "SPDX",
            "key_rotation_procedure": "Procedimiento de rotacion cada 90 dias.",
            "compliance_narrative": "Este archivo de log es compatible con SOC 2 y garantiza certificacion inmediata.",
        }

        with pytest.raises(ValueError, match="Calling an operational log file 'compatible con SOC 2' is a conceptual fallacy"):
            auditor.audit_document(fallacious_doc)
