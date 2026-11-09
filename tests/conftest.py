"""Offline tests fail closed on accidental real network connections."""

import socket

import pytest


@pytest.fixture(autouse=True)
def offline_network_boundary(request, monkeypatch):
    if any(request.node.get_closest_marker(mark) for mark in ("postgres", "external", "live_llm")):
        return

    original_connect = socket.socket.connect

    def guarded_connect(sock, address):
        # Windows asyncio implements its internal socketpair over loopback TCP.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        raise AssertionError(
            "Network forbidden in offline tests; mark external/postgres/live_llm explicitly"
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
