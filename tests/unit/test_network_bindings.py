"""Unit tests for IPv4 binding helpers."""

from __future__ import annotations

from colosseum_host.host.network_bindings import IPv4NetworkBinding


def test_binding_as_dict() -> None:
    binding = IPv4NetworkBinding("eth0", "192.168.1.10", "192.168.1.0", 24)
    assert binding.as_dict() == {
        "interface": "eth0",
        "address": "192.168.1.10",
        "network": "192.168.1.0",
        "prefix": 24,
    }
