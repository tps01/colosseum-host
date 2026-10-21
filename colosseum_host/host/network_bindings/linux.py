"""Linux IPv4 binding projection from shared network primitives."""

from __future__ import annotations

import ipaddress

from colosseum_host.host.network import list_adapters

from .bindings import IPv4NetworkBinding


def list_ipv4_network_bindings(*, include_loopback: bool = False) -> list[IPv4NetworkBinding]:
    bindings: list[IPv4NetworkBinding] = []
    for adapter in list_adapters(include_loopback=include_loopback):
        for endpoint in adapter.ipv4:
            if endpoint.prefix is None:
                continue
            try:
                network = ipaddress.IPv4Network(
                    f"{endpoint.address}/{endpoint.prefix}",
                    strict=False,
                )
            except ValueError:
                continue
            bindings.append(
                IPv4NetworkBinding(
                    interface=adapter.name,
                    address=endpoint.address,
                    network=str(network.network_address),
                    prefix=endpoint.prefix,
                ),
            )
    return bindings
