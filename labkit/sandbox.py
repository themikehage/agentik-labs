from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence


class HardeningViolationError(ValueError):
    """Raised when a container execution configuration violates security hardening invariants."""
    pass


REQUIRED_HARDENING_FLAGS: tuple[str, ...] = (
    "--network none",
    "--read-only",
    "--cap-drop ALL",
    "--security-opt no-new-privileges",
)


@dataclass
class SandboxExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    command: list[str]
    dry_run: bool = False


def validate_hardened_flags(args: Sequence[str]) -> bool:
    """Verifies that all mandatory isolation flags are strictly present in the command."""
    joined = " ".join(args)

    for flag in REQUIRED_HARDENING_FLAGS:
        if flag not in joined:
            raise HardeningViolationError(f"Mandatory security hardening flag missing: {flag}")

    # Check resource constraints
    if "--pids-limit" not in joined:
        raise HardeningViolationError("Mandatory resource constraint missing: --pids-limit")
    if "--memory" not in joined:
        raise HardeningViolationError("Mandatory resource constraint missing: --memory")
    if "--user" not in joined:
        raise HardeningViolationError("Mandatory unprivileged user flag missing: --user")

    # Anti-patterns check
    if "--privileged" in joined:
        raise HardeningViolationError("Privileged containers are strictly forbidden: --privileged detected")
    if "--net=host" in joined or "--network host" in joined:
        raise HardeningViolationError("Host network is strictly forbidden in sandbox")

    return True


class HardenedSandbox:
    """Local hardened container launcher for untrusted student code execution."""

    def __init__(
        self,
        runtime: str | None = None,
        pids_limit: int = 64,
        memory: str = "256m",
        user_id: int = 10001,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.runtime = runtime or self._detect_runtime()
        self.pids_limit = pids_limit
        self.memory = memory
        self.user_id = user_id
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _detect_runtime() -> str:
        if shutil.which("docker"):
            return "docker"
        if shutil.which("podman"):
            return "podman"
        return "docker"

    def build_command(
        self,
        command_in_container: Sequence[str],
        image: str = "python:3.12-alpine",
        volumes: Sequence[str] | None = None,
    ) -> list[str]:
        cmd: list[str] = [
            self.runtime,
            "run",
            "--rm",
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.pids_limit),
            "--memory", self.memory,
            "--user", f"{self.user_id}:{self.user_id}",
        ]

        if volumes:
            for v in volumes:
                cmd.extend(["-v", v])

        cmd.append(image)
        cmd.extend(command_in_container)

        validate_hardened_flags(cmd)
        return cmd

    def run(
        self,
        command_in_container: Sequence[str],
        image: str = "python:3.12-alpine",
        volumes: Sequence[str] | None = None,
        dry_run: bool = False,
    ) -> SandboxExecutionResult:
        cmd = self.build_command(command_in_container, image=image, volumes=volumes)

        if dry_run or not shutil.which(self.runtime):
            return SandboxExecutionResult(
                exit_code=0,
                stdout="[dry-run] Container command validated and simulated successfully.",
                stderr="",
                command=cmd,
                dry_run=True,
            )

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            return SandboxExecutionResult(
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                command=cmd,
                dry_run=False,
            )
        except subprocess.TimeoutExpired as e:
            return SandboxExecutionResult(
                exit_code=124,
                stdout="",
                stderr=f"Execution timed out after {self.timeout_seconds}s",
                command=cmd,
                dry_run=False,
            )
