"""
Reference tests for Curso 2 M2 - Diseño de Herramientas y Esquemas MCP.
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
_spec = importlib.util.spec_from_file_location("c2_m2_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ToolRegistry = _mod.ToolRegistry
ToolCatalogProfiler = _mod.ToolCatalogProfiler
ToolValidationError = _mod.ToolValidationError
BusinessError = _mod.BusinessError
from labkit.tokenizer import OfflineTokenizer


class TestRA21SchemaAndOutputValidation:
    """
    RA-2.1: El estudiante debe validar structuredContent contra outputSchema y bloquear $ref externos.
    """

    def test_positive_structured_content_conforms_to_output_schema(self) -> None:
        """
        [RA-2.1 POSITIVE] Confirma que una herramienta que genera salida conforme
        a su outputSchema retorna resultType: 'complete' con structuredContent íntegro.
        """
        registry = ToolRegistry()
        input_schema = {
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
            "required": ["user_id"],
            "additionalProperties": False,
        }
        output_schema = {
            "type": "object",
            "properties": {"status": {"type": "string"}, "balance": {"type": "integer"}},
            "required": ["status", "balance"],
            "additionalProperties": False,
        }

        registry.register_tool(
            name="get_account_balance",
            description="Returns current balance",
            input_schema=input_schema,
            output_schema=output_schema,
            handler=lambda args: {"status": "active", "balance": 1500},
        )

        res = registry.call_tool("get_account_balance", {"user_id": "usr-123"})
        assert "result" in res
        assert res["result"]["resultType"] == "complete"
        assert res["result"]["structuredContent"] == {"status": "active", "balance": 1500}

    def test_negative_rejects_external_network_ref(self) -> None:
        """
        [RA-2.1 NEGATIVE] Exige que el registro de herramientas rechace cualquier esquema
        que intente dereferenciar un URI externo por red vía $ref (vector de SSRF).
        """
        registry = ToolRegistry()
        schema_with_ssrf_ref = {
            "type": "object",
            "$ref": "https://attacker.example.com/malicious.json",
        }

        with pytest.raises(ToolValidationError) as exc_info:
            registry.register_tool(
                name="unsafe_tool",
                description="Unsafe external ref",
                input_schema=schema_with_ssrf_ref,
                output_schema={"type": "object"},
                handler=lambda args: {},
            )
        assert "External network $ref" in exc_info.value.message

    def test_negative_rejects_unexpected_additional_properties(self) -> None:
        """
        [RA-2.1 NEGATIVE] Detecta violación de esquema cuando el llamador envía parámetros
        no declarados contra un inputSchema con additionalProperties: False.
        """
        registry = ToolRegistry()
        input_schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "additionalProperties": False,
        }
        registry.register_tool(
            name="search",
            description="Search query",
            input_schema=input_schema,
            output_schema={"type": "object"},
            handler=lambda args: {"found": 0},
        )

        res = registry.call_tool("search", {"query": "test", "injected_param": "payload"})
        assert "error" in res
        assert res["error"]["code"] == -32602
        assert "Unexpected parameter not allowed" in res["error"]["message"]


class TestRA22CatalogTokenProfiling:
    """
    RA-2.2: El estudiante debe medir el ahorro en tokens mediante OfflineTokenizer.
    """

    def test_positive_measures_real_token_savings_with_offline_tokenizer(self) -> None:
        """
        [RA-2.2 POSITIVE] Confirma que el profiler calcula T_full, T_min y ahorro
        basándose en mediciones reales de tokens sobre el catálogo BPE, no en números estáticos.
        """
        tokenizer = OfflineTokenizer()
        profiler = ToolCatalogProfiler(tokenizer=tokenizer)

        full_cat = [
            {"name": f"admin_tool_{i}", "description": "Administrative cluster control tool with extensive schemas"}
            for i in range(20)
        ]
        filtered_cat = [
            {"name": "admin_tool_0", "description": "Administrative cluster control tool with extensive schemas"}
        ]

        report = profiler.profile_catalog(full_cat, filtered_cat)
        assert report["t_full"] > report["t_min"]
        assert report["saved_tokens"] > 0
        assert report["savings_percentage"] > 50.0

    def test_negative_fails_if_savings_are_mocked_or_zero_with_shrinking(self) -> None:
        """
        [RA-2.2 NEGATIVE] Detecta si alguien hardcodea el ahorro en 0% cuando el catálogo
        se reduce drásticamente.
        """
        profiler = ToolCatalogProfiler()
        full_cat = [{"name": f"t_{i}", "desc": "long payload text describing functionality"} for i in range(15)]
        single_tool = [full_cat[0]]

        report = profiler.profile_catalog(full_cat, single_tool)
        assert report["savings_percentage"] != 0.0
        assert report["saved_tokens"] == (report["t_full"] - report["t_min"])


class TestRA23ProgressiveDisclosure:
    """
    RA-2.3: El estudiante debe aplicar divulgación progresiva por namespaces o relevancia.
    """

    def test_positive_progressive_disclosure_exposes_relevant_subset(self) -> None:
        """
        [RA-2.3 POSITIVE] Confirma que la divulgación progresiva permite al cliente
        obtener únicamente las herramientas de un dominio específico (namespace).
        """
        registry = ToolRegistry()
        for i in range(5):
            registry.register_tool(
                name=f"finance_op_{i}",
                description="Financial transactions",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                handler=lambda args: {},
                namespace="finance",
            )
        for j in range(5):
            registry.register_tool(
                name=f"devops_op_{j}",
                description="Cloud deployment",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                handler=lambda args: {},
                namespace="devops",
            )

        finance_tools = registry.list_tools(namespace="finance")
        assert len(finance_tools) == 5
        assert all(t["name"].startswith("finance_") for t in finance_tools)

    def test_negative_query_filtering_hides_unrelated_tools(self) -> None:
        """
        [RA-2.3 NEGATIVE] Confirma que un filtrado por query oculta herramientas
        no relacionadas, impidiendo la sobrecarga del contexto del LLM.
        """
        registry = ToolRegistry()
        registry.register_tool(
            name="calculate_tax",
            description="Computes sales taxes",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            handler=lambda args: {},
        )
        registry.register_tool(
            name="reboot_server",
            description="Restarts linux node",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            handler=lambda args: {},
        )

        tools = registry.list_tools(query="tax")
        assert len(tools) == 1
        assert tools[0]["name"] == "calculate_tax"


class TestRA24ErrorHandlingSemantics:
    """
    RA-2.4: El estudiante debe separar errores de negocio (isError: true) de errores de protocolo (-32601).
    """

    def test_positive_business_error_reported_as_actionable_tool_result(self) -> None:
        """
        [RA-2.4 POSITIVE] Confirma que una falla de negocio (ej. falta de inventario)
        se devuelve como resultado de herramienta exitoso en protocolo con isError: true
        y una pista accionable que permita la autocorrección del modelo.
        """
        registry = ToolRegistry()

        def inventory_handler(args: dict) -> dict:
            qty = args.get("quantity", 0)
            if qty > 5:
                raise BusinessError("Insufficient stock in warehouse", retry_hint="Maximum available quantity is 5")
            return {"status": "reserved", "quantity": qty}

        registry.register_tool(
            name="reserve_stock",
            description="Reserve inventory",
            input_schema={"type": "object", "properties": {"quantity": {"type": "integer"}}},
            output_schema={"type": "object"},
            handler=inventory_handler,
        )

        res = registry.call_tool("reserve_stock", {"quantity": 10})
        assert "result" in res
        assert res["result"]["isError"] is True
        assert "Maximum available quantity is 5" in res["result"]["content"][0]["text"]

    def test_negative_missing_tool_returns_protocol_error_32601(self) -> None:
        """
        [RA-2.4 NEGATIVE] Confirma que una herramienta inexistente NO devuelve isError: true
        dentro de un resultado, sino un error de protocolo JSON-RPC con código -32601.
        """
        registry = ToolRegistry()
        res = registry.call_tool("non_existent_tool", {})
        assert "error" in res
        assert res["error"]["code"] == -32601
