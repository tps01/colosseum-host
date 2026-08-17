"""Windows host collectors (ctypes, pyserial)."""

from __future__ import annotations

import contextlib
import ctypes
import platform
import socket
from ctypes import wintypes
from typing import Any

from serial.tools import list_ports

from .types import (
    CpuUtilization,
    DiskRates,
    LoadAverage,
    MemInfo,
    NetRates,
    NetworkInterface,
    ProcessInfo,
    VmStat,
)


def _kernel32() -> Any:  # noqa: ANN401
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        raise OSError("Windows API unavailable")
    return windll.kernel32


def _iphlpapi() -> Any:  # noqa: ANN401
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        raise OSError("Windows API unavailable")
    return windll.iphlpapi


def _linux_only(feature: str) -> OSError:
    return OSError(f"{feature} is only available on Linux")


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def memory_available_mb() -> float:
    return meminfo().available_mb


def meminfo() -> MemInfo:
    stat = _MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    if not _kernel32().GlobalMemoryStatusEx(ctypes.byref(stat)):
        raise OSError("GlobalMemoryStatusEx failed")
    total_mb = float(stat.ullTotalPhys) / (1024**2)
    available_mb = float(stat.ullAvailPhys) / (1024**2)
    # Page file figures approximate swap capacity on Windows.
    swap_total_mb = max(0.0, float(stat.ullTotalPageFile - stat.ullTotalPhys) / (1024**2))
    swap_free_mb = max(0.0, float(stat.ullAvailPageFile - stat.ullAvailPhys) / (1024**2))
    return MemInfo(
        total_mb=total_mb,
        available_mb=available_mb,
        swap_total_mb=swap_total_mb,
        swap_free_mb=swap_free_mb,
    )


def uptime_s() -> float:
    return float(_kernel32().GetTickCount64()) / 1000.0


def serial_ports_csv() -> str:
    names = sorted(
        port.device for port in list_ports.comports() if port.device.upper().startswith("COM")
    )
    return ",".join(names)


def uname_release() -> str:
    return platform.version()


def uname_string() -> str:
    return f"{platform.system()} {platform.release()} {platform.version()} {platform.machine()}"


def loadavg() -> LoadAverage:
    raise _linux_only("loadavg")


def thermal_temp_c(zone: int = 0) -> float:
    _ = zone
    raise _linux_only("thermal_temp_c")


def list_thermal_zones() -> list[int]:
    return []


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


def list_network_interfaces(*, include_loopback: bool = False) -> list[NetworkInterface]:
    interfaces: dict[str, NetworkInterface] = {}
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
            return []

        adapter = _IP_ADAPTER_ADDRESSES.from_buffer(buffer)
        while True:
            name = adapter.FriendlyName or adapter.Description or adapter.AdapterName or ""
            if isinstance(name, bytes):
                interface = name.decode("utf-8", errors="replace")
            else:
                interface = str(name)
            is_loopback = adapter.IfType == 24
            if is_loopback and not include_loopback:
                next_adapter = adapter.Next
                if not next_adapter:
                    break
                adapter = next_adapter.contents
                continue
            mac = _format_mac(bytes(adapter.PhysicalAddress), int(adapter.PhysicalAddressLength))
            ipv4: list[str] = []
            ipv6: list[str] = []
            unicast_ptr = adapter.FirstUnicastAddress
            while unicast_ptr:
                addr_addr = (
                    int(unicast_ptr)
                    if not isinstance(unicast_ptr, int)
                    else unicast_ptr
                )
                try:
                    addr_struct = _IP_ADAPTER_UNICAST_ADDRESS.from_address(addr_addr)
                except TypeError:
                    break
                sa = addr_struct.Address
                if sa.iSockaddrLength >= 16 and sa.lpSockaddr:
                    sockaddr = (ctypes.c_ubyte * sa.iSockaddrLength).from_address(
                        int(sa.lpSockaddr)
                    )
                    family_value = int.from_bytes(sockaddr[0:2], "little")
                    if family_value == socket.AF_INET and sa.iSockaddrLength >= 16:
                        ipv4.append(socket.inet_ntoa(bytes(sockaddr[4:8])))
                    elif family_value == socket.AF_INET6 and sa.iSockaddrLength >= 28:
                        with contextlib.suppress(OSError):
                            ipv6.append(socket.inet_ntop(socket.AF_INET6, bytes(sockaddr[8:24])))
                next_unicast = addr_struct.Next
                unicast_ptr = int(next_unicast) if next_unicast else 0
            interfaces[interface] = NetworkInterface(
                name=interface,
                mac=mac,
                ipv4=ipv4,
                ipv6=ipv6,
                operstate=_IF_OPER_STATUS.get(int(adapter.OperStatus)),
                mtu=int(adapter.Mtu) if adapter.Mtu else None,
            )
            next_adapter = adapter.Next
            if not next_adapter:
                break
            adapter = next_adapter.contents
    except (AttributeError, OSError, ValueError, TypeError):
        return list(interfaces.values())
    return list(interfaces.values())


def network_interface(iface: str, *, include_counters: bool = True) -> NetworkInterface:
    _ = include_counters
    for item in list_network_interfaces(include_loopback=True):
        if item.name == iface:
            return item
    raise OSError(f"network interface not found: {iface}")


def process_info(pid: int) -> ProcessInfo:
    _ = pid
    raise _linux_only("process_info")


def find_pids_by_comm(comm: str) -> list[int]:
    _ = comm
    raise _linux_only("find_pids_by_comm")


def cpu_utilization(*, interval_s: float = 0.2) -> CpuUtilization:
    _ = interval_s
    raise _linux_only("cpu_utilization")


def vmstat() -> VmStat:
    raise _linux_only("vmstat")


def disk_rates(*, device: str, interval_s: float = 0.2) -> DiskRates:
    _ = device, interval_s
    raise _linux_only("disk_rates")


def net_rates(*, iface: str, interval_s: float = 0.2) -> NetRates:
    _ = iface, interval_s
    raise _linux_only("net_rates")
