"""
Reference implementation for Curso 2 M4 - Clientes y Conformidad MCP.
Client negotiation, metadata injection, polymorphic resultType dispatching, and conformance checks.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable


class IncompatibleServerVersionError(Exception):
    def __init__(self, requested_version: str, supported: list[str]) -> None:
        super().__init__(
            f"Server does not support requested version '{requested_version}'. Supported versions: {supported}"
        )
        self.requested_version = requested_version
        self.supported = supported


class MCPClient:
    def __init__(
        self,
        transport: Callable[[dict[str, Any]], dict[str, Any]],
        client_version: str = "2026-07-28",
        capabilities: dict[str, Any] | None = None,
    ) -> None:
        self.transport = transport
        self.client_version = client_version
        self.capabilities = capabilities or {
            "experimental": {},
            "roots": {"listChanged": False},
        }

    def _build_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        req_id = f"client-{uuid.uuid4().hex[:8]}"
        req_params = dict(params or {})
        req_params["_meta"] = {
            "version": self.client_version,
            "io.modelcontextprotocol/clientCapabilities": self.capabilities,
        }
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": req_params,
        }

    def discover_server(self) -> dict[str, Any]:
        req = self._build_request("server/discover")
        resp = self.transport(req)

        if "error" in resp:
            err = resp["error"]
            if err.get("code") == -32022:
                data = err.get("data") or {}
                supported = data.get("supported", [])
                raise IncompatibleServerVersionError(self.client_version, supported)
            raise RuntimeError(f"Server error during discover: {err.get('message')}")

        return resp.get("result", {})

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        request_state: str | None = None,
        input_responses: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"name": name, "arguments": arguments or {}}
        if request_state:
            params["requestState"] = request_state
        if input_responses:
            params["inputResponses"] = input_responses

        req = self._build_request("tools/call", params)
        resp = self.transport(req)

        if "error" in resp:
            return {"status": "error", "error": resp["error"]}

        result = resp.get("result", {})
        # Polimorphic dispatch: absence defaults to "complete" for backwards compatibility
        result_type = result.get("resultType", "complete")

        if result_type == "complete":
            return {
                "status": "complete",
                "isError": result.get("isError", False),
                "structuredContent": result.get("structuredContent"),
                "content": result.get("content", []),
            }
        elif result_type == "input_required":
            return {
                "status": "input_required",
                "requestState": result.get("requestState"),
                "inputRequests": result.get("inputRequests", []),
            }

        return {"status": "unknown_result_type", "raw": result}


class ConformanceRunner:
    @staticmethod
    def verify_server(transport: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, bool]:
        report: dict[str, bool] = {}

        # Check 1: server/discover returns supportedVersions
        client = MCPClient(transport=transport)
        try:
            disc = client.discover_server()
            report["supports_discover"] = "supportedVersions" in disc
        except Exception:
            report["supports_discover"] = False

        # Check 2: Missing clientCapabilities returns -32602
        raw_no_caps = {
            "jsonrpc": "2.0",
            "id": "conf-test",
            "method": "server/discover",
            "params": {"_meta": {"version": "2026-07-28"}},
        }
        res_caps = transport(raw_no_caps)
        report["rejects_missing_capabilities"] = res_caps.get("error", {}).get("code") == -32602

        # Check 3: Initialize returns -32601
        raw_init = {
            "jsonrpc": "2.0",
            "id": "conf-init",
            "method": "initialize",
            "params": {},
        }
        res_init = transport(raw_init)
        report["rejects_initialize"] = res_init.get("error", {}).get("code") == -32601

        return report
