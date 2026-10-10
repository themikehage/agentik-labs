from __future__ import annotations

import socket
import pytest

try:
    from pytest_socket import SocketBlockedError
except ImportError:
    SocketBlockedError = OSError  # type: ignore


def test_network_isolation_blocks_external_connection() -> None:
    """
    Verification Plan requirement:
    Asserts that any attempt to open an external network socket fails under pytest-socket isolation.
    """
    with pytest.raises((SocketBlockedError, OSError)):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
