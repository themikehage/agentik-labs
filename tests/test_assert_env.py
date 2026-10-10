from __future__ import annotations

import json
from pathlib import Path
import pytest
from labkit.assert_env import (
    assert_fs_matches,
    assert_db_matches,
    assert_http_endpoint,
    EnvironmentAssertionError,
)
from labkit.fake_provider import FakeProviderServer


def test_assert_fs_matches_success(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"version": "1.0", "port": 8080}), encoding="utf-8")

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    schema = {
        "config.json": {"required": True, "json_keys": ["version", "port"], "min_size_bytes": 10},
        "logs": {"required": True, "is_dir": True},
    }
    assert_fs_matches(tmp_path, schema)


def test_assert_fs_matches_missing_file_raises(tmp_path: Path) -> None:
    schema = {"missing.txt": {"required": True}}
    with pytest.raises(EnvironmentAssertionError, match="Expected path does not exist: missing.txt"):
        assert_fs_matches(tmp_path, schema)


def test_assert_db_matches() -> None:
    in_memory_db = {"users": ["alice", "bob"], "active_sessions": 2}

    assert_db_matches(
        query_fn=lambda: in_memory_db["active_sessions"],
        predicate=lambda val: val >= 2,
    )

    with pytest.raises(EnvironmentAssertionError, match="Session threshold not reached"):
        assert_db_matches(
            query_fn=lambda: in_memory_db["active_sessions"],
            predicate=lambda val: val > 10,
            error_message="Session threshold not reached",
        )


@pytest.mark.enable_socket
def test_assert_http_endpoint_success() -> None:
    with FakeProviderServer() as server:
        data = assert_http_endpoint(
            f"{server.base_url}/health",
            expected_status=200,
            expected_json_subset={"status": "ok"},
        )
        assert data["provider"] == "fake-provider"
