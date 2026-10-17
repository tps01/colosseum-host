"""Shared network adapter snapshots used by collectors and bindings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IPv4Endpoint:
    """IPv4 address with CIDR prefix length."""

    address: str
    prefix: int


@dataclass(frozen=True)
class AdapterSnapshot:
    """Platform-neutral adapter identity and addresses."""

    name: str
    mac: str | None
    ipv4: tuple[IPv4Endpoint, ...]
    ipv6: tuple[str, ...]
    operstate: str | None
    mtu: int | None
    is_loopback: bool
