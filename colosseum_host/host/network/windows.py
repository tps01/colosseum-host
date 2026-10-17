"""Windows adapter enumeration via GetAdaptersAddresses (single path)."""

from __future__ import annotations

import contextlib
import ctypes
import socket
from ctypes import wintypes
from typing import Any

from .types import AdapterSnapshot, IPv4Endpoint


def _iphlpapi() -> Any:  # noqa: ANN401
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        raise OSError("Windows API unavailable")
    return windll.iphlpapi


class _IP_ADAPTER_ADDRESSES(ctypes.Structure):
    pass


_IP_ADAPTER_ADDRESSES._fields_ = [
    ("Length", wintypes.ULONG),
    ("IfIndex", wintypes.DWORD),
    ("Next", ctypes.POINTER(_IP_ADAPTER_ADDRESSES)),
    ("AdapterName", ctypes.c_char_p),
    ("FirstUnicastAddress", ctypes.c_void_p),
    ("FirstAnycastAddress", ctypes.c_void_p),
    ("FirstMulticastAddress", ctypes.c_void_p),
    ("FirstDnsServerAddress", ctypes.c_void_p),
    ("DnsSuffix", wintypes.LPWSTR),
    ("Description", wintypes.LPWSTR),
    ("FriendlyName", wintypes.LPWSTR),
    ("PhysicalAddress", wintypes.BYTE * 8),
    ("PhysicalAddressLength", wintypes.DWORD),
    ("Flags", wintypes.DWORD),
    ("Mtu", wintypes.DWORD),
    ("IfType", wintypes.DWORD),
    ("OperStatus", wintypes.DWORD),
    ("Ipv6IfIndex", wintypes.DWORD),
    ("ZoneIndices", wintypes.DWORD * 16),
    ("FirstPrefix", ctypes.c_void_p),
]


class _SOCKET_ADDRESS(ctypes.Structure):
    _fields_ = [
        ("lpSockaddr", ctypes.c_void_p),
        ("iSockaddrLength", ctypes.c_int),
    ]


class _IP_ADAPTER_UNICAST_ADDRESS(ctypes.Structure):
    pass


_IP_ADAPTER_UNICAST_ADDRESS._fields_ = [
    ("Length", wintypes.ULONG),
    ("Flags", wintypes.DWORD),
    ("Next", ctypes.POINTER(_IP_ADAPTER_UNICAST_ADDRESS)),
    ("Address", _SOCKET_ADDRESS),
    ("PrefixOrigin", ctypes.c_int),
    ("SuffixOrigin", ctypes.c_int),
    ("DadState", ctypes.c_int),
    ("ValidLifetime", wintypes.ULONG),
    ("PreferredLifetime", wintypes.ULONG),
    ("LeaseLifetime", wintypes.ULONG),
    ("OnLinkPrefixLength", ctypes.c_ubyte),
]


_IF_OPER_STATUS = {
    1: "up",
    2: "down",
    3: "testing",
    4: "unknown",
    5: "dormant",
    6: "notPresent",
    7: "lowerLayerDown",
}


def _format_mac(raw: bytes, length: int) -> str | None:
    if length <= 0:
        return None
    return ":".join(f"{b:02x}" for b in raw[:length])


def _adapter_name(adapter: _IP_ADAPTER_ADDRESSES) -> str:
    name = adapter.FriendlyName or adapter.Description or adapter.AdapterName or ""
    if isinstance(name, bytes):
        return name.decode("utf-8", errors="replace")
    return str(name)


def list_adapters(*, include_loopback: bool = False) -> list[AdapterSnapshot]:
    """Enumerate adapters once; both collectors and bindings project from this."""
    adapters: list[AdapterSnapshot] = []
    try:
        size = wintypes.ULONG(15000)
        buffer = ctypes.create_string_buffer(size.value)
        flags = 0
        family = socket.AF_UNSPEC
        result = _iphlpapi().GetAdaptersAddresses(
            family,
            flags,
            None,
            ctypes.byref(_IP_ADAPTER_ADDRESSES.from_buffer(buffer)),
            ctypes.byref(size),
        )
        if result == 111:
            buffer = ctypes.create_string_buffer(size.value)
            result = _iphlpapi().GetAdaptersAddresses(
                family,
                flags,
                None,
                ctypes.byref(_IP_ADAPTER_ADDRESSES.from_buffer(buffer)),
                ctypes.byref(size),
            )
        if result != 0:
            return adapters

        adapter = _IP_ADAPTER_ADDRESSES.from_buffer(buffer)
        while True:
            is_loopback = adapter.IfType == 24
            if is_loopback and not include_loopback:
                next_adapter = adapter.Next
                if not next_adapter:
                    break
                adapter = next_adapter.contents
                continue

            ipv4: list[IPv4Endpoint] = []
            ipv6: list[str] = []
            unicast_ptr = adapter.FirstUnicastAddress
            while unicast_ptr:
                addr_addr = int(unicast_ptr) if not isinstance(unicast_ptr, int) else unicast_ptr
                try:
                    addr_struct = _IP_ADAPTER_UNICAST_ADDRESS.from_address(addr_addr)
                except TypeError:
                    break
                sa = addr_struct.Address
                if sa.iSockaddrLength >= 16 and sa.lpSockaddr:
                    sockaddr = (ctypes.c_ubyte * sa.iSockaddrLength).from_address(
                        int(sa.lpSockaddr),
                    )
                    family_value = int.from_bytes(sockaddr[0:2], "little")
                    if family_value == socket.AF_INET and sa.iSockaddrLength >= 16:
                        address = socket.inet_ntoa(bytes(sockaddr[4:8]))
                        prefix = int(addr_struct.OnLinkPrefixLength)
                        if prefix == 0:
                            prefix = 24
                        ipv4.append(IPv4Endpoint(address=address, prefix=prefix))
                    elif family_value == socket.AF_INET6 and sa.iSockaddrLength >= 28:
                        with contextlib.suppress(OSError):
                            ipv6.append(socket.inet_ntop(socket.AF_INET6, bytes(sockaddr[8:24])))
                next_unicast = addr_struct.Next
                unicast_ptr = int(next_unicast) if next_unicast else 0

            adapters.append(
                AdapterSnapshot(
                    name=_adapter_name(adapter),
                    mac=_format_mac(
                        bytes(adapter.PhysicalAddress),
                        int(adapter.PhysicalAddressLength),
                    ),
                    ipv4=tuple(ipv4),
                    ipv6=tuple(ipv6),
                    operstate=_IF_OPER_STATUS.get(int(adapter.OperStatus)),
                    mtu=int(adapter.Mtu) if adapter.Mtu else None,
                    is_loopback=is_loopback,
                ),
            )
            next_adapter = adapter.Next
            if not next_adapter:
                break
            adapter = next_adapter.contents
    except (AttributeError, OSError, ValueError, TypeError):
        return adapters
    return adapters
