"""Host collector platform helpers."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from colosseum_host.host.collectors import common, linux, types, windows
from colosseum_host.host.collectors.types import CpuTimes, NetworkInterface

if TYPE_CHECKING:
    from pathlib import Path


def test_disk_free_gb_uses_shutil(tmp_path: Path) -> None:
    with patch("colosseum_host.host.collectors.common.shutil.disk_usage") as usage:
        usage.return_value = MagicMock(free=5 * 1024**3)
        assert common.disk_free_gb(tmp_path) == pytest.approx(5.0)


def test_linux_memory_available_mb_parses_meminfo() -> None:
    meminfo = (
        "MemTotal:       16384000 kB\n"
        "MemAvailable:    2048000 kB\n"
        "SwapTotal:       1048576 kB\n"
        "SwapFree:         524288 kB\n"
    )
    with patch.object(linux.Path, "read_text", return_value=meminfo):
        info = linux.meminfo()
        assert info.available_mb == pytest.approx(2000.0)
        assert info.total_mb == pytest.approx(16000.0)
        assert info.swap_used_mb == pytest.approx(512.0)
        assert linux.memory_available_mb() == pytest.approx(2000.0)


def test_linux_uptime_s_reads_proc() -> None:
    with patch.object(linux.Path, "read_text", return_value="123.45 456.78\n"):
        assert linux.uptime_s() == pytest.approx(123.45)


def test_linux_loadavg() -> None:
    with patch.object(linux.Path, "read_text", return_value="0.50 0.75 1.00 1/200 1234\n"):
        avg = linux.loadavg()
        assert avg.load1 == pytest.approx(0.5)
        assert avg.load5 == pytest.approx(0.75)
        assert avg.load15 == pytest.approx(1.0)


def test_linux_thermal_temp_c_millidegrees() -> None:
    with patch.object(linux, "_read_sys_int", return_value=45500):
        assert linux.thermal_temp_c(0) == pytest.approx(45.5)


def test_linux_process_info() -> None:
    status = "Name:\tpython\nVmRSS:\t204800 kB\nThreads:\t4\n"
    smaps = "Pss:               102400 kB\n"

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        _ = args, kwargs
        text = self.as_posix()
        if text.endswith("/status"):
            return status
        if text.endswith("/smaps_rollup"):
            return smaps
        raise AssertionError(text)

    with (
        patch.object(linux.Path, "read_text", fake_read_text),
        patch.object(linux.Path, "is_file", return_value=True),
        patch.object(linux.Path, "iterdir", return_value=iter([1, 2, 3])),
    ):
        info = linux.process_info(42)
    assert info.pid == 42
    assert info.name == "python"
    assert info.rss_mb == pytest.approx(200.0)
    assert info.threads == 4
    assert info.fd_count == 3
    assert info.pss_mb == pytest.approx(100.0)


def test_linux_cpu_utilization_from_samples() -> None:
    first = CpuTimes(100, 0, 50, 850, 0, 0, 0, 0)
    second = CpuTimes(150, 0, 70, 880, 0, 0, 0, 0)
    util = linux.cpu_utilization_from_samples(first, second)
    assert util.percent == pytest.approx(70.0)
    assert util.user_percent == pytest.approx(50.0)
    assert util.system_percent == pytest.approx(20.0)
    assert util.idle_percent == pytest.approx(30.0)


def test_linux_vmstat() -> None:
    text = "pgpgin 10\npgpgout 20\npgfault 100\noom_kill 2\n"
    with patch.object(linux.Path, "read_text", return_value=text):
        stats = linux.vmstat()
    assert stats.pgfault == 100
    assert stats.oom_kill == 2


def test_linux_net_rates_from_samples() -> None:
    first = NetworkInterface(
        name="eth0",
        rx_bytes=1000,
        tx_bytes=2000,
        rx_packets=10,
        tx_packets=20,
        rx_errors=0,
        tx_errors=1,
        rx_dropped=0,
        tx_dropped=0,
    )
    second = NetworkInterface(
        name="eth0",
        rx_bytes=3000,
        tx_bytes=4000,
        rx_packets=30,
        tx_packets=40,
        rx_errors=0,
        tx_errors=1,
        rx_dropped=2,
        tx_dropped=0,
    )
    rates = linux.net_rates_from_samples(first, second, interval_s=1.0)
    assert rates.rx_bps == pytest.approx(2000.0)
    assert rates.tx_bps == pytest.approx(2000.0)
    assert rates.rx_pps == pytest.approx(20.0)
    assert rates.rx_dropped == 2


def test_types_meminfo_swap_used() -> None:
    info = types.MemInfo(total_mb=1000, available_mb=400, swap_total_mb=200, swap_free_mb=50)
    assert info.swap_used_mb == pytest.approx(150.0)


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only ctypes path")
def test_windows_memory_available_mb() -> None:
    fake_kernel = MagicMock()
    fake_kernel.GlobalMemoryStatusEx.return_value = True
    with patch("colosseum_host.host.collectors.windows.ctypes.windll.kernel32", fake_kernel):
        assert windows.memory_available_mb() >= 0.0


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only ctypes path")
def test_windows_uptime_s() -> None:
    fake_kernel = MagicMock()
    fake_kernel.GetTickCount64.return_value = 60_000
    with patch("colosseum_host.host.collectors.windows.ctypes.windll.kernel32", fake_kernel):
        assert windows.uptime_s() == pytest.approx(60.0)


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only path")
def test_windows_linux_only_raises() -> None:
    with pytest.raises(OSError, match="only available on Linux"):
        windows.loadavg()
