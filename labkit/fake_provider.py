from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable
from urllib.parse import urlparse
from labkit.clock import Clock, RealClock


class _FakeProviderHandler(BaseHTTPRequestHandler):
    server: "_FakeHTTPServer"  # Type hint for custom server

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress standard logging during tests
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/health", "/v1/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "provider": "fake-provider"}')
            return

        if parsed.path in ("/v1/models", "/models"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"object": "list", "data": [{"id": "agentik-fake-v1", "object": "model"}]}')
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/v1/chat/completions", "/chat/completions"):
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)
        try:
            body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            body = {}

        self.server.recorded_requests.append(body)

        stream = bool(body.get("stream", False))
        model = body.get("model", "agentik-fake-v1")

        # Configured or custom response handler
        response_text = self.server.response_generator(body)
        ttft_s = self.server.ttft_ms / 1000.0
        itl_s = self.server.itl_ms / 1000.0

        if not stream:
            # Simulate TTFT latency
            self.server.clock.sleep(ttft_s)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            prompt_toks = 15
            comp_toks = len(response_text.split())
            payload = {
                "id": "chatcmpl-agentik-fake",
                "object": "chat.completion",
                "created": int(self.server.clock.now()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": response_text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_toks,
                    "completion_tokens": comp_toks,
                    "total_tokens": prompt_toks + comp_toks,
                },
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        # Streaming SSE protocol
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        # Simulate TTFT before first token
        self.server.clock.sleep(ttft_s)

        words = response_text.split()
        if not words:
            words = [""]

        # Initial empty delta with role
        init_chunk = {
            "id": "chatcmpl-agentik-fake",
            "object": "chat.completion.chunk",
            "created": int(self.server.clock.now()),
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
        }
        self.wfile.write(f"data: {json.dumps(init_chunk)}\n\n".encode("utf-8"))
        self.wfile.flush()

        # Stream words as tokens with ITL latency
        for idx, word in enumerate(words):
            if idx > 0:
                self.server.clock.sleep(itl_s)

            delta_text = word + (" " if idx < len(words) - 1 else "")
            chunk = {
                "id": "chatcmpl-agentik-fake",
                "object": "chat.completion.chunk",
                "created": int(self.server.clock.now()),
                "model": model,
                "choices": [{"index": 0, "delta": {"content": delta_text}, "finish_reason": None}],
            }
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
            self.wfile.flush()

        # Final stop chunk
        stop_chunk = {
            "id": "chatcmpl-agentik-fake",
            "object": "chat.completion.chunk",
            "created": int(self.server.clock.now()),
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        self.wfile.write(f"data: {json.dumps(stop_chunk)}\n\n".encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


class _FakeHTTPServer(HTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        clock: Clock,
        ttft_ms: float,
        itl_ms: float,
        response_generator: Callable[[dict[str, Any]], str],
    ) -> None:
        super().__init__(server_address, _FakeProviderHandler)
        self.clock = clock
        self.ttft_ms = ttft_ms
        self.itl_ms = itl_ms
        self.response_generator = response_generator
        self.recorded_requests: list[dict[str, Any]] = []


class FakeProviderServer:
    """Local server speaking the OpenAI SSE chat completions protocol with controllable latencies."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        clock: Clock | None = None,
        ttft_ms: float = 0.0,
        itl_ms: float = 0.0,
        default_response: str = "Deterministic test response from FakeProviderServer.",
    ) -> None:
        self.host = host
        self.port = port
        self.clock = clock or RealClock()
        self.ttft_ms = ttft_ms
        self.itl_ms = itl_ms
        self.default_response = default_response
        self._response_generator: Callable[[dict[str, Any]], str] = lambda _body: self.default_response

        self._server: _FakeHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def set_response_generator(self, fn: Callable[[dict[str, Any]], str]) -> None:
        self._response_generator = fn
        if self._server:
            self._server.response_generator = fn

    def start(self) -> str:
        self._server = _FakeHTTPServer(
            (self.host, self.port),
            clock=self.clock,
            ttft_ms=self.ttft_ms,
            itl_ms=self.itl_ms,
            response_generator=self._response_generator,
        )
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.base_url

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    @property
    def recorded_requests(self) -> list[dict[str, Any]]:
        return self._server.recorded_requests if self._server else []

    def __enter__(self) -> "FakeProviderServer":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
