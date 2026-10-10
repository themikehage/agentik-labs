"""
Reference implementation for Curso 2 M5 - Autorización OAuth 2.1 y Token Exchange MCP.
PKCE S256 verification, strict token validation, insufficient_scope challenges, and RFC 8693 token exchange.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from typing import Any
from labkit.clock import VirtualClock


def generate_s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


class OAuthError(Exception):
    def __init__(self, error: str, description: str, status_code: int = 400) -> None:
        super().__init__(description)
        self.error = error
        self.description = description
        self.status_code = status_code


class InsufficientScopeError(OAuthError):
    def __init__(self, required_scope: str, granted_scopes: list[str]) -> None:
        super().__init__(
            error="insufficient_scope",
            description=f"Operation requires scope '{required_scope}', but token only has '{' '.join(granted_scopes)}'",
            status_code=403,
        )
        self.required_scope = required_scope
        self.granted_scopes = granted_scopes


class OAuthAuthorizationServer:
    def __init__(self, issuer: str = "https://auth.agentik.im", clock: VirtualClock | None = None) -> None:
        self.issuer = issuer
        self.clock = clock or VirtualClock()
        self._auth_codes: dict[str, dict[str, Any]] = {}

    def authorize(
        self,
        client_id: str,
        code_challenge: str,
        code_challenge_method: str = "S256",
        scope: str = "tools:read",
        user_id: str = "usr-dev",
    ) -> str:
        if code_challenge_method != "S256":
            raise OAuthError("invalid_request", "OAuth 2.1 requires code_challenge_method=S256")

        code = f"code-{uuid.uuid4().hex[:12]}"
        self._auth_codes[code] = {
            "client_id": client_id,
            "code_challenge": code_challenge,
            "scope": scope.split(),
            "user_id": user_id,
            "expires_at": self.clock.now() + 60.0,
        }
        return code

    def token_exchange_pkce(self, client_id: str, code: str, code_verifier: str) -> dict[str, Any]:
        record = self._auth_codes.get(code)
        if not record:
            raise OAuthError("invalid_grant", "Authorization code is invalid or already consumed")

        if self.clock.now() > record["expires_at"]:
            del self._auth_codes[code]
            raise OAuthError("invalid_grant", "Authorization code has expired")

        del self._auth_codes[code]

        # Verify S256 challenge
        computed_challenge = generate_s256_challenge(code_verifier)
        if computed_challenge != record["code_challenge"]:
            raise OAuthError("invalid_grant", "PKCE code_verifier does not match code_challenge")

        # Issue access token
        return {
            "access_token": {
                "iss": self.issuer,
                "aud": "urn:agentik:mcp-gateway",
                "sub": record["user_id"],
                "scope": record["scope"],
                "exp": self.clock.now() + 3600.0,
                "jti": f"jwt-{uuid.uuid4().hex[:8]}",
            },
            "token_type": "Bearer",
            "expires_in": 3600,
        }


class TokenValidator:
    def __init__(
        self,
        expected_issuer: str = "https://auth.agentik.im",
        expected_audience: str = "urn:agentik:mcp-gateway",
        clock: VirtualClock | None = None,
    ) -> None:
        self.expected_issuer = expected_issuer
        self.expected_audience = expected_audience
        self.clock = clock or VirtualClock()

    def validate_token(self, token: dict[str, Any], required_scope: str | None = None) -> dict[str, Any]:
        if token.get("iss") != self.expected_issuer:
            raise OAuthError("invalid_token", f"Invalid issuer. Expected {self.expected_issuer}", 401)

        if token.get("aud") != self.expected_audience:
            raise OAuthError("invalid_token", f"Invalid audience. Expected {self.expected_audience}", 401)

        exp = token.get("exp", 0.0)
        if self.clock.now() >= exp:
            raise OAuthError("invalid_token", "Token has expired", 401)

        scopes = token.get("scope", [])
        if required_scope and required_scope not in scopes:
            raise InsufficientScopeError(required_scope, scopes)

        return token


class DownstreamTokenExchanger:
    """
    Implements RFC 8693 Token Exchange for downstream invocations.
    Prohibits token passthrough by minting target-specific tokens with narrowed audience.
    """

    def __init__(self, issuer: str = "https://auth.agentik.im", clock: VirtualClock | None = None) -> None:
        self.issuer = issuer
        self.clock = clock or VirtualClock()

    def exchange_token(
        self,
        subject_token: dict[str, Any],
        target_audience: str,
        narrowed_scope: list[str] | None = None,
    ) -> dict[str, Any]:
        # Validate that we do not simply forward the original token
        if target_audience == subject_token.get("aud"):
            raise OAuthError("invalid_target", "Target audience must differ from gateway audience")

        return {
            "iss": self.issuer,
            "aud": target_audience,
            "sub": subject_token["sub"],
            "scope": narrowed_scope or ["service:access"],
            "exp": self.clock.now() + 300.0,
            "act": {"sub": "urn:agentik:mcp-gateway"},  # RFC 8693 delegation actor
            "jti": f"downstream-{uuid.uuid4().hex[:8]}",
        }
