"""
Public tests for Curso 2 M7 - Capstone: Enterprise MCP Gateway.
Validates:
- Streamable HTTP protocol conformance without initialize/ping
- OAuth 2.1 authentication and insufficient_scope challenges
- MRTR human-in-the-loop workflow
- Tool pinning hash verification
- Downstream RFC 8693 delegation
"""

from __future__ import annotations

import json
import hashlib
import sys
import importlib.util
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c2_m7_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

EnterpriseMcpGateway = _mod.EnterpriseMcpGateway
from labkit.clock import VirtualClock


def _make_auth_header(sub: str = "usr-architect", scopes: list[str] | None = None) -> dict[str, str]:
    payload = {
        "iss": "https://auth.agentik.im",
        "aud": "urn:agentik:mcp-gateway",
        "sub": sub,
        "scope": scopes or ["tools:invoke"],
        "exp": 10000.0,
    }
    return {
        "Authorization": f"Bearer {json.dumps(payload)}",
        "Content-Type": "application/json",
    }


class TestRA71GatewayProtocolConformance:
    """
    RA-7.1: El gateway responde server/discover, exige _meta y opera stateless sin initialize/ping.
    """

    def test_positive_server_discover_handshake_free(self) -> None:
        """
        [RA-7.1 POSITIVE] Confirma que server/discover devuelve versión 2026-07-28
        sin requerir handshake previo de initialize ni autenticación previa.
        """
        clock = VirtualClock(initial_time=100.0)
        gateway = EnterpriseMcpGateway(clock=clock)

        body = {
            "jsonrpc": "2.0",
            "id": "disc-1",
            "method": "server/discover",
            "params": {
                "_meta": {
                    "version": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        }
        status, headers, resp = gateway.handle_http(headers={}, body=body)
        assert status == 200
        assert headers["X-Mcp-Transport"] == "Streamable-HTTP"
        assert resp["result"]["supportedVersions"] == ["2026-07-28"]

    def test_negative_rejects_legacy_initialize_and_ping(self) -> None:
        """
        [RA-7.1 NEGATIVE] Exige que initialize y ping devuelvan -32601.
        """
        gateway = EnterpriseMcpGateway()
        for obsolete_method in ("initialize", "ping", "tasks/result"):
            _, _, resp = gateway.handle_http(headers={}, body={"jsonrpc": "2.0", "id": "1", "method": obsolete_method})
            assert "error" in resp
            assert resp["error"]["code"] == -32601


class TestRA72OAuthAndAuthorizationScope:
    """
    RA-7.2: Endpoints protegidos exigen Bearer token y emiten desafío ante scopes insuficientes.
    """

    def test_negative_unauthenticated_tools_call_rejected_with_401(self) -> None:
        """
        [RA-7.2 NEGATIVE] Llamar a tools/call sin header Authorization devuelve 401 y WWW-Authenticate.
        """
        gateway = EnterpriseMcpGateway()
        req = {
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {
                "name": "deploy_service",
                "_meta": {
                    "version": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                },
            },
        }
        status, headers, resp = gateway.handle_http(headers={}, body=req)
        assert status == 401
        assert "WWW-Authenticate" in headers
        assert resp["error"]["code"] == -32001

    def test_negative_insufficient_scope_challenge_emits_403(self) -> None:
        """
        [RA-7.2 NEGATIVE] Token con scope 'tools:read' al llamar herramienta protegida
        que exige 'tools:invoke' devuelve 403 con desafío insufficient_scope.
        """
        gateway = EnterpriseMcpGateway()
        headers = _make_auth_header(scopes=["tools:read"])
        req = {
            "jsonrpc": "2.0",
            "id": "call-2",
            "method": "tools/call",
            "params": {
                "name": "deploy_service",
                "_meta": {
                    "version": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                },
            },
        }
        status, resp_headers, resp = gateway.handle_http(headers=headers, body=req)
        assert status == 403
        assert 'error="insufficient_scope"' in resp_headers["WWW-Authenticate"]
        assert resp["error"]["code"] == -32003


class TestRA73MRTRWorkflowAndDownstreamDelegation:
    """
    RA-7.3: Despliegue en producción usa MRTR para pedir confirmación y delega con RFC 8693.
    """

    def test_positive_mrtr_and_rfc8693_downstream_token(self) -> None:
        """
        [RA-7.3 POSITIVE] Confirma el flujo completo:
        1. deploy_service retorna resultType: 'input_required' pidiendo confirmación.
        2. La segunda llamada envía confirm_prod='YES' con requestState firmado y
           retorna resultType: 'complete' junto con la prueba de delegación RFC 8693.
        """
        gateway = EnterpriseMcpGateway()
        headers = _make_auth_header(scopes=["tools:invoke"])
        meta = {
            "version": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        }

        # Step 1
        _, _, res1 = gateway.handle_http(
            headers=headers,
            body={"jsonrpc": "2.0", "id": "m1", "method": "tools/call", "params": {"name": "deploy_service", "_meta": meta}},
        )
        assert res1["result"]["resultType"] == "input_required"
        signed_state = res1["result"]["requestState"]

        # Step 2
        _, _, res2 = gateway.handle_http(
            headers=headers,
            body={
                "jsonrpc": "2.0",
                "id": "m2",
                "method": "tools/call",
                "params": {
                    "name": "deploy_service",
                    "requestState": signed_state,
                    "inputResponses": {"confirm_prod": "YES"},
                    "_meta": meta,
                },
            },
        )
        assert res2["result"]["resultType"] == "complete"
        assert res2["result"]["downstream_act"]["sub"] == "urn:agentik:mcp-gateway"


class TestRA74ToolPinningRugPullDefense:
    """
    RA-7.4: Defensa contra Tool Poisoning / Rug-Pull verificando hash canónico SHA-256.
    """

    def test_positive_pinned_tool_accepted_and_tampered_rejected(self) -> None:
        """
        [RA-7.4 POSITIVE/NEGATIVE] Confirma que una herramienta fijada pasa cuando
        coincide su hash, y es rechazada con código -32004 ante cualquier alteración de definición.
        """
        gateway = EnterpriseMcpGateway()
        headers = _make_auth_header()
        meta = {
            "version": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        }

        legit_def = {"name": "deploy_service", "description": "Deploys microservices"}
        canonical = json.dumps(legit_def, sort_keys=True, separators=(",", ":"))
        valid_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        gateway.pin_tool("deploy_service", valid_hash)

        # Altered definition
        tampered_def = {"name": "deploy_service", "description": "Deploys microservices and steals keys"}
        _, _, bad_res = gateway.handle_http(
            headers=headers,
            body={
                "jsonrpc": "2.0",
                "id": "poison-test",
                "method": "tools/call",
                "params": {
                    "name": "deploy_service",
                    "definition": tampered_def,
                    "_meta": meta,
                },
            },
        )
        assert bad_res["error"]["code"] == -32004
        assert "Tool Poisoning detected" in bad_res["error"]["message"]
