# STUB: implement the capstone here. See README.md. Run: uv run pytest curso-2/m7-capstone/tests
"""C2-M7 capstone: Enterprise MCP Gateway (student stub)."""

from __future__ import annotations

from typing import Any

from labkit.clock import VirtualClock


class EnterpriseGatewayError(Exception):
    """Gateway error carrying a JSON-RPC style code and an HTTP status."""

    def __init__(self, code: int, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class EnterpriseMcpGateway:
    """Stateless Streamable HTTP MCP gateway (protocol version 2026-07-28)."""

    SUPPORTED_VERSION = "2026-07-28"

    def __init__(
        self,
        clock: VirtualClock | None = None,
        issuer: str = "https://auth.agentik.im",
        audience: str = "urn:agentik:mcp-gateway",
    ) -> None:
        self.clock = clock if clock is not None else VirtualClock()
        self.issuer = issuer
        self.audience = audience
        self._pinned_hashes: dict[str, str] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._idempotency_cache: dict[str, dict[str, Any]] = {}

    def pin_tool(self, name: str, expected_hash: str) -> None:
        """Register the expected definition hash for a tool (tool pinning)."""
        raise NotImplementedError("Implement tool pinning registration")

    def _verify_auth(self, headers: dict[str, str], required_scope: str | None = None) -> dict[str, Any]:
        """Validate the Bearer token (issuer, audience, expiry on the injected clock,
        scope) and return its claims.

        Raise EnterpriseGatewayError: code -32001 / HTTP 401 for missing or invalid
        tokens, code -32003 / HTTP 403 for insufficient scope.
        """
        raise NotImplementedError("Implement OAuth 2.1 bearer validation")

    def exchange_downstream_token(self, user_token: dict[str, Any], downstream_aud: str) -> dict[str, Any]:
        """RFC 8693 token exchange: return a short-lived downstream token for the
        same subject with an 'act' delegation claim naming the gateway.

        A downstream audience equal to the gateway audience is rejected (code -32002).
        """
        raise NotImplementedError("Implement downstream token exchange")

    def handle_http(
        self,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> tuple[int, dict[str, str], dict[str, Any]]:
        """Handle one JSON-RPC request; return (status, response_headers, body).

        Required behavior (see README.md and the public tests):
        - Responses carry header "X-Mcp-Transport: Streamable-HTTP".
        - 'initialize', 'ping' and 'tasks/result' are removed methods (-32601).
        - Requests need _meta with clientCapabilities; unsupported versions are rejected.
        - 'server/discover' is public and lists the supported version.
        - 'tools/call' requires a Bearer token with scope 'tools:invoke'; failures
          return 401/403 with a WWW-Authenticate challenge.
        - Pinned tools whose definition hash does not match are rejected.
        - 'deploy_service' uses the multi-round-trip flow (resultType
          "input_required" with a tamper-evident requestState, then "complete" with
          downstream delegation proof).
        - 'tasks/get' polls async task status.
        - Idempotency-Key replays return the cached response.
        """
        raise NotImplementedError("Implement the Streamable HTTP request handler")
