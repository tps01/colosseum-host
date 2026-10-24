"""Shared network adapter snapshots used by collectors and bindings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IPv4Endpoint:
    """IPv4 address with CIDR prefix length.

    ``prefix`` is ``None`` when the platform did not provide a usable length.
    Callers must not substitute a subnet for that missing value.
    """

    address: str
    prefix: int | None


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
