from __future__ import annotations

import json
import pytest
import httpx
from labkit.fake_provider import FakeProviderServer


@pytest.mark.enable_socket
def test_fake_provider_health_and_models() -> None:
    with FakeProviderServer() as server:
        with httpx.Client(base_url=server.base_url, timeout=2.0) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

            resp_models = client.get("/models")
            assert resp_models.status_code == 200
            assert "data" in resp_models.json()


@pytest.mark.enable_socket
def test_fake_provider_non_streaming_chat_completion() -> None:
    with FakeProviderServer(default_response="Simulated non-streaming completion.") as server:
        with httpx.Client(base_url=server.base_url, timeout=2.0) as client:
            payload = {
                "model": "gpt-4o-mock",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            }
            resp = client.post("/chat/completions", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["choices"][0]["message"]["content"] == "Simulated non-streaming completion."
            assert data["usage"]["total_tokens"] > 0


@pytest.mark.enable_socket
def test_fake_provider_streaming_sse() -> None:
    with FakeProviderServer(default_response="Token1 Token2 Token3") as server:
        with httpx.Client(base_url=server.base_url, timeout=2.0) as client:
            payload = {
                "model": "gpt-4o-mock",
                "messages": [{"role": "user", "content": "Stream me tokens"}],
                "stream": True,
            }
            with client.stream("POST", "/chat/completions", json=payload) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers.get("content-type", "")

                received_chunks = []
                for line in response.iter_lines():
                    if line.strip() == "data: [DONE]":
                        break
                    if line.startswith("data: "):
                        raw_json = line[len("data: "):]
                        data = json.loads(raw_json)
                        delta = data["choices"][0]["delta"].get("content", "")
                        if delta:
                            received_chunks.append(delta)

                assembled = "".join(received_chunks)
                assert assembled.strip() == "Token1 Token2 Token3"
