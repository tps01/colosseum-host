"""Unit tests for IPv4 binding helpers."""

from __future__ import annotations

from unittest.mock import patch

from colosseum_host.host.network.types import AdapterSnapshot, IPv4Endpoint
from colosseum_host.host.network_bindings import IPv4NetworkBinding
from colosseum_host.host.network_bindings import windows as win_bindings


def test_binding_as_dict() -> None:
    binding = IPv4NetworkBinding("eth0", "192.168.1.10", "192.168.1.0", 24)
    assert binding.as_dict() == {
        "interface": "eth0",
        "address": "192.168.1.10",
        "network": "192.168.1.0",
        "prefix": 24,
    }


def test_windows_binding_keeps_prefix_zero_and_skips_missing_prefix() -> None:
    adapters = [
        AdapterSnapshot(
            name="eth0",
            mac=None,
            ipv4=(
                IPv4Endpoint("10.1.2.3", 0),
                IPv4Endpoint("10.9.9.9", None),
                IPv4Endpoint("192.168.1.10", 24),
            ),
            ipv6=(),
            operstate="up",
            mtu=1500,
            is_loopback=False,
        ),
    ]
    with patch.object(win_bindings, "list_adapters", return_value=adapters):
        bindings = win_bindings.list_ipv4_network_bindings()
    assert [(item.address, item.network, item.prefix) for item in bindings] == [
        ("10.1.2.3", "0.0.0.0", 0),
        ("192.168.1.10", "192.168.1.0", 24),
    ]
