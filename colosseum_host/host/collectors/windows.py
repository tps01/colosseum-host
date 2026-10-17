"""Windows host collectors (ctypes, pyserial)."""

from __future__ import annotations

import ctypes
import platform
from ctypes import wintypes
from typing import Any

from colosseum_host.exceptions import HostCapabilityError
from colosseum_host.host.network import list_adapters
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


def _linux_only(feature: str) -> HostCapabilityError:
    return HostCapabilityError(
        f"{feature} is only available on Linux "
        "(see README Linux-first capability table)",
    )


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


def list_network_interfaces(*, include_loopback: bool = False) -> list[NetworkInterface]:
    return [
        NetworkInterface(
            name=adapter.name,
            mac=adapter.mac,
            ipv4=[ep.address for ep in adapter.ipv4],
            ipv6=list(adapter.ipv6),
            operstate=adapter.operstate,
            mtu=adapter.mtu,
        )
        for adapter in list_adapters(include_loopback=include_loopback)
    ]


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
