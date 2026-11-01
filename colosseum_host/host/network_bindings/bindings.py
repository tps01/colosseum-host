"""Platform dispatch for local IPv4 interface/network lookup."""

from __future__ import annotations

import ipaddress
import sys
from dataclasses import dataclass

from colosseum_host.host.network import list_adapters


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
    if not (sys.platform.startswith("win") or sys.platform.startswith("linux")):
        return []
    bindings: list[IPv4NetworkBinding] = []
    for adapter in list_adapters(include_loopback=True):
        for endpoint in adapter.ipv4:
            if endpoint.prefix is None:
                continue
            try:
                iface = ipaddress.IPv4Interface(f"{endpoint.address}/{endpoint.prefix}")
            except ValueError:
                continue
            bindings.append(
                IPv4NetworkBinding(
                    interface=adapter.name,
                    address=str(iface.ip),
                    network=str(iface.network.network_address),
                    prefix=iface.network.prefixlen,
                ),
            )
    if include_loopback:
        return bindings
    return [binding for binding in bindings if not binding.address.startswith("127.")]
