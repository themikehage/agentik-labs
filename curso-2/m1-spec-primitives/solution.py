"""
Reference implementation for Curso 2 M1 - Especificación y Primitivas MCP (2026-07-28).
Stateless MCP Server with MRTR support, version discovery, and client capability validation.
"""

from __future__ import annotations

import hmac
import hashlib
from typing import Any

SUPPORTED_VERSION = "2026-07-28"
STATE_SECRET = b"agentik-m1-stateless-secret-key"


def _sign_state(state_data: str) -> str:
    sig = hmac.new(STATE_SECRET, state_data.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{state_data}:{sig}"


def _verify_and_unpack_state(packed_state: str) -> str | None:
    if ":" not in packed_state:
        return None
    state_data, sig = packed_state.rsplit(":", 1)
    expected_sig = hmac.new(STATE_SECRET, state_data.encode("utf-8"), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected_sig):
        return state_data
    return None


class MCPServer:
    """
    Stateless reference server for MCP 2026-07-28.
    Never caches connection capabilities or conversation state in instance attributes.
    """

    def __init__(self, supported_versions: list[str] | None = None) -> None:
        self.supported_versions = supported_versions or [SUPPORTED_VERSION]

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        meta = params.get("_meta") or {}

        if method in ("initialize", "ping"):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' is obsolete and removed in MCP 2026-07-28",
                },
            }

        client_caps = meta.get("io.modelcontextprotocol/clientCapabilities")
        if client_caps is None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32602,
                    "message": "Missing mandatory clientCapabilities in _meta",
                },
            }

        req_version = meta.get("version", SUPPORTED_VERSION)
        if req_version not in self.supported_versions:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32022,
                    "message": f"Unsupported protocol version: {req_version}",
                    "data": {"supported": self.supported_versions},
                },
            }

        if method == "server/discover":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "supportedVersions": self.supported_versions,
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "resources": {"subscribe": True},
                        "prompts": {},
                    },
                },
            }

        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments") or {}

            if tool_name == "transfer_funds":
                input_responses = params.get("inputResponses")
                request_state = params.get("requestState")

                if input_responses and request_state:
                    unpacked = _verify_and_unpack_state(request_state)
                    if not unpacked or unpacked != "pending_confirmation":
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {
                                "code": -32602,
                                "message": "Invalid or tampered requestState in MRTR resumption",
                            },
                        }
                    auth_code = input_responses.get("auth_code")
                    if auth_code == "123456":
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {
                                "resultType": "complete",
                                "content": [
                                    {"type": "text", "text": "Transfer of funds completed successfully."}
                                ],
                            },
                        }
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "resultType": "complete",
                            "isError": True,
                            "content": [
                                {"type": "text", "text": "Transfer failed: invalid confirmation code."}
                            ],
                        },
                    }

                packed = _sign_state("pending_confirmation")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "resultType": "input_required",
                        "requestState": packed,
                        "inputRequests": [
                            {
                                "field": "auth_code",
                                "prompt": "Please enter the 6-digit confirmation code sent to your device",
                                "type": "string",
                            }
                        ],
                    },
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }


def classify_legacy_features() -> dict[str, dict[str, str]]:
    """
    Classifies obsolete and deprecated MCP features per SEP-2577 / 2026-07-28 specification.
    """
    return {
        "roots": {
            "status": "deprecated",
            "migration": "Direct resource URIs and client workspace handles",
        },
        "sampling": {
            "status": "deprecated",
            "migration": "Model-Requested Tool Resumption (MRTR) with polymorphic resultType",
        },
        "logging": {
            "status": "deprecated",
            "migration": "OpenTelemetry GenAI standard telemetry spans and events",
        },
    }
