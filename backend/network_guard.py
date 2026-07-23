from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import Callable


class NetworkAccessBlocked(RuntimeError):
    """Raised immediately when a hermetic gate attempts external networking."""


_INSTALLED = False
_original_getaddrinfo = socket.getaddrinfo
_original_create_connection = socket.create_connection
_original_connect = socket.socket.connect


def _is_loopback(host: object) -> bool:
    if host in {None, "", "localhost"}:
        return True
    try:
        return ipaddress.ip_address(str(host)).is_loopback
    except ValueError:
        return False


def install_network_sentinel(*, allow_loopback: bool = False) -> Callable[[], None]:
    """Block DNS and outbound sockets; optionally preserve local smoke-test traffic."""
    global _INSTALLED
    if _INSTALLED:
        return uninstall_network_sentinel

    def guarded_getaddrinfo(host, *args, **kwargs):
        if allow_loopback and _is_loopback(host):
            return _original_getaddrinfo(host, *args, **kwargs)
        raise NetworkAccessBlocked(f"network sentinel blocked DNS lookup for {host!r}")

    def guarded_create_connection(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if allow_loopback and _is_loopback(host):
            return _original_create_connection(address, *args, **kwargs)
        raise NetworkAccessBlocked(f"network sentinel blocked connection to {host!r}")

    def guarded_connect(sock, address):
        if isinstance(address, str):  # Unix-domain sockets are local IPC.
            return _original_connect(sock, address)
        host = address[0] if isinstance(address, tuple) and address else address
        if allow_loopback and _is_loopback(host):
            return _original_connect(sock, address)
        raise NetworkAccessBlocked(f"network sentinel blocked socket connection to {host!r}")

    socket.getaddrinfo = guarded_getaddrinfo
    socket.create_connection = guarded_create_connection
    socket.socket.connect = guarded_connect
    _INSTALLED = True
    return uninstall_network_sentinel


def uninstall_network_sentinel() -> None:
    global _INSTALLED
    socket.getaddrinfo = _original_getaddrinfo
    socket.create_connection = _original_create_connection
    socket.socket.connect = _original_connect
    _INSTALLED = False


def install_from_environment() -> None:
    if os.getenv("STOP_LOSS_NETWORK_SENTINEL") == "1":
        install_network_sentinel(allow_loopback=os.getenv("STOP_LOSS_NETWORK_ALLOW_LOOPBACK") == "1")
