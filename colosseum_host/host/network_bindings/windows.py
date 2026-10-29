"""Windows IPv4 binding projection from shared network primitives."""

from __future__ import annotations

import ipaddress

from colosseum_host.host.network import list_adapters

from .bindings import IPv4NetworkBinding


def list_ipv4_network_bindings(*, include_loopback: bool = False) -> list[IPv4NetworkBinding]:
    _ = include_loopback  # filtered in bindings.list_ipv4_network_bindings
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
    return bindings
