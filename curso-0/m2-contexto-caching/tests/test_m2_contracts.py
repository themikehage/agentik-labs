"""
Reference tests for Curso 0 M2 - Contexto, Caching y Contratos.
Strictly follows the test conventions:
- One test function per acceptance criterion citing the RA in docstring.
- Both positive and negative test cases to detect conceptual bugs.
- Zero network socket usage, zero real sleep.
"""

from __future__ import annotations

import json
import sys
import importlib.util
from pathlib import Path
import pytest

_solution_file = Path(__file__).resolve().parent.parent / "solution.py"
_spec = importlib.util.spec_from_file_location("c0_m2_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

PromptCacheSerializer = _mod.PromptCacheSerializer
PromptCacheEconomics = _mod.PromptCacheEconomics
PricingModel = _mod.PricingModel
ThreeLayerValidator = _mod.ThreeLayerValidator
ToolExecutionEngine = _mod.ToolExecutionEngine


class TestRA21CacheFriendlyPromptStructure:
    """
    RA-2.1: Estructura de prompt cache-friendly con prefijo estable byte a byte y variables al final.
    """

    def test_positive_identical_prefix_hash_with_trailing_variables(self) -> None:
        """
        [RA-2.1 POSITIVE] Confirma que dos llamadas consecutivas con diferentes variables
        dinámicas de usuario al final producen exactamente el mismo hash de prefijo byte a byte.
        """
        serializer = PromptCacheSerializer()
        static_sys = "You are an enterprise extraction specialist in Agentik ERP."
        few_shots = [
            {"input": "Order 100", "output": '{"order_id": 100}'},
            {"input": "Order 200", "output": '{"order_id": 200}'},
        ]
        schema = {"type": "object", "properties": {"order_id": {"type": "integer"}}}

        vars_call1 = {"user_query": "Process invoice #8891", "user_id": "usr-1"}
        vars_call2 = {"user_query": "Process invoice #9923", "user_id": "usr-2"}

        _, hash1 = serializer.serialize_prompt(static_sys, few_shots, schema, vars_call1)
        _, hash2 = serializer.serialize_prompt(static_sys, few_shots, schema, vars_call2)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_negative_early_variables_invalidate_prefix_hash(self) -> None:
        """
        [RA-2.1 NEGATIVE] Demuestra que insertar variables volátiles (ej. timestamp)
        al inicio del prompt rompe la contigüidad del prefijo y cambia el hash SHA-256.
        """
        serializer = PromptCacheSerializer()
        static_sys = "You are an enterprise extraction specialist in Agentik ERP."
        few_shots = [{"input": "Order 100", "output": '{"order_id": 100}'}]
        schema = {"type": "object"}

        vars_t1 = {"timestamp": "2026-10-10T10:00:00Z", "query": "Find order"}
        vars_t2 = {"timestamp": "2026-10-10T10:01:00Z", "query": "Find order"}

        _, hash1 = serializer.serialize_prompt(
            static_sys, few_shots, schema, vars_t1, place_variables_early=True
        )
        _, hash2 = serializer.serialize_prompt(
            static_sys, few_shots, schema, vars_t2, place_variables_early=True
        )

        assert hash1 != hash2


class TestRA22PromptCacheEconomicsBreakEven:
    """
    RA-2.2: Modelo económico de break-even de prompt caching sobre tabla versionada.
    """

    def test_positive_break_even_minimum_reads_calculation(self) -> None:
        """
        [RA-2.2 POSITIVE] Calcula el mínimo de llamadas de reutilización para que el caché
        sea rentable, considerando recargo de escritura (write surcharge) y descuento de lectura.
        """
        pricing = PricingModel(
            base_input_usd_per_m=3.00,
            cache_write_usd_per_m=3.75,
            cache_read_usd_per_m=0.30,
            output_usd_per_m=15.00,
        )
        economics = PromptCacheEconomics(pricing)

        # Break-even formula: (write - read) / (base - read) = (3.75 - 0.30) / (3.00 - 0.30) = 3.45 / 2.70 = 1.277 -> ceil = 2
        break_even = economics.calculate_break_even_reads()
        assert break_even == 2

        # At 1 reuse (only write), cached cost is HIGHER than uncached cost
        comparison_1 = economics.calculate_cost_comparison(prefix_tokens=100_000, reuse_count=1)
        assert comparison_1["cost_cached_usd"] > comparison_1["cost_uncached_usd"]

        # At 2 reuses, cached cost is LOWER than uncached cost
        comparison_2 = economics.calculate_cost_comparison(prefix_tokens=100_000, reuse_count=2)
        assert comparison_2["cost_cached_usd"] < comparison_2["cost_uncached_usd"]
        assert comparison_2["savings_ratio"] > 0.0

    def test_negative_ignoring_write_cost_produces_flawed_breakeven(self) -> None:
        """
        [RA-2.2 NEGATIVE] Falla si se ignora el coste de escritura asumiendo erróneamente
        que el caché es rentable desde la primera llamada sin amortización.
        """
        pricing = PricingModel(
            base_input_usd_per_m=3.00,
            cache_write_usd_per_m=3.75,
            cache_read_usd_per_m=0.30,
            output_usd_per_m=15.00,
        )
        economics = PromptCacheEconomics(pricing)

        flawed_breakeven = economics.calculate_break_even_reads(ignore_write_surcharge=True)
        assert flawed_breakeven == 1
        real_breakeven = economics.calculate_break_even_reads()
        assert real_breakeven > flawed_breakeven


class TestRA23ThreeLayerValidation:
    """
    RA-2.3: Validación de tres capas (sintaxis -> esquema -> semántica de negocio).
    """

    def test_positive_semantic_business_rejection_of_schema_valid_payload(self) -> None:
        """
        [RA-2.3 POSITIVE] Demuestra que un payload con sintaxis JSON válida y tipos
        de esquema conformes pero con inconsistencia aritmética de negocio es rechazado.
        """
        validator = ThreeLayerValidator()
        payload = json.dumps({
            "invoice_id": "INV-2026-001",
            "currency": "USD",
            "items": [
                {"qty": 2, "unit_price": 10.0},
                {"qty": 1, "unit_price": 15.0},
            ],
            "total_amount_usd": 100.0,
        })

        result = validator.validate_invoice(payload)
        assert not result.is_valid
        assert result.layer_failed == "business_semantic"
        assert "sum of item line totals" in (result.error_message or "")

    def test_negative_pure_schema_validator_fails_to_catch_business_hallucination(self) -> None:
        """
        [RA-2.3 NEGATIVE] Demuestra que validar únicamente sintaxis y esquema aceptaría
        un importe alucinado, evidenciando la necesidad obligatoria de la capa 3.
        """
        validator = ThreeLayerValidator()
        payload = json.dumps({
            "invoice_id": "INV-2026-001",
            "currency": "USD",
            "items": [
                {"qty": 2, "unit_price": 10.0},
            ],
            "total_amount_usd": 999.0,
        })

        # Syntax check passes
        raw = json.loads(payload)
        # Schema field check passes
        schema_passed = all(k in raw for k in ["invoice_id", "items", "total_amount_usd", "currency"])
        assert schema_passed is True

        # Full 3-layer validator correctly catches the business hallucination
        result = validator.validate_invoice(payload)
        assert result.is_valid is False
        assert result.layer_failed == "business_semantic"


class TestRA24ToolExecutionCycle:
    """
    RA-2.4: Ciclo tool_use -> tool_result con validación de argumentos antes de ejecución.
    """

    def test_positive_valid_arguments_executes_and_returns_content(self) -> None:
        """
        [RA-2.4 POSITIVE] Ejecuta la herramienta cuando los argumentos cumplen el esquema.
        """
        engine = ToolExecutionEngine()
        executed_tracker = []

        def mock_refund(order_id: str, amount_cents: int) -> dict[str, str]:
            executed_tracker.append((order_id, amount_cents))
            return {"status": "refunded", "order_id": order_id}

        engine.register_tool(
            name="process_refund",
            parameters_schema={"order_id": str, "amount_cents": int},
            handler=mock_refund,
        )

        res = engine.execute_tool_call("process_refund", {"order_id": "ord-1", "amount_cents": 5000})
        assert not res.is_error
        assert res.content == {"status": "refunded", "order_id": "ord-1"}
        assert len(executed_tracker) == 1

    def test_negative_invalid_arguments_returns_error_without_execution(self) -> None:
        """
        [RA-2.4 NEGATIVE] Con argumentos inválidos (tipo erróneo o faltante), devuelve
        error estructurado sin invocar el handler ni lanzar excepciones no controladas.
        """
        engine = ToolExecutionEngine()
        executed_tracker = []

        def mock_refund(order_id: str, amount_cents: int) -> dict[str, str]:
            executed_tracker.append((order_id, amount_cents))
            return {"status": "refunded"}

        engine.register_tool(
            name="process_refund",
            parameters_schema={"order_id": str, "amount_cents": int},
            handler=mock_refund,
        )

        res = engine.execute_tool_call(
            "process_refund", {"order_id": "ord-1", "amount_cents": "5000"}
        )
        assert res.is_error is True
        assert res.error_code == "INVALID_ARGUMENTS"
        assert len(executed_tracker) == 0
