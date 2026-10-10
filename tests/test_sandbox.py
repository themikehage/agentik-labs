from __future__ import annotations

import pytest
from labkit.sandbox import (
    HardenedSandbox,
    HardeningViolationError,
    validate_hardened_flags,
)


def test_validate_hardened_flags_valid_command() -> None:
    valid_cmd = [
        "docker", "run",
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "64",
        "--memory", "256m",
        "--user", "10001:10001",
        "alpine:latest", "echo", "ok",
    ]
    assert validate_hardened_flags(valid_cmd) is True


def test_validate_hardened_flags_rejects_missing_network_none() -> None:
    insecure_cmd = [
        "docker", "run",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "64",
        "--memory", "256m",
        "--user", "10001:10001",
        "alpine:latest",
    ]
    with pytest.raises(HardeningViolationError, match="--network none"):
        validate_hardened_flags(insecure_cmd)


def test_validate_hardened_flags_rejects_privileged() -> None:
    insecure_cmd = [
        "docker", "run",
        "--privileged",
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "64",
        "--memory", "256m",
        "--user", "10001:10001",
        "alpine:latest",
    ]
    with pytest.raises(HardeningViolationError, match="Privileged containers are strictly forbidden"):
        validate_hardened_flags(insecure_cmd)


def test_hardened_sandbox_dry_run() -> None:
    sandbox = HardenedSandbox(pids_limit=32, memory="128m")
    result = sandbox.run(["echo", "hello"], dry_run=True)
    assert result.exit_code == 0
    assert result.dry_run is True
    assert "--pids-limit 32" in " ".join(result.command)
    assert "--memory 128m" in " ".join(result.command)
