"""Shared collector data types."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LoadAverage:
    """System load averages (1 / 5 / 15 minute)."""

    load1: float
    load5: float
    load15: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class MemInfo:
    """Memory snapshot in megabytes."""

    total_mb: float
    available_mb: float
    swap_total_mb: float
    swap_free_mb: float

    @property
    def swap_used_mb(self) -> float:
        return max(0.0, self.swap_total_mb - self.swap_free_mb)

    def as_dict(self) -> dict[str, float]:
        data = asdict(self)
        data["swap_used_mb"] = self.swap_used_mb
        return data


@dataclass(frozen=True)
class NetworkInterface:
    """Local network interface identity and optional counters."""

    name: str
    mac: str | None = None
    ipv4: list[str] | None = None
    ipv6: list[str] | None = None
    operstate: str | None = None
    mtu: int | None = None
    rx_bytes: int | None = None
    tx_bytes: int | None = None
    rx_packets: int | None = None
    tx_packets: int | None = None
    rx_errors: int | None = None
    tx_errors: int | None = None
    rx_dropped: int | None = None
    tx_dropped: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CpuTimes:
    """Cumulative CPU time counters from ``/proc/stat`` (jiffies)."""

    user: float
    nice: float
    system: float
    idle: float
    iowait: float
    irq: float
    softirq: float
    steal: float

    @property
    def total(self) -> float:
        return (
            self.user
            + self.nice
            + self.system
            + self.idle
            + self.iowait
            + self.irq
            + self.softirq
            + self.steal
        )

    @property
    def busy(self) -> float:
        return self.total - self.idle - self.iowait

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class CpuUtilization:
    """CPU utilization percentages derived from two ``CpuTimes`` samples."""

    percent: float
    user_percent: float
    system_percent: float
    idle_percent: float
    iowait_percent: float
    irq_percent: float
    steal_percent: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class NetRates:
    """Network interface byte/packet rates over a sample interval."""

    iface: str
    rx_bps: float
    tx_bps: float
    rx_pps: float
    tx_pps: float
    rx_errors: int
    tx_errors: int
    rx_dropped: int
    tx_dropped: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiskRates:
    """Block device I/O rates over a sample interval."""

    device: str
    read_bps: float
    write_bps: float
    read_iops: float
    write_iops: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VmStat:
    """Selected ``/proc/vmstat`` counters."""

    pgfault: int
    pgpgin: int
    pgpgout: int
    oom_kill: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class ProcessInfo:
    """Per-process memory and thread facts."""

    pid: int
    name: str
    rss_mb: float
    threads: int
    fd_count: int | None = None
    pss_mb: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
