"""Platform dispatch for host collectors."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import cast

from . import common
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

if sys.platform.startswith("win"):
    from . import windows as _platform
elif sys.platform.startswith("linux"):
    from . import linux as _platform
else:
    _platform = None


def _require_platform() -> ModuleType:
    if _platform is None:
        raise OSError(f"Unsupported platform for host collection: {sys.platform}")
    return _platform


def memory_available_mb() -> float:
    return cast(float, _require_platform().memory_available_mb())


def meminfo() -> MemInfo:
    return cast(MemInfo, _require_platform().meminfo())


def uptime_s() -> float:
    return cast(float, _require_platform().uptime_s())


def serial_ports_csv() -> str:
    if _platform is None:
        return ""
    return str(_platform.serial_ports_csv())


def uname_release() -> str:
    return cast(str, _require_platform().uname_release())


def uname_string() -> str:
    return cast(str, _require_platform().uname_string())


def loadavg() -> LoadAverage:
    return cast(LoadAverage, _require_platform().loadavg())


def thermal_temp_c(zone: int = 0) -> float:
    return cast(float, _require_platform().thermal_temp_c(zone=zone))


def list_thermal_zones() -> list[int]:
    return cast(list[int], _require_platform().list_thermal_zones())


def list_network_interfaces(*, include_loopback: bool = False) -> list[NetworkInterface]:
    return cast(
        list[NetworkInterface],
        _require_platform().list_network_interfaces(include_loopback=include_loopback),
    )


def network_interface(iface: str, *, include_counters: bool = True) -> NetworkInterface:
    return cast(
        NetworkInterface,
        _require_platform().network_interface(iface, include_counters=include_counters),
    )


def process_info(pid: int) -> ProcessInfo:
    return cast(ProcessInfo, _require_platform().process_info(pid))


def find_pids_by_comm(comm: str) -> list[int]:
    return cast(list[int], _require_platform().find_pids_by_comm(comm))


def cpu_utilization(*, interval_s: float = 0.2) -> CpuUtilization:
    return cast(CpuUtilization, _require_platform().cpu_utilization(interval_s=interval_s))


def vmstat() -> VmStat:
    return cast(VmStat, _require_platform().vmstat())


def disk_rates(*, device: str, interval_s: float = 0.2) -> DiskRates:
    return cast(DiskRates, _require_platform().disk_rates(device=device, interval_s=interval_s))


def net_rates(*, iface: str, interval_s: float = 0.2) -> NetRates:
    return cast(NetRates, _require_platform().net_rates(iface=iface, interval_s=interval_s))


__all__ = [
    "common",
    "memory_available_mb",
    "meminfo",
    "uptime_s",
    "serial_ports_csv",
    "uname_release",
    "uname_string",
    "loadavg",
    "thermal_temp_c",
    "list_thermal_zones",
    "list_network_interfaces",
    "network_interface",
    "process_info",
    "find_pids_by_comm",
    "cpu_utilization",
    "vmstat",
    "disk_rates",
    "net_rates",
    "CpuUtilization",
    "DiskRates",
    "LoadAverage",
    "MemInfo",
    "NetRates",
    "NetworkInterface",
    "ProcessInfo",
    "VmStat",
]
