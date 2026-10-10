"""
Reference implementation for Curso 2 M6 - Hardening, Anti-SSRF y Cadena de Suministro MCP.
Tool pinning SHA-256 verification, anti-SSRF policy engine, prompt injection mitigation, and sandbox enforcement.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from urllib.parse import urlparse
from typing import Any

from labkit.sandbox import validate_hardened_flags, HardenedSandbox


class SecurityViolationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ToolPoisoningDetectedError(SecurityViolationError):
    def __init__(self, tool_name: str, expected_hash: str, actual_hash: str) -> None:
        super().__init__(
            code="TOOL_POISONING_DETECTED",
            message=f"Rug-pull detected on tool '{tool_name}': expected hash {expected_hash}, got {actual_hash}",
        )
        self.tool_name = tool_name
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


class SsrfBlockedError(SecurityViolationError):
    def __init__(self, target_url: str, reason: str) -> None:
        super().__init__(code="SSRF_BLOCKED", message=f"URL '{target_url}' blocked by Anti-SSRF policy: {reason}")
        self.target_url = target_url
        self.reason = reason


def compute_tool_hash(tool_def: dict[str, Any]) -> str:
    # Deterministic canonical serialization
    canonical = json.dumps(
        {
            "name": tool_def.get("name"),
            "description": tool_def.get("description"),
            "inputSchema": tool_def.get("inputSchema"),
            "outputSchema": tool_def.get("outputSchema"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ToolPolicyEngine:
    def __init__(self) -> None:
        self._pinned_hashes: dict[str, str] = {}

    def pin_tool(self, name: str, expected_hash: str) -> None:
        self._pinned_hashes[name] = expected_hash

    def verify_tool(self, tool_def: dict[str, Any]) -> bool:
        name = tool_def.get("name")
        if not name or name not in self._pinned_hashes:
            raise SecurityViolationError("UNPINNED_TOOL", f"Tool '{name}' is not in pinned policy store")

        actual_hash = compute_tool_hash(tool_def)
        expected = self._pinned_hashes[name]

        if actual_hash != expected:
            raise ToolPoisoningDetectedError(name, expected, actual_hash)

        return True


class AntiSsrfValidator:
    def __init__(self, allowlist_domains: list[str] | None = None) -> None:
        self.allowlist_domains = [d.lower() for d in (allowlist_domains or [])]

    def validate_url(self, target_url: str) -> bool:
        try:
            parsed = urlparse(target_url)
        except Exception:
            raise SsrfBlockedError(target_url, "Malformed URL")

        if parsed.scheme not in ("http", "https"):
            raise SsrfBlockedError(target_url, f"Forbidden URI scheme '{parsed.scheme}'")

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise SsrfBlockedError(target_url, "Missing host in URL")

        # Check localhost / loopback
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            raise SsrfBlockedError(target_url, "Loopback / Localhost addresses are strictly prohibited")

        # Check IP address targets
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if str(ip_obj) == "169.254.169.254":
                raise SsrfBlockedError(target_url, "Cloud instance metadata service address 169.254.169.254 is prohibited")
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
                raise SsrfBlockedError(target_url, f"Private / Link-local IP address {hostname} is prohibited")
        except ValueError:
            # Hostname is a domain name, check internal domains
            if hostname.endswith(".internal") or hostname.endswith(".local") or hostname.endswith(".corp"):
                raise SsrfBlockedError(target_url, f"Internal domain name '{hostname}' is prohibited")

        if self.allowlist_domains:
            if not any(hostname == d or hostname.endswith("." + d) for d in self.allowlist_domains):
                raise SsrfBlockedError(target_url, f"Host '{hostname}' is not in domain allowlist")

        return True


class PromptSanitizer:
    OVERRIDE_PATTERNS = [
        re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
        re.compile(r"<\|im_start\|>", re.IGNORECASE),
        re.compile(r"<\|im_end\|>", re.IGNORECASE),
    ]

    @classmethod
    def sanitize_untrusted_output(cls, raw_text: str) -> str:
        cleaned = raw_text
        for pattern in cls.OVERRIDE_PATTERNS:
            cleaned = pattern.sub("[FILTERED_INSTRUCTION_OVERRIDE]", cleaned)

        # Encapsulate safely inside structured data boundary tags
        return f"<untrusted_tool_output>\n{cleaned.strip()}\n</untrusted_tool_output>"


def execute_sandboxed_command(command: list[str]) -> bool:
    """
    Validates hardened container flags using labkit sandbox utilities.
    """
    try:
        return validate_hardened_flags(command)
    except Exception:
        return False
