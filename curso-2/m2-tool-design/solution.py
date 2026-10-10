"""
Reference implementation for Curso 2 M2 - Diseño de Herramientas y Esquemas MCP.
Features schema validation, structuredContent, progressive disclosure, and token profiling.
"""

from __future__ import annotations

import json
from typing import Any, Callable
from labkit.tokenizer import OfflineTokenizer


class ToolValidationError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class BusinessError(Exception):
    def __init__(self, message: str, retry_hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.retry_hint = retry_hint


def _validate_json_schema(schema: dict[str, Any], data: dict[str, Any]) -> None:
    if schema.get("type") != "object":
        return

    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    additional = schema.get("additionalProperties", True)

    for req_field in required:
        if req_field not in data:
            raise ToolValidationError(-32602, f"Missing required parameter: {req_field}")

    if additional is False:
        for k in data:
            if k not in properties:
                raise ToolValidationError(-32602, f"Unexpected parameter not allowed: {k}")

    for k, val in data.items():
        if k in properties:
            expected_type = properties[k].get("type")
            if expected_type == "integer" and (not isinstance(val, int) or isinstance(val, bool)):
                raise ToolValidationError(-32602, f"Parameter '{k}' must be integer")
            if expected_type == "string" and not isinstance(val, str):
                raise ToolValidationError(-32602, f"Parameter '{k}' must be string")
            if expected_type == "number" and not isinstance(val, (int, float)):
                raise ToolValidationError(-32602, f"Parameter '{k}' must be number")


def _has_external_network_ref(data: Any) -> bool:
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "$ref" and isinstance(v, str) and (v.startswith("http://") or v.startswith("https://")):
                return True
            if _has_external_network_ref(v):
                return True
    elif isinstance(data, list):
        for item in data:
            if _has_external_network_ref(item):
                return True
    return False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        handler: Callable[[dict[str, Any]], Any],
        namespace: str = "default",
    ) -> None:
        if _has_external_network_ref(input_schema) or _has_external_network_ref(output_schema):
            raise ToolValidationError(
                -32602, "Security violation: External network $ref resolution is disabled by default"
            )

        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "outputSchema": output_schema,
            "namespace": namespace,
        }
        self._handlers[name] = handler

    def list_tools(
        self,
        namespace: str | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        results = []
        for name, tool in self._tools.items():
            if namespace and tool["namespace"] != namespace:
                continue
            if query and query.lower() not in name.lower() and query.lower() not in tool["description"].lower():
                continue
            results.append({
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
                "outputSchema": tool["outputSchema"],
            })
        return results

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Tool '{name}' not found in registry",
                },
            }

        tool = self._tools[name]
        handler = self._handlers[name]

        try:
            _validate_json_schema(tool["inputSchema"], arguments)
        except ToolValidationError as e:
            return {
                "jsonrpc": "2.0",
                "error": {"code": e.code, "message": e.message},
            }

        try:
            raw_result = handler(arguments)
        except BusinessError as e:
            msg = e.message
            if e.retry_hint:
                msg += f" (Hint: {e.retry_hint})"
            return {
                "jsonrpc": "2.0",
                "result": {
                    "resultType": "complete",
                    "isError": True,
                    "content": [{"type": "text", "text": msg}],
                },
            }

        try:
            _validate_json_schema(tool["outputSchema"], raw_result)
        except ToolValidationError as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Server output validation failed: {e.message}",
                },
            }

        return {
            "jsonrpc": "2.0",
            "result": {
                "resultType": "complete",
                "structuredContent": raw_result,
                "content": [{"type": "text", "text": json.dumps(raw_result)}],
            },
        }


class ToolCatalogProfiler:
    def __init__(self, tokenizer: OfflineTokenizer | None = None) -> None:
        self.tokenizer = tokenizer or OfflineTokenizer()

    def profile_catalog(
        self,
        full_catalog: list[dict[str, Any]],
        progressive_catalog: list[dict[str, Any]],
    ) -> dict[str, Any]:
        text_full = json.dumps(full_catalog, separators=(",", ":"))
        text_prog = json.dumps(progressive_catalog, separators=(",", ":"))

        t_full = self.tokenizer.count_tokens(text_full)
        t_min = self.tokenizer.count_tokens(text_prog)

        savings = max(0, t_full - t_min)
        savings_pct = (savings / t_full * 100.0) if t_full > 0 else 0.0

        return {
            "t_full": t_full,
            "t_min": t_min,
            "saved_tokens": savings,
            "savings_percentage": round(savings_pct, 2),
        }
