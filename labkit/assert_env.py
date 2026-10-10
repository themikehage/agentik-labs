from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable
import httpx


class EnvironmentAssertionError(AssertionError):
    """Raised when an environment outcome expectation fails."""
    pass


def assert_fs_matches(base_path: Path | str, schema: dict[str, Any]) -> None:
    """
    Asserts filesystem state against a declarative outcome schema.

    Schema structure example:
    {
        "config.json": {"required": True, "json_keys": ["version", "port"]},
        "output.txt": {"required": True, "contains": "SUCCESS"},
        "logs/": {"required": True, "is_dir": True},
    }
    """
    root = Path(base_path)
    if not root.exists():
        raise EnvironmentAssertionError(f"Root directory does not exist: {root}")

    for rel_path, spec in schema.items():
        target = root / rel_path
        required = spec.get("required", True)

        if not target.exists():
            if required:
                raise EnvironmentAssertionError(f"Expected path does not exist: {rel_path} (in {root})")
            continue

        if spec.get("is_dir", False):
            if not target.is_dir():
                raise EnvironmentAssertionError(f"Expected directory at {rel_path}, but found file.")
            continue

        if not target.is_file():
            raise EnvironmentAssertionError(f"Expected file at {rel_path}, but found directory.")

        min_size = spec.get("min_size_bytes")
        if min_size is not None and target.stat().st_size < min_size:
            raise EnvironmentAssertionError(
                f"File {rel_path} size {target.stat().st_size}B is smaller than expected minimum {min_size}B."
            )

        sha256_expected = spec.get("sha256")
        if sha256_expected:
            actual_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual_sha != sha256_expected:
                raise EnvironmentAssertionError(
                    f"SHA-256 mismatch for {rel_path}: expected {sha256_expected}, got {actual_sha}"
                )

        contains = spec.get("contains")
        if contains:
            text = target.read_text(encoding="utf-8")
            if contains not in text:
                raise EnvironmentAssertionError(f"File {rel_path} does not contain expected substring: {contains!r}")

        json_keys = spec.get("json_keys")
        if json_keys:
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
            except Exception as e:
                raise EnvironmentAssertionError(f"File {rel_path} is not valid JSON: {e}")
            for k in json_keys:
                if k not in data:
                    raise EnvironmentAssertionError(f"File {rel_path} JSON missing required key: {k!r}")


def assert_db_matches(
    query_fn: Callable[[], Any],
    predicate: Callable[[Any], bool],
    error_message: str = "Database outcome condition not met.",
) -> None:
    """Evaluates a database query function and asserts predicate condition."""
    result = query_fn()
    if not predicate(result):
        raise EnvironmentAssertionError(f"{error_message} (query result: {result!r})")


def assert_http_endpoint(
    url: str,
    expected_status: int = 200,
    expected_json_subset: dict[str, Any] | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    """Asserts that a local HTTP endpoint is healthy and fulfills contract without external network."""
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
    except Exception as e:
        raise EnvironmentAssertionError(f"Failed to connect to local endpoint {url}: {e}")

    if resp.status_code != expected_status:
        raise EnvironmentAssertionError(
            f"Expected status {expected_status} from {url}, got {resp.status_code}. Body: {resp.text[:200]}"
        )

    data: dict[str, Any] = {}
    if expected_json_subset is not None:
        try:
            data = resp.json()
        except Exception as e:
            raise EnvironmentAssertionError(f"Response from {url} is not valid JSON: {e}")

        for k, v in expected_json_subset.items():
            if k not in data or data[k] != v:
                raise EnvironmentAssertionError(
                    f"Key {k!r} mismatch in {url}: expected {v!r}, got {data.get(k)!r}"
                )
    return data
