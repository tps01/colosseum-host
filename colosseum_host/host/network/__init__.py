"""Shared platform network primitives for collectors and bindings."""

from __future__ import annotations

import sys

from .types import AdapterSnapshot, IPv4Endpoint

if sys.platform.startswith("win"):
    from . import windows as _platform
elif sys.platform.startswith("linux"):
    from . import linux as _platform
else:
    _platform = None


def list_adapters(*, include_loopback: bool = False) -> list[AdapterSnapshot]:
    if _platform is None:
        return []
    return list(_platform.list_adapters(include_loopback=include_loopback))


__all__ = [
    "AdapterSnapshot",
    "IPv4Endpoint",
    "list_adapters",
]
