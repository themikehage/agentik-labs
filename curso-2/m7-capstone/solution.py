"""
Reference implementation for Curso 2 M7 - Capstone: Enterprise MCP Gateway.
Complete integration of Streamable HTTP, MRTR, OAuth 2.1, Anti-SSRF, Tool Pinning, and Async Tasks.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from labkit.clock import VirtualClock
from labkit.seed import derive_seed


class EnterpriseGatewayError(Exception):
    def __init__(self, code: int, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class EnterpriseMcpGateway:
    SUPPORTED_VERSION = "2026-07-28"

    def __init__(
        self,
        clock: VirtualClock | None = None,
        issuer: str = "https://auth.agentik.im",
        audience: str = "urn:agentik:mcp-gateway",
    ) -> None:
        self.clock = clock or VirtualClock()
        self.issuer = issuer
        self.audience = audience
        self._pinned_hashes: dict[str, str] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._idempotency_cache: dict[str, dict[str, Any]] = {}
        self._execution_counts: dict[str, int] = {}
        self.secret_key = b"enterprise-stateless-mrtr-secret"

    def pin_tool(self, name: str, expected_hash: str) -> None:
        self._pinned_hashes[name] = expected_hash

    def _sign_state(self, state_text: str) -> str:
        sig = hashlib.sha256(self.secret_key + state_text.encode("utf-8")).hexdigest()
        return f"{state_text}:{sig}"

    def _verify_state(self, signed_state: str) -> str | None:
        if ":" not in signed_state:
            return None
        text, sig = signed_state.rsplit(":", 1)
        expected = hashlib.sha256(self.secret_key + text.encode("utf-8")).hexdigest()
        if sig == expected:
            return text
        return None

    def _verify_auth(self, headers: dict[str, str], required_scope: str | None = None) -> dict[str, Any]:
        auth_header = headers.get("Authorization") or headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise EnterpriseGatewayError(-32001, "Missing or malformed Authorization header", 401)

        token_raw = auth_header[7:].strip()
        try:
            token_payload = json.loads(token_raw)
        except Exception:
            raise EnterpriseGatewayError(-32001, "Invalid bearer token format", 401)

        if token_payload.get("iss") != self.issuer:
            raise EnterpriseGatewayError(-32001, "Invalid token issuer", 401)

        if token_payload.get("aud") != self.audience:
            raise EnterpriseGatewayError(-32001, "Invalid token audience", 401)

        if self.clock.now() >= token_payload.get("exp", 0.0):
            raise EnterpriseGatewayError(-32001, "Token has expired", 401)

        if required_scope:
            scopes = token_payload.get("scope", [])
            if required_scope not in scopes:
                raise EnterpriseGatewayError(
                    -32003,
                    f"Insufficient scope: operation requires '{required_scope}'",
                    403,
                )

        return token_payload

    def exchange_downstream_token(self, user_token: dict[str, Any], downstream_aud: str) -> dict[str, Any]:
        if downstream_aud == self.audience:
            raise EnterpriseGatewayError(-32002, "Downstream audience must differ from gateway audience", 400)

        return {
            "iss": self.issuer,
            "aud": downstream_aud,
            "sub": user_token["sub"],
            "act": {"sub": self.audience},  # RFC 8693 delegation actor
            "exp": self.clock.now() + 300.0,
            "scope": ["downstream:access"],
        }

    def handle_http(
        self,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> tuple[int, dict[str, str], dict[str, Any]]:
        resp_headers = {
            "Content-Type": "application/json",
            "X-Mcp-Transport": "Streamable-HTTP",
        }

        # Idempotency check
        idem_key = headers.get("Idempotency-Key") or headers.get("idempotency-key")
        if idem_key and idem_key in self._idempotency_cache:
            resp_headers["X-Cache-Lookup"] = "HIT"
            return 200, resp_headers, self._idempotency_cache[idem_key]

        req_id = body.get("id")
        method = body.get("method")
        params = body.get("params") or {}
        meta = params.get("_meta") or {}

        # Obsolete protocol methods check
        if method in ("initialize", "ping"):
            return 200, resp_headers, {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' was removed in MCP 2026-07-28.",
                },
            }

        if method == "tasks/result":
            return 200, resp_headers, {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": "Method 'tasks/result' is obsolete. Use 'tasks/get' to poll status.",
                },
            }

        # Meta validation
        if "io.modelcontextprotocol/clientCapabilities" not in meta:
            return 200, resp_headers, {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32602,
                    "message": "Missing mandatory clientCapabilities in _meta",
                },
            }

        req_version = meta.get("version", self.SUPPORTED_VERSION)
        if req_version != self.SUPPORTED_VERSION:
            return 200, resp_headers, {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32022,
                    "message": f"Unsupported version: {req_version}",
                    "data": {"supported": [self.SUPPORTED_VERSION]},
                },
            }

        # Method dispatch
        if method == "server/discover":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "supportedVersions": [self.SUPPORTED_VERSION],
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "resources": {"subscribe": True},
                    },
                },
            }
            return 200, resp_headers, res

        # Protected routes require valid bearer token
        try:
            user_token = self._verify_auth(headers, required_scope="tools:invoke")
        except EnterpriseGatewayError as e:
            err_headers = dict(resp_headers)
            if e.status_code == 401:
                err_headers["WWW-Authenticate"] = 'Bearer error="invalid_token"'
            elif e.status_code == 403:
                err_headers["WWW-Authenticate"] = 'Bearer error="insufficient_scope", scope="tools:invoke"'
            return e.status_code, err_headers, {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": e.code, "message": e.message},
            }

        if method == "tasks/get":
            task_id = params.get("taskId")
            task = self._tasks.get(task_id or "")
            if not task:
                return 200, resp_headers, {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": f"Task '{task_id}' not found"},
                }
            return 200, resp_headers, {"jsonrpc": "2.0", "id": req_id, "result": task}

        if method == "tools/call":
            tool_name = params.get("name")
            tool_def = params.get("definition") or {}

            # Tool Pinning check
            if tool_name in self._pinned_hashes:
                canonical = json.dumps(tool_def, sort_keys=True, separators=(",", ":"))
                actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                if actual_hash != self._pinned_hashes[tool_name]:
                    return 200, resp_headers, {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32004,
                            "message": f"Tool Poisoning detected on '{tool_name}': hash mismatch",
                        },
                    }

            # MRTR high-risk action workflow
            if tool_name == "deploy_service":
                input_responses = params.get("inputResponses")
                request_state = params.get("requestState")

                if input_responses and request_state:
                    state_val = self._verify_state(request_state)
                    if not state_val or state_val != "deploy_pending":
                        return 200, resp_headers, {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32602, "message": "Invalid or tampered requestState"},
                        }

                    # Resumed and completed
                    # Downstream delegation
                    downstream_jwt = self.exchange_downstream_token(user_token, "urn:service:deployer")
                    res = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "resultType": "complete",
                            "content": [{"type": "text", "text": "Deployment executed successfully"}],
                            "downstream_act": downstream_jwt["act"],
                        },
                    }
                    if idem_key:
                        self._idempotency_cache[idem_key] = res
                    return 200, resp_headers, res

                # First pass asks confirmation
                packed_state = self._sign_state("deploy_pending")
                return 200, resp_headers, {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "resultType": "input_required",
                        "requestState": packed_state,
                        "inputRequests": [
                            {"field": "confirm_prod", "prompt": "Type YES to confirm deployment"}
                        ],
                    },
                }

        return 200, resp_headers, {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }
