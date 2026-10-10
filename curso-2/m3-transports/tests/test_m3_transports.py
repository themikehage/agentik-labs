"""
Reference tests for Curso 2 M3 - Transportes y Asincronía MCP.
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
_spec = importlib.util.spec_from_file_location("c2_m3_solution", _solution_file)
if not _spec or not _spec.loader:
    raise ImportError(f"Cannot load solution from {_solution_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

StreamableHttpGateway = _mod.StreamableHttpGateway
TaskManager = _mod.TaskManager
IdempotencyStore = _mod.IdempotencyStore


class TestRA31StreamableHttpStateless:
    """
    RA-3.1: El estudiante debe implementar Streamable HTTP sin afinidad ni sesiones Mcp-Session-Id.
    """

    def test_positive_streamable_http_processes_request_cleanly(self) -> None:
        """
        [RA-3.1 POSITIVE] Confirma que el gateway procesa peticiones HTTP con cabecera
        X-Mcp-Transport y devuelve respuesta JSON-RPC válida.
        """
        gateway = StreamableHttpGateway()
        status, headers, body = gateway.handle_http(
            headers={"Content-Type": "application/json"},
            body={"jsonrpc": "2.0", "id": "req-1", "method": "charge_payment", "params": {"tx_id": "tx-1"}},
        )
        assert status == 200
        assert headers["X-Mcp-Transport"] == "Streamable-HTTP"
        assert body["result"]["resultType"] == "complete"

    def test_negative_ignores_or_rejects_reliance_on_mcp_session_id(self) -> None:
        """
        [RA-3.1 NEGATIVE] Detecta si el servidor asume estado o afinidad a partir de
        la cabecera obsoleta 'Mcp-Session-Id'. Dos instancias diferentes de Gateway
        deben procesar peticiones independientes sin requerir compartir sesión de transporte.
        """
        gw1 = StreamableHttpGateway()
        gw2 = StreamableHttpGateway()

        _, _, body1 = gw1.handle_http(
            headers={"Mcp-Session-Id": "legacy-session-abc"},
            body={"jsonrpc": "2.0", "id": "req-1", "method": "charge_payment", "params": {"tx_id": "tx-1"}},
        )
        _, _, body2 = gw2.handle_http(
            headers={"Mcp-Session-Id": "legacy-session-abc"},
            body={"jsonrpc": "2.0", "id": "req-2", "method": "charge_payment", "params": {"tx_id": "tx-2"}},
        )
        assert body1["id"] == "req-1"
        assert body2["id"] == "req-2"


class TestRA32Multiplexing:
    """
    RA-3.2: El estudiante debe soportar multiplexación concurrente de requests sin colisión de IDs.
    """

    def test_positive_multiplexed_batch_preserves_independent_ids(self) -> None:
        """
        [RA-3.2 POSITIVE] Confirma que un batch de llamadas concurrentes multiplexadas
        recibe respuestas mapeadas 1:1 a sus IDs correspondientes.
        """
        gateway = StreamableHttpGateway()
        batch = [
            {"jsonrpc": "2.0", "id": f"batch-{i}", "method": "charge_payment", "params": {"tx_id": f"tx-{i}"}}
            for i in range(5)
        ]
        status, _, responses = gateway.handle_http(headers={}, body=batch)
        assert status == 200
        assert len(responses) == 5
        for i, res in enumerate(responses):
            assert res["id"] == f"batch-{i}"
            assert res["result"]["chargeCount"] == 1

    def test_negative_colliding_or_missing_ids_in_batch(self) -> None:
        """
        [RA-3.2 NEGATIVE] Confirma que respuestas con errores en métodos individuales
        del batch mantienen su ID y no abortan el procesamiento de los demás RPCs.
        """
        gateway = StreamableHttpGateway()
        batch = [
            {"jsonrpc": "2.0", "id": "ok-1", "method": "charge_payment", "params": {"tx_id": "tx-ok"}},
            {"jsonrpc": "2.0", "id": "err-2", "method": "invalid_method", "params": {}},
        ]
        _, _, responses = gateway.handle_http(headers={}, body=batch)
        assert len(responses) == 2
        assert "result" in responses[0]
        assert "error" in responses[1]
        assert responses[1]["id"] == "err-2"


class TestRA33IdempotencyKey:
    """
    RA-3.3: El estudiante debe garantizar la idempotencia de mutaciones mediante Idempotency-Key.
    """

    def test_positive_idempotent_retry_prevents_duplicate_execution(self) -> None:
        """
        [RA-3.3 POSITIVE] Confirma que reenviar una petición con la misma Idempotency-Key
        devuelve el mismo resultado y NO vuelve a incrementar el contador de cobro (side-effect).
        """
        gateway = StreamableHttpGateway()
        headers = {"Idempotency-Key": "idem-uuid-999"}
        req = {"jsonrpc": "2.0", "id": "charge-1", "method": "charge_payment", "params": {"tx_id": "tx-999"}}

        _, h1, res1 = gateway.handle_http(headers=headers, body=req)
        assert h1["X-Cache-Lookup"] == "MISS"
        assert res1["result"]["chargeCount"] == 1

        # Second identical request with same key
        _, h2, res2 = gateway.handle_http(headers=headers, body=req)
        assert h2["X-Cache-Lookup"] == "HIT"
        assert res2["result"]["chargeCount"] == 1
        assert gateway.execution_counts["tx-999"] == 1

    def test_negative_different_idempotency_key_triggers_new_execution(self) -> None:
        """
        [RA-3.3 NEGATIVE] Confirma que con distinta Idempotency-Key la operación sí
        se ejecuta nuevamente.
        """
        gateway = StreamableHttpGateway()
        req = {"jsonrpc": "2.0", "id": "charge-1", "method": "charge_payment", "params": {"tx_id": "tx-multi"}}

        gateway.handle_http(headers={"Idempotency-Key": "key-alpha"}, body=req)
        assert gateway.execution_counts["tx-multi"] == 1

        gateway.handle_http(headers={"Idempotency-Key": "key-beta"}, body=req)
        assert gateway.execution_counts["tx-multi"] == 2


class TestRA34AsyncTasksLifecycle:
    """
    RA-3.4: El estudiante debe gestionar tareas de larga duración con tasks/get y rechazar tasks/result.
    """

    def test_positive_tasks_get_and_update_lifecycle(self) -> None:
        """
        [RA-3.4 POSITIVE] Confirma que una tarea asíncrona se consulta mediante tasks/get
        y progresa de running a completed mediante tasks/update.
        """
        task_mgr = TaskManager()
        gateway = StreamableHttpGateway(task_manager=task_mgr)
        task_id = task_mgr.create_task("data_export", {"dataset": "analytics"})

        # Query initial state
        _, _, res_get = gateway.handle_http(
            headers={},
            body={"jsonrpc": "2.0", "id": "t-1", "method": "tasks/get", "params": {"taskId": task_id}},
        )
        assert res_get["result"]["status"] == "running"
        assert res_get["result"]["progress"] == 0.0

        # Update to completed
        gateway.handle_http(
            headers={},
            body={
                "jsonrpc": "2.0",
                "id": "t-2",
                "method": "tasks/update",
                "params": {"taskId": task_id, "status": "completed", "progress": 1.0, "result": {"rows": 1000}},
            },
        )

        _, _, res_final = gateway.handle_http(
            headers={},
            body={"jsonrpc": "2.0", "id": "t-3", "method": "tasks/get", "params": {"taskId": task_id}},
        )
        assert res_final["result"]["status"] == "completed"
        assert res_final["result"]["result"]["rows"] == 1000

    def test_negative_rejects_tasks_result_method_with_32601(self) -> None:
        """
        [RA-3.4 NEGATIVE] Detecta el error común de invocar 'tasks/result'.
        Dicho método no existe en el estándar MCP y debe devolver -32601 indicando usar 'tasks/get'.
        """
        gateway = StreamableHttpGateway()
        _, _, res = gateway.handle_http(
            headers={},
            body={"jsonrpc": "2.0", "id": "bad-task-call", "method": "tasks/result", "params": {"taskId": "t-1"}},
        )
        assert "error" in res
        assert res["error"]["code"] == -32601
        assert "tasks/get" in res["error"]["message"]
