"""Linux host collectors (/proc, /sys, pyserial)."""

from __future__ import annotations

import platform
import socket
import struct
import time
from pathlib import Path
from typing import Any

from serial.tools import list_ports

from .types import (
    CpuTimes,
    CpuUtilization,
    DiskRates,
    LoadAverage,
    MemInfo,
    NetRates,
    NetworkInterface,
    ProcessInfo,
    VmStat,
)

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


def memory_available_mb() -> float:
    return meminfo().available_mb


def meminfo() -> MemInfo:
    text = _read_text(Path("/proc/meminfo"))
    fields: dict[str, float] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        key = parts[0].rstrip(":")
        try:
            fields[key] = int(parts[1]) / 1024.0
        except ValueError:
            continue
    if "MemTotal" not in fields or "MemAvailable" not in fields:
        raise OSError("MemTotal/MemAvailable not found in /proc/meminfo")
    return MemInfo(
        total_mb=fields["MemTotal"],
        available_mb=fields["MemAvailable"],
        swap_total_mb=fields.get("SwapTotal", 0.0),
        swap_free_mb=fields.get("SwapFree", 0.0),
    )


def uptime_s() -> float:
    uptime = _read_text(Path("/proc/uptime")).split()
    return float(uptime[0])


def serial_ports_csv() -> str:
    names = sorted(port.device for port in list_ports.comports() if "/dev/tty" in port.device)
    return ",".join(names)


def uname_release() -> str:
    return platform.uname().release


def uname_string() -> str:
    u = platform.uname()
    return f"{u.system} {u.release} {u.version} {u.machine}"


def loadavg() -> LoadAverage:
    text = _read_text(Path("/proc/loadavg")).split()
    return LoadAverage(load1=float(text[0]), load5=float(text[1]), load15=float(text[2]))


def thermal_temp_c(zone: int = 0) -> float:
    path = Path(f"/sys/class/thermal/thermal_zone{zone}/temp")
    raw = _read_sys_int(path)
    if raw is None:
        raise OSError(f"thermal zone {zone} unavailable")
    # Most zones report millidegrees Celsius.
    return raw / 1000.0 if abs(raw) > 1000 else float(raw)


def _ioctl_ipv4(name: str, request: int) -> str:
    if _fcntl_mod is None:
        raise OSError("fcntl is not available on this platform")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        ifreq = struct.pack("256s", name[:15].encode())
        result = _fcntl_mod.ioctl(sock.fileno(), request, ifreq)
        return socket.inet_ntoa(result[20:24])
    finally:
        sock.close()


def _iface_names() -> list[str]:
    net = Path("/sys/class/net")
    if net.is_dir():
        return sorted(p.name for p in net.iterdir() if p.is_dir())
    try:
        return [name for _idx, name in socket.if_nameindex()]
    except OSError:
        return []


def _read_iface_stat(iface: str, name: str) -> int | None:
    return _read_sys_int(Path(f"/sys/class/net/{iface}/statistics/{name}"))


def _iface_ipv4(iface: str) -> list[str]:
    try:
        return [_ioctl_ipv4(iface, SIOCGIFADDR)]
    except OSError:
        return []


def _iface_ipv6(iface: str) -> list[str]:
    path = Path("/proc/net/if_inet6")
    if not path.is_file():
        return []
    addrs: list[str] = []
    try:
        text = _read_text(path)
    except OSError:
        return []
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
    return addrs


def network_interface(iface: str, *, include_counters: bool = True) -> NetworkInterface:
    base = Path(f"/sys/class/net/{iface}")
    if not base.is_dir():
        raise OSError(f"network interface not found: {iface}")
    mac = _read_sys_str(base / "address")
    operstate = _read_sys_str(base / "operstate")
    mtu = _read_sys_int(base / "mtu")
    counters: dict[str, int | None] = {}
    if include_counters:
        for key in (
            "rx_bytes",
            "tx_bytes",
            "rx_packets",
            "tx_packets",
            "rx_errors",
            "tx_errors",
            "rx_dropped",
            "tx_dropped",
        ):
            counters[key] = _read_iface_stat(iface, key)
    return NetworkInterface(
        name=iface,
        mac=mac,
        ipv4=_iface_ipv4(iface),
        ipv6=_iface_ipv6(iface),
        operstate=operstate,
        mtu=mtu,
        rx_bytes=counters.get("rx_bytes"),
        tx_bytes=counters.get("tx_bytes"),
        rx_packets=counters.get("rx_packets"),
        tx_packets=counters.get("tx_packets"),
        rx_errors=counters.get("rx_errors"),
        tx_errors=counters.get("tx_errors"),
        rx_dropped=counters.get("rx_dropped"),
        tx_dropped=counters.get("tx_dropped"),
    )


def list_network_interfaces(*, include_loopback: bool = False) -> list[NetworkInterface]:
    ifaces: list[NetworkInterface] = []
    for name in _iface_names():
        if name == "lo" and not include_loopback:
            continue
        try:
            ifaces.append(network_interface(name))
        except OSError:
            continue
    return ifaces


def process_info(pid: int) -> ProcessInfo:
    status_path = Path(f"/proc/{pid}/status")
    text = _read_text(status_path)
    name = ""
    rss_kb: float | None = None
    threads = 0
    for line in text.splitlines():
        if line.startswith("Name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("VmRSS:"):
            rss_kb = float(line.split()[1])
        elif line.startswith("Threads:"):
            threads = int(line.split()[1])
    if rss_kb is None:
        raise OSError(f"VmRSS not found for pid {pid}")
    fd_count: int | None = None
    fd_dir = Path(f"/proc/{pid}/fd")
    try:
        fd_count = sum(1 for _ in fd_dir.iterdir())
    except OSError:
        fd_count = None
    pss_mb: float | None = None
    smaps = Path(f"/proc/{pid}/smaps_rollup")
    if smaps.is_file():
        try:
            for line in _read_text(smaps).splitlines():
                if line.startswith("Pss:"):
                    pss_mb = float(line.split()[1]) / 1024.0
                    break
        except OSError:
            pss_mb = None
    return ProcessInfo(
        pid=pid,
        name=name,
        rss_mb=rss_kb / 1024.0,
        threads=threads,
        fd_count=fd_count,
        pss_mb=pss_mb,
    )


def find_pids_by_comm(comm: str) -> list[int]:
    matches: list[int] = []
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            name = _read_text(entry / "comm").strip()
        except OSError:
            continue
        if name == comm:
            matches.append(int(entry.name))
    return sorted(matches)


def cpu_times() -> CpuTimes:
    text = _read_text(Path("/proc/stat"))
    for line in text.splitlines():
        if not line.startswith("cpu "):
            continue
        parts = line.split()
        values = [float(p) for p in parts[1:9]]
        while len(values) < 8:
            values.append(0.0)
        return CpuTimes(
            user=values[0],
            nice=values[1],
            system=values[2],
            idle=values[3],
            iowait=values[4],
            irq=values[5],
            softirq=values[6],
            steal=values[7],
        )
    raise OSError("cpu line not found in /proc/stat")


def cpu_utilization(*, interval_s: float = 0.2) -> CpuUtilization:
    first = cpu_times()
    time.sleep(max(0.01, interval_s))
    second = cpu_times()
    return cpu_utilization_from_samples(first, second)


def cpu_utilization_from_samples(first: CpuTimes, second: CpuTimes) -> CpuUtilization:
    delta_total = second.total - first.total
    if delta_total <= 0:
        return CpuUtilization(
            percent=0.0,
            user_percent=0.0,
            system_percent=0.0,
            idle_percent=0.0,
            iowait_percent=0.0,
            irq_percent=0.0,
            steal_percent=0.0,
        )

    def pct(a: float, b: float) -> float:
        return 100.0 * (b - a) / delta_total

    return CpuUtilization(
        percent=100.0 * (second.busy - first.busy) / delta_total,
        user_percent=pct(first.user + first.nice, second.user + second.nice),
        system_percent=pct(first.system, second.system),
        idle_percent=pct(first.idle, second.idle),
        iowait_percent=pct(first.iowait, second.iowait),
        irq_percent=pct(first.irq + first.softirq, second.irq + second.softirq),
        steal_percent=pct(first.steal, second.steal),
    )


def vmstat() -> VmStat:
    text = _read_text(Path("/proc/vmstat"))
    fields: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            fields[parts[0]] = int(parts[1])
        except ValueError:
            continue
    return VmStat(
        pgfault=fields.get("pgfault", 0),
        pgpgin=fields.get("pgpgin", 0),
        pgpgout=fields.get("pgpgout", 0),
        oom_kill=fields.get("oom_kill", 0),
    )


def _diskstats_row(device: str) -> tuple[int, int, int, int]:
    """Return (reads, read_sectors, writes, write_sectors) for ``device``."""
    text = _read_text(Path("/proc/diskstats"))
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 14:
            continue
        if parts[2] != device:
            continue
        return int(parts[3]), int(parts[5]), int(parts[7]), int(parts[9])
    raise OSError(f"diskstats entry not found for {device}")


def disk_rates(*, device: str, interval_s: float = 0.2) -> DiskRates:
    r1, rs1, w1, ws1 = _diskstats_row(device)
    time.sleep(max(0.01, interval_s))
    r2, rs2, w2, ws2 = _diskstats_row(device)
    dt = max(0.01, interval_s)
    # Linux sectors are typically 512 bytes.
    sector = 512.0
    return DiskRates(
        device=device,
        read_bps=(rs2 - rs1) * sector / dt,
        write_bps=(ws2 - ws1) * sector / dt,
        read_iops=(r2 - r1) / dt,
        write_iops=(w2 - w1) / dt,
    )


def net_rates(*, iface: str, interval_s: float = 0.2) -> NetRates:
    first = network_interface(iface, include_counters=True)
    time.sleep(max(0.01, interval_s))
    second = network_interface(iface, include_counters=True)
    return net_rates_from_samples(first, second, interval_s=interval_s)


def net_rates_from_samples(
    first: NetworkInterface,
    second: NetworkInterface,
    *,
    interval_s: float,
) -> NetRates:
    dt = max(0.01, interval_s)

    def delta(a: int | None, b: int | None) -> float:
        if a is None or b is None:
            return 0.0
        return float(b - a)

    return NetRates(
        iface=second.name,
        rx_bps=delta(first.rx_bytes, second.rx_bytes) / dt,
        tx_bps=delta(first.tx_bytes, second.tx_bytes) / dt,
        rx_pps=delta(first.rx_packets, second.rx_packets) / dt,
        tx_pps=delta(first.tx_packets, second.tx_packets) / dt,
        rx_errors=int(second.rx_errors or 0),
        tx_errors=int(second.tx_errors or 0),
        rx_dropped=int(second.rx_dropped or 0),
        tx_dropped=int(second.tx_dropped or 0),
    )
