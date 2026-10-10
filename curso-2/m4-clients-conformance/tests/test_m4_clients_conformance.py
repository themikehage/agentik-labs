"""
Reference tests for Curso 2 M4 - Clientes y Conformidad MCP.
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
_spec = importlib.util.spec_from_file_location("c2_m4_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

MCPClient = _mod.MCPClient
IncompatibleServerVersionError = _mod.IncompatibleServerVersionError
ConformanceRunner = _mod.ConformanceRunner


class TestRA41ClientMetaInjection:
    """
    RA-4.1: El estudiante debe asegurar que el cliente inyecta versión y clientCapabilities en cada llamada.
    """

    def test_positive_client_injects_canonical_meta(self) -> None:
        """
        [RA-4.1 POSITIVE] Confirma que toda petición generada por el cliente
        incluye _meta con la versión del cliente y clientCapabilities.
        """
        captured: dict = {}

        def mock_transport(req: dict) -> dict:
            nonlocal captured
            captured = req
            return {"jsonrpc": "2.0", "id": req["id"], "result": {"supportedVersions": ["2026-07-28"]}}

        client = MCPClient(transport=mock_transport, client_version="2026-07-28")
        client.discover_server()

        meta = captured.get("params", {}).get("_meta", {})
        assert meta.get("version") == "2026-07-28"
        assert "io.modelcontextprotocol/clientCapabilities" in meta

    def test_negative_fails_if_client_omits_meta(self) -> None:
        """
        [RA-4.1 NEGATIVE] Detecta si el cliente omite _meta en peticiones de herramientas.
        """
        captured: dict = {}

        def mock_transport(req: dict) -> dict:
            nonlocal captured
            captured = req
            return {"jsonrpc": "2.0", "id": req["id"], "result": {"resultType": "complete"}}

        client = MCPClient(transport=mock_transport)
        client.call_tool("test_tool", {"arg1": "val1"})
        params = captured.get("params", {})
        assert "_meta" in params
        assert len(params["_meta"]) > 0


class TestRA42VersionNegotiation:
    """
    RA-4.2: El estudiante debe negociar versión con discover y lanzar IncompatibleServerVersionError ante -32022.
    """

    def test_positive_successful_discovery_handshake_free(self) -> None:
        """
        [RA-4.2 POSITIVE] Confirma que discover_server devuelve las capacidades
        y versiones soportadas del servidor sin necesidad de handshake previo.
        """
        def mock_transport(req: dict) -> dict:
            return {
                "jsonrpc": "2.0",
                "id": req["id"],
                "result": {"supportedVersions": ["2026-07-28"], "capabilities": {}},
            }

        client = MCPClient(transport=mock_transport)
        disc = client.discover_server()
        assert "supportedVersions" in disc

    def test_negative_handles_unsupported_version_error(self) -> None:
        """
        [RA-4.2 NEGATIVE] Exige que el cliente capture el error -32022 y levante
        IncompatibleServerVersionError con la lista de versiones que el servidor sí soporta.
        """
        def mock_transport(req: dict) -> dict:
            return {
                "jsonrpc": "2.0",
                "id": req["id"],
                "error": {
                    "code": -32022,
                    "message": "Unsupported version",
                    "data": {"supported": ["2025-11-25"]},
                },
            }

        client = MCPClient(transport=mock_transport, client_version="2026-07-28")
        with pytest.raises(IncompatibleServerVersionError) as exc_info:
            client.discover_server()

        assert "2025-11-25" in exc_info.value.supported
        assert exc_info.value.requested_version == "2026-07-28"


class TestRA43ResultTypeDispatch:
    """
    RA-4.3: El estudiante debe despachar por resultType y tratar la ausencia como 'complete'.
    """

    def test_positive_dispatches_input_required_for_mrtr(self) -> None:
        """
        [RA-4.3 POSITIVE] Confirma que cuando el servidor responde resultType: 'input_required',
        el cliente transiciona al estado 'input_required' extrayendo el requestState.
        """
        def mock_transport(req: dict) -> dict:
            return {
                "jsonrpc": "2.0",
                "id": req["id"],
                "result": {
                    "resultType": "input_required",
                    "requestState": "signed-state-payload",
                    "inputRequests": [{"field": "otp", "prompt": "Enter OTP"}],
                },
            }

        client = MCPClient(transport=mock_transport)
        outcome = client.call_tool("mfa_tool")
        assert outcome["status"] == "input_required"
        assert outcome["requestState"] == "signed-state-payload"
        assert len(outcome["inputRequests"]) == 1

    def test_positive_absence_of_result_type_treated_as_complete(self) -> None:
        """
        [RA-4.3 POSITIVE] Confirma la regla de compatibilidad: si el resultado del servidor
        no contiene 'resultType', el cliente DEBE tratarlo como 'complete'.
        """
        def mock_legacy_transport(req: dict) -> dict:
            # Server omits resultType
            return {
                "jsonrpc": "2.0",
                "id": req["id"],
                "result": {
                    "content": [{"type": "text", "text": "Legacy output without resultType"}],
                },
            }

        client = MCPClient(transport=mock_legacy_transport)
        outcome = client.call_tool("legacy_tool")
        assert outcome["status"] == "complete"
        assert outcome["content"][0]["text"] == "Legacy output without resultType"


class TestRA44ConformanceAudit:
    """
    RA-4.4: El estudiante debe ejecutar la suite de conformidad en aislamiento total.
    """

    def test_positive_conformance_runner_evaluates_compliant_server(self) -> None:
        """
        [RA-4.4 POSITIVE] Confirma que ConformanceRunner valida todos los checks
        de conformidad contra un servidor MCP que cumple la norma 2026-07-28.
        """
        def compliant_server(req: dict) -> dict:
            method = req.get("method")
            meta = req.get("params", {}).get("_meta", {})
            if method == "initialize":
                return {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32601, "message": "Removed"}}
            if "io.modelcontextprotocol/clientCapabilities" not in meta:
                return {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32602, "message": "Missing caps"}}
            if method == "server/discover":
                return {"jsonrpc": "2.0", "id": req.get("id"), "result": {"supportedVersions": ["2026-07-28"]}}
            return {"jsonrpc": "2.0", "id": req.get("id"), "result": {}}

        report = ConformanceRunner.verify_server(compliant_server)
        assert report["supports_discover"] is True
        assert report["rejects_missing_capabilities"] is True
        assert report["rejects_initialize"] is True
