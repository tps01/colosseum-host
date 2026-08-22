"""Platform dispatch for local IPv4 interface/network lookup."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class IPv4NetworkBinding:
    """Local IPv4 address and subnet on a named interface."""

    interface: str
    address: str
    network: str
    prefix: int

    def as_dict(self) -> dict[str, str | int]:
        return {
            "interface": self.interface,
            "address": self.address,
            "network": self.network,
            "prefix": self.prefix,
        }


def list_ipv4_network_bindings(*, include_loopback: bool = False) -> list[IPv4NetworkBinding]:
    """Return IPv4 address/subnet bindings for local network interfaces."""
    if sys.platform.startswith("win"):
        from . import windows as platform_module
    elif sys.platform.startswith("linux"):
        from . import linux as platform_module
    else:
        return []
    bindings = platform_module.list_ipv4_network_bindings(include_loopback=include_loopback)
    if include_loopback:
        return bindings
    return [binding for binding in bindings if not binding.address.startswith("127.")]
