"""Unit tests for IPv4 binding helpers."""

from __future__ import annotations

from colosseum_host.host.network_bindings import (
    IPv4NetworkBinding,
    bindings_for_blacklist_entry,
)


def test_bindings_for_blacklist_entry_by_address() -> None:
    bindings = [
        IPv4NetworkBinding("eth0", "192.168.1.10", "192.168.1.0", 24),
        IPv4NetworkBinding("wlan0", "10.0.0.5", "10.0.0.0", 8),
    ]
    matches = bindings_for_blacklist_entry("192.168.1.10", bindings)
    assert matches == [bindings[0]]


def test_bindings_for_blacklist_entry_by_interface() -> None:
    bindings = [
        IPv4NetworkBinding("eth0", "192.168.1.10", "192.168.1.0", 24),
        IPv4NetworkBinding("eth0", "192.168.1.11", "192.168.1.0", 24),
    ]
    matches = bindings_for_blacklist_entry("eth0", bindings)
    assert matches == bindings


def test_binding_as_dict() -> None:
    binding = IPv4NetworkBinding("eth0", "192.168.1.10", "192.168.1.0", 24)
    assert binding.as_dict() == {
        "interface": "eth0",
        "address": "192.168.1.10",
        "network": "192.168.1.0",
        "prefix": 24,
    }
