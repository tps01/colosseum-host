"""Linux adapter enumeration via sysfs + ioctl (single path)."""

from __future__ import annotations

import ipaddress
import socket
import struct
from pathlib import Path
from typing import Any

from .types import AdapterSnapshot, IPv4Endpoint

_fcntl_mod: Any = None
try:
    import fcntl

    _fcntl_mod = fcntl
except ModuleNotFoundError:
    pass

SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891B


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_sys_int(path: Path) -> int | None:
    try:
        return int(_read_text(path).strip())
    except (OSError, ValueError):
        return None


def _read_sys_str(path: Path) -> str | None:
    try:
        return _read_text(path).strip()
    except OSError:
        return None


def ioctl_ipv4(name: str, request: int) -> str:
    if _fcntl_mod is None:
        raise OSError("fcntl is not available on this platform")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ifreq = struct.pack("256s", name[:15].encode())
        result = _fcntl_mod.ioctl(sock.fileno(), request, ifreq)
        return socket.inet_ntoa(result[20:24])
    finally:
        sock.close()


def iface_names() -> list[str]:
    net = Path("/sys/class/net")
    if net.is_dir():
        return sorted(p.name for p in net.iterdir() if p.is_dir())
    try:
        return [name for _idx, name in socket.if_nameindex()]
    except OSError:
        return []


def iface_ipv4_endpoints(iface: str) -> tuple[IPv4Endpoint, ...]:
    try:
        address = ioctl_ipv4(iface, SIOCGIFADDR)
        netmask = ioctl_ipv4(iface, SIOCGIFNETMASK)
    except OSError:
        return ()
    try:
        iface_obj = ipaddress.IPv4Interface(f"{address}/{netmask}")
    except ValueError:
        return ()
    return (IPv4Endpoint(address=str(iface_obj.ip), prefix=iface_obj.network.prefixlen),)


def iface_ipv6(iface: str) -> tuple[str, ...]:
    path = Path("/proc/net/if_inet6")
    if not path.is_file():
        return ()
    addrs: list[str] = []
    try:
        text = _read_text(path)
    except OSError:
        return ()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 6 or parts[5] != iface:
            continue
        raw = parts[0]
        try:
            packed = bytes.fromhex(raw)
            addrs.append(socket.inet_ntop(socket.AF_INET6, packed))
        except (OSError, ValueError):
            continue
    return tuple(addrs)


def list_adapters(*, include_loopback: bool = False) -> list[AdapterSnapshot]:
    adapters: list[AdapterSnapshot] = []
    for name in iface_names():
        is_loopback = name == "lo"
        if is_loopback and not include_loopback:
            continue
        base = Path(f"/sys/class/net/{name}")
        if not base.is_dir():
            continue
        adapters.append(
            AdapterSnapshot(
                name=name,
                mac=_read_sys_str(base / "address"),
                ipv4=iface_ipv4_endpoints(name),
                ipv6=iface_ipv6(name),
                operstate=_read_sys_str(base / "operstate"),
                mtu=_read_sys_int(base / "mtu"),
                is_loopback=is_loopback,
            ),
        )
    return adapters
