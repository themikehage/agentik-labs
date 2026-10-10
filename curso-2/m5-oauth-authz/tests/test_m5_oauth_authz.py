"""
Reference tests for Curso 2 M5 - Autorización OAuth 2.1 y Token Exchange MCP.
Strictly adheres to:
- One test function per acceptance criterion citing the RA in docstring.
- Positive and negative cases detecting conceptual misconceptions.
- Zero network socket usage (pytest-socket enforced).
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c2_m5_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

OAuthAuthorizationServer = _mod.OAuthAuthorizationServer
TokenValidator = _mod.TokenValidator
DownstreamTokenExchanger = _mod.DownstreamTokenExchanger
generate_s256_challenge = _mod.generate_s256_challenge
OAuthError = _mod.OAuthError
InsufficientScopeError = _mod.InsufficientScopeError
from labkit.clock import VirtualClock


class TestRA51OAuthPKCES256:
    """
    RA-5.1: El estudiante debe exigir OAuth 2.1 con PKCE obligatorio (code_challenge_method S256).
    """

    def test_positive_pkce_authorization_and_token_exchange(self) -> None:
        """
        [RA-5.1 POSITIVE] Confirma que un cliente con verifier válido y S256
        obtiene el código y lo intercambia exitosamente por un Access Token.
        """
        clock = VirtualClock(initial_time=1000.0)
        auth_server = OAuthAuthorizationServer(clock=clock)

        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        challenge = generate_s256_challenge(verifier)

        code = auth_server.authorize(
            client_id="mcp-client-1",
            code_challenge=challenge,
            code_challenge_method="S256",
            scope="tools:read tools:write",
        )
        assert code.startswith("code-")

        token_response = auth_server.token_exchange_pkce("mcp-client-1", code, verifier)
        assert "access_token" in token_response
        token = token_response["access_token"]
        assert token["iss"] == "https://auth.agentik.im"
        assert token["aud"] == "urn:agentik:mcp-gateway"
        assert "tools:write" in token["scope"]

    def test_negative_rejects_plain_code_challenge_method(self) -> None:
        """
        [RA-5.1 NEGATIVE] Exige que OAuth 2.1 rechace code_challenge_method=plain
        para impedir ataques de intercepción de autorización en texto plano.
        """
        auth_server = OAuthAuthorizationServer()
        with pytest.raises(OAuthError) as exc_info:
            auth_server.authorize(
                client_id="insecure-client",
                code_challenge="plain_string",
                code_challenge_method="plain",
            )
        assert "code_challenge_method=S256" in exc_info.value.description

    def test_negative_rejects_mismatched_pkce_verifier(self) -> None:
        """
        [RA-5.1 NEGATIVE] Detecta cuando un atacante intenta canjear un código
        con un code_verifier incorrecto o falsificado.
        """
        auth_server = OAuthAuthorizationServer()
        verifier = "valid_verifier_string_12345"
        challenge = generate_s256_challenge(verifier)

        code = auth_server.authorize("mcp-client-1", challenge, "S256")

        with pytest.raises(OAuthError) as exc_info:
            auth_server.token_exchange_pkce("mcp-client-1", code, "wrong_verifier_payload")
        assert "does not match code_challenge" in exc_info.value.description


class TestRA52TokenValidationAndAudience:
    """
    RA-5.2: El estudiante debe validar iss, aud y expiración del token contra VirtualClock.
    """

    def test_positive_valid_token_within_lifetime(self) -> None:
        """
        [RA-5.2 POSITIVE] Confirma que un token con emisor, audiencia y expiración válidos
        es aceptado sin error.
        """
        clock = VirtualClock(initial_time=2000.0)
        validator = TokenValidator(clock=clock)

        token = {
            "iss": "https://auth.agentik.im",
            "aud": "urn:agentik:mcp-gateway",
            "sub": "usr-123",
            "scope": ["tools:read"],
            "exp": 2500.0,
        }
        res = validator.validate_token(token)
        assert res["sub"] == "usr-123"

    def test_negative_expired_token_rejected_deterministically(self) -> None:
        """
        [RA-5.2 NEGATIVE] Avanza el VirtualClock más allá de exp y exige rechazo con 401.
        """
        clock = VirtualClock(initial_time=2000.0)
        validator = TokenValidator(clock=clock)

        token = {
            "iss": "https://auth.agentik.im",
            "aud": "urn:agentik:mcp-gateway",
            "exp": 2500.0,
        }
        # Advance clock past expiration
        clock.sleep(600.0)  # time is now 2600.0 > 2500.0

        with pytest.raises(OAuthError) as exc_info:
            validator.validate_token(token)
        assert exc_info.value.error == "invalid_token"
        assert "expired" in exc_info.value.description


class TestRA53InsufficientScopeChallenge:
    """
    RA-5.3: El estudiante debe emitir error insufficient_scope (403) ante permisos faltantes.
    """

    def test_positive_insufficient_scope_challenge_details(self) -> None:
        """
        [RA-5.3 POSITIVE] Confirma que si la operación requiere tools:write pero el token
        posee únicamente tools:read, se levanta InsufficientScopeError (403).
        """
        clock = VirtualClock(initial_time=100.0)
        validator = TokenValidator(clock=clock)

        token = {
            "iss": "https://auth.agentik.im",
            "aud": "urn:agentik:mcp-gateway",
            "scope": ["tools:read"],
            "exp": 500.0,
        }

        with pytest.raises(InsufficientScopeError) as exc_info:
            validator.validate_token(token, required_scope="tools:write")
        assert exc_info.value.status_code == 403
        assert exc_info.value.required_scope == "tools:write"
        assert exc_info.value.error == "insufficient_scope"


class TestRA54TokenExchangeVsPassthrough:
    """
    RA-5.4: El estudiante debe implementar RFC 8693 token exchange y prohibir token passthrough.
    """

    def test_positive_rfc_8693_downstream_delegation(self) -> None:
        """
        [RA-5.4 POSITIVE] Confirma que para invocar un servicio downstream (ej. base de datos),
        se emite un token con aud específica ('urn:service:database') y actor de delegación.
        """
        clock = VirtualClock(initial_time=100.0)
        exchanger = DownstreamTokenExchanger(clock=clock)

        user_token = {
            "iss": "https://auth.agentik.im",
            "aud": "urn:agentik:mcp-gateway",
            "sub": "usr-analytics",
            "scope": ["tools:read"],
            "exp": 1000.0,
        }

        downstream_token = exchanger.exchange_token(user_token, target_audience="urn:service:database")
        assert downstream_token["aud"] == "urn:service:database"
        assert downstream_token["sub"] == "usr-analytics"
        assert downstream_token["act"]["sub"] == "urn:agentik:mcp-gateway"
        assert downstream_token["aud"] != user_token["aud"]

    def test_negative_passthrough_to_same_audience_rejected(self) -> None:
        """
        [RA-5.4 NEGATIVE] Detecta el error de reenviar el token con la misma audiencia
        del gateway hacia el exterior.
        """
        exchanger = DownstreamTokenExchanger()
        user_token = {
            "iss": "https://auth.agentik.im",
            "aud": "urn:agentik:mcp-gateway",
            "sub": "usr-1",
        }
        with pytest.raises(OAuthError) as exc_info:
            exchanger.exchange_token(user_token, target_audience="urn:agentik:mcp-gateway")
        assert "Target audience must differ" in exc_info.value.description
