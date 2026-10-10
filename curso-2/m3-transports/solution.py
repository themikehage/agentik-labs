"""
Reference implementation for Curso 2 M3 - Transportes y Asincronía MCP.
Stateless Streamable HTTP gateway, multiplexing, idempotency keys, and async tasks.
"""

from __future__ import annotations

import uuid
from typing import Any


class IdempotencyStore:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self._cache.get(key)

    def set(self, key: str, response: dict[str, Any]) -> None:
        self._cache[key] = response


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}

    def create_task(self, name: str, params: dict[str, Any]) -> str:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        self._tasks[task_id] = {
            "taskId": task_id,
            "name": name,
            "status": "running",
            "progress": 0.0,
            "result": None,
            "error": None,
        }
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._tasks.get(task_id)

    def update_task(
        self,
        task_id: str,
        status: str,
        progress: float = 1.0,
        result: Any = None,
        error: str | None = None,
    ) -> bool:
        if task_id not in self._tasks:
            return False
        self._tasks[task_id].update({
            "status": status,
            "progress": progress,
            "result": result,
            "error": error,
        })
        return True


class StreamableHttpGateway:
    def __init__(
        self,
        idempotency_store: IdempotencyStore | None = None,
        task_manager: TaskManager | None = None,
    ) -> None:
        self.idempotency = idempotency_store or IdempotencyStore()
        self.task_manager = task_manager or TaskManager()
        self.execution_counts: dict[str, int] = {}

    def process_rpc(self, req: dict[str, Any]) -> dict[str, Any]:
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        if method == "tasks/result":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": "Method 'tasks/result' is obsolete and invalid. Use 'tasks/get' to inspect task status.",
                },
            }

        if method == "tasks/get":
            task_id = params.get("taskId")
            task = self.task_manager.get_task(task_id or "")
            if not task:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": f"Task '{task_id}' not found"},
                }
            return {"jsonrpc": "2.0", "id": req_id, "result": task}

        if method == "tasks/update":
            task_id = params.get("taskId")
            status = params.get("status", "completed")
            progress = params.get("progress", 1.0)
            res = params.get("result")
            success = self.task_manager.update_task(task_id or "", status, progress, res)
            if not success:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32602, "message": f"Task '{task_id}' not found"},
                }
            return {"jsonrpc": "2.0", "id": req_id, "result": {"success": True}}

        if method == "charge_payment":
            tx_id = params.get("tx_id", "tx-default")
            self.execution_counts[tx_id] = self.execution_counts.get(tx_id, 0) + 1
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resultType": "complete",
                    "receipt": f"receipt-{tx_id}",
                    "chargeCount": self.execution_counts[tx_id],
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }

    def handle_http(
        self,
        headers: dict[str, str],
        body: dict[str, Any] | list[dict[str, Any]],
    ) -> tuple[int, dict[str, str], Any]:
        resp_headers = {
            "Content-Type": "application/json",
            "X-Mcp-Transport": "Streamable-HTTP",
        }

        # Idempotency check for single mutating request
        idem_key = headers.get("Idempotency-Key") or headers.get("idempotency-key")
        if idem_key and isinstance(body, dict):
            cached = self.idempotency.get(idem_key)
            if cached:
                resp_headers["X-Cache-Lookup"] = "HIT"
                return 200, resp_headers, cached

        if isinstance(body, list):
            # Multiplexed batch of concurrent RPC calls
            responses = [self.process_rpc(single_req) for single_req in body]
            return 200, resp_headers, responses

        resp = self.process_rpc(body)
        if idem_key and "result" in resp:
            self.idempotency.set(idem_key, resp)
            resp_headers["X-Cache-Lookup"] = "MISS"

        return 200, resp_headers, resp
