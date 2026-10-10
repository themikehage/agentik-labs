"""
Reference tests for Curso 2 M1 - Especificación y Primitivas MCP (2026-07-28).
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
_spec = importlib.util.spec_from_file_location("c2_m1_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

MCPServer = _mod.MCPServer
classify_legacy_features = _mod.classify_legacy_features


class TestRA11ClientCapabilities:
    """
    RA-1.1: El estudiante debe exigir clientCapabilities en _meta y rechazar con -32602 si falta.
    """

    def test_positive_requires_capabilities_in_meta(self) -> None:
        """
        [RA-1.1 POSITIVE] Confirma que una llamada con clientCapabilities válidas en _meta
        es procesada exitosamente por el servidor sin rechazo de validación.
        """
        server = MCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": "req-1",
            "method": "server/discover",
            "params": {
                "_meta": {
                    "version": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {
                        "experimental": {}
                    },
                }
            },
        }
        response = server.handle_request(request)
        assert "result" in response
        assert response["id"] == "req-1"
        assert "supportedVersions" in response["result"]

    def test_negative_rejects_missing_client_capabilities_with_32602(self) -> None:
        """
        [RA-1.1 NEGATIVE] Detecta la falta de capacidades del cliente en _meta y exige
        código de error -32602 (Invalid params).
        """
        server = MCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": "req-bad",
            "method": "server/discover",
            "params": {
                "_meta": {
                    "version": "2026-07-28"
                }
            },
        }
        response = server.handle_request(request)
        assert "error" in response
        assert response["error"]["code"] == -32602

    def test_negative_stateless_server_does_not_cache_capabilities(self) -> None:
        """
        [RA-1.1 NEGATIVE] Detecta el error conceptual de asumir que el servidor "recuerda"
        las capacidades de una conexión previa. Una llamada posterior sin _meta debe fallar
        incluso si la llamada anterior tuvo éxito.
        """
        server = MCPServer()
        req_valid = {
            "jsonrpc": "2.0",
            "id": "req-1",
            "method": "server/discover",
            "params": {
                "_meta": {
                    "version": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        }
        server.handle_request(req_valid)

        req_missing = {
            "jsonrpc": "2.0",
            "id": "req-2",
            "method": "server/discover",
            "params": {"_meta": {"version": "2026-07-28"}},
        }
        res_missing = server.handle_request(req_missing)
        assert "error" in res_missing
        assert res_missing["error"]["code"] == -32602


class TestRA12ProtocolVersioning:
    """
    RA-1.2: El estudiante debe implementar server/discover y devolver -32022 ante versiones no soportadas.
    """

    def test_positive_server_discover_and_version_support(self) -> None:
        """
        [RA-1.2 POSITIVE] Confirma que server/discover devuelve la lista de versiones
        soportadas conteniendo '2026-07-28'.
        """
        server = MCPServer()
        request = {
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
        response = server.handle_request(request)
        assert response["result"]["supportedVersions"] == ["2026-07-28"]

    def test_negative_rejects_unsupported_version_with_code_32022(self) -> None:
        """
        [RA-1.2 NEGATIVE] Exige que una versión incompatible (ej. 1900-01-01) responda
        estrictamente con -32022 (UnsupportedProtocolVersionError) incluyendo 'data.supported'.
        """
        server = MCPServer()
        request = {
            "jsonrpc": "2.0",
            "id": "ver-bad",
            "method": "server/discover",
            "params": {
                "_meta": {
                    "version": "1900-01-01",
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        }
        response = server.handle_request(request)
        assert "error" in response
        assert response["error"]["code"] == -32022
        assert "supported" in response["error"]["data"]


class TestRA13MRTRWorkflow:
    """
    RA-1.3: El estudiante debe implementar el patrón MRTR con resultType 'input_required'.
    """

    def test_positive_mrtr_input_required_and_resume(self) -> None:
        """
        [RA-1.3 POSITIVE] Confirma el ciclo completo de dos pasos de MRTR:
        1. Primer tools/call devuelve resultType: 'input_required' con inputRequests y requestState firmado.
        2. Segundo tools/call aporta inputResponses y completa la operación con resultType: 'complete'.
        """
        server = MCPServer()
        meta = {
            "version": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        }
        req_step1 = {
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {
                "name": "transfer_funds",
                "arguments": {"amount": 500},
                "_meta": meta,
            },
        }
        res1 = server.handle_request(req_step1)
        assert res1["result"]["resultType"] == "input_required"
        assert len(res1["result"]["inputRequests"]) == 1
        req_state = res1["result"]["requestState"]

        req_step2 = {
            "jsonrpc": "2.0",
            "id": "call-2",
            "method": "tools/call",
            "params": {
                "name": "transfer_funds",
                "inputResponses": {"auth_code": "123456"},
                "requestState": req_state,
                "_meta": meta,
            },
        }
        res2 = server.handle_request(req_step2)
        assert res2["result"]["resultType"] == "complete"
        assert not res2["result"].get("isError", False)

    def test_negative_mrtr_fails_if_server_retains_process_memory(self) -> None:
        """
        [RA-1.3 NEGATIVE] Confirma que la reanudación funciona entre dos réplicas o instancias
        completamente desacopladas sin memoria compartida, demostrando que todo el estado
        reside en el handle firmado de requestState.
        """
        replica_a = MCPServer()
        replica_b = MCPServer()

        meta = {
            "version": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        }
        res1 = replica_a.handle_request({
            "jsonrpc": "2.0",
            "id": "step-1",
            "method": "tools/call",
            "params": {"name": "transfer_funds", "arguments": {}, "_meta": meta},
        })
        state = res1["result"]["requestState"]

        res2 = replica_b.handle_request({
            "jsonrpc": "2.0",
            "id": "step-2",
            "method": "tools/call",
            "params": {
                "name": "transfer_funds",
                "inputResponses": {"auth_code": "123456"},
                "requestState": state,
                "_meta": meta,
            },
        })
        assert res2["result"]["resultType"] == "complete"


class TestRA14DeprecatedFeatures:
    """
    RA-1.4: El estudiante debe clasificar Roots, Sampling y Logging como Deprecated y rechazar initialize/ping.
    """

    def test_positive_roots_sampling_logging_classified_deprecated(self) -> None:
        """
        [RA-1.4 POSITIVE] Confirma que las tres características obsoletas de revisiones anteriores
        son catalogadas explícitamente como deprecated con su correspondiente alternativa arquitectónica.
        """
        report = classify_legacy_features()
        for feature in ("roots", "sampling", "logging"):
            assert feature in report
            assert report[feature]["status"] == "deprecated"
            assert len(report[feature]["migration"]) > 5

    def test_negative_server_rejects_initialize_and_ping_methods(self) -> None:
        """
        [RA-1.4 NEGATIVE] Detecta el error común de implementar 'initialize' o 'ping' en 2026-07-28.
        Ambos métodos deben responder con error -32601 (Method not found / obsolete).
        """
        server = MCPServer()
        for method in ("initialize", "ping"):
            res = server.handle_request({
                "jsonrpc": "2.0",
                "id": f"test-{method}",
                "method": method,
                "params": {},
            })
            assert "error" in res
            assert res["error"]["code"] == -32601
