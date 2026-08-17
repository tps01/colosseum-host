"""Assemble host profile JSON snapshot."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import colosseum

from .collectors import (
    common,
    list_network_interfaces,
    meminfo,
    memory_available_mb,
    serial_ports_csv,
    uname_string,
    uptime_s,
)


def _visa_backend() -> str | None:
    try:
        import pyvisa

        rm = pyvisa.ResourceManager()
        return str(rm.visalib)
    except Exception:
        return None


def _network_summary() -> list[dict[str, Any]]:
    try:
        return [
            {
                "name": iface.name,
                "mac": iface.mac,
                "ipv4": list(iface.ipv4 or []),
                "ipv6": list(iface.ipv6 or []),
                "operstate": iface.operstate,
                "mtu": iface.mtu,
            }
            for iface in list_network_interfaces(include_loopback=False)
        ]
    except (OSError, TypeError, ValueError, AttributeError):
        return []


def collect_profile(*, disk_path: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        memory = meminfo().as_dict()
    except OSError:
        memory = {"available_mb": memory_available_mb()}
    try:
        kernel = uname_string()
    except OSError:
        kernel = None
    profile: dict[str, Any] = {
        "colosseum_version": colosseum.__version__,
        "python_version": common.python_version(),
        "platform": common.platform_name(),
        "machine": common.machine(),
        "hostname": common.hostname(),
        "cpu_count": common.cpu_count(),
        "cpu_model": common.cpu_model(),
        "kernel": kernel,
        "memory_available_mb": memory.get("available_mb", memory_available_mb()),
        "memory": memory,
        "disk_free_gb": common.disk_free_gb(disk_path),
        "uptime_s": uptime_s(),
        "network_interfaces": _network_summary(),
        "visa_backend": _visa_backend(),
        "serial_ports": serial_ports_csv(),
        "bench_config_env": common.bench_config_env(),
        "bench_config_path": None,
    }
    from colosseum.context import get_context

    ctx = get_context()
    if ctx is not None and ctx.config_path is not None:
        profile["bench_config_path"] = str(ctx.config_path)
    profile["collection_duration_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
    return profile


def write_profile(path: str, *, disk_path: str | None = None) -> str:
    data = collect_profile(disk_path=disk_path)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path
