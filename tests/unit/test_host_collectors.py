"""Host collector platform helpers."""

from __future__ import annotations

import ctypes
import socket
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from colosseum_host.host.collectors import common, linux, types, windows
from colosseum_host.host.collectors.types import CpuTimes, NetworkInterface
from colosseum_host.host.network import windows as win_network

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


@pytest.mark.parametrize(
    ("raw", "celsius"),
    [
        (45500, 45.5),
        (1000, 1.0),
        (500, 0.5),
        (0, 0.0),
        (-500, -0.5),
        (-1000, -1.0),
    ],
)
def test_linux_thermal_temp_c_uses_millidegree_unit(raw: int, celsius: float) -> None:
    with patch.object(linux, "_read_sys_int", return_value=raw):
        assert linux.thermal_temp_c(0) == pytest.approx(celsius)


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


def test_linux_fd_count_zero_is_distinct_from_unavailable() -> None:
    status = "Name:\tpython\nVmRSS:\t1024 kB\nThreads:\t1\n"

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        _ = args, kwargs
        text = self.as_posix()
        if text.endswith("/status"):
            return status
        raise AssertionError(text)

    with (
        patch.object(linux.Path, "read_text", fake_read_text),
        patch.object(linux.Path, "is_file", return_value=False),
        patch.object(linux.Path, "iterdir", return_value=iter(())),
    ):
        assert linux.process_info(1).fd_count == 0
    with (
        patch.object(linux.Path, "read_text", fake_read_text),
        patch.object(linux.Path, "is_file", return_value=False),
        patch.object(linux.Path, "iterdir", side_effect=OSError("unreadable")),
    ):
        assert linux.process_info(1).fd_count is None


def test_linux_net_rates_divide_by_elapsed_time() -> None:
    clock = {"now": 0.0}

    def monotonic() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    def iface(_name: str, *, include_counters: bool) -> NetworkInterface:
        _ = include_counters
        clock["now"] += 0.1
        return NetworkInterface(
            name="eth0",
            rx_bytes=int(clock["now"] * 100),
            tx_bytes=0,
            rx_packets=0,
            tx_packets=0,
            rx_errors=0,
            tx_errors=0,
            rx_dropped=0,
            tx_dropped=0,
        )

    with (
        patch.object(linux.time, "monotonic", monotonic),
        patch.object(linux.time, "sleep", sleep),
        patch.object(linux, "network_interface", side_effect=iface),
    ):
        rates = linux.net_rates(iface="eth0", interval_s=0.1)
    assert rates.rx_bps == pytest.approx(100.0)


def test_linux_disk_rates_divide_by_delayed_wakeup() -> None:
    clock = {"now": 0.0}

    def monotonic() -> float:
        return clock["now"]

    def sleep(_seconds: float) -> None:
        clock["now"] += 0.5

    def row(_device: str) -> tuple[int, int, int, int]:
        return (0, int(clock["now"] * 2), 0, 0)

    with (
        patch.object(linux.time, "monotonic", monotonic),
        patch.object(linux.time, "sleep", sleep),
        patch.object(linux, "_diskstats_row", side_effect=row),
    ):
        rates = linux.disk_rates(device="sda", interval_s=0.1)
    assert rates.read_bps == pytest.approx(1024.0)


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
    from colosseum_host.exceptions import HostCapabilityError

    with pytest.raises(HostCapabilityError, match="only available on Linux"):
        windows.loadavg()


class _FakeGetTickCount64:
    """Return a tick count truncated the way ctypes would for the configured restype."""

    def __init__(self, raw_ms: int) -> None:
        self.restype = ctypes.c_int
        self.raw_ms = raw_ms

    def __call__(self) -> int:
        restype = self.restype if self.restype is not None else ctypes.c_int
        return int(restype(self.raw_ms).value)


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only ctypes path")
@pytest.mark.parametrize(
    "raw_ms",
    [
        (1 << 31) + 1000,
        (1 << 32) + (1 << 31),
    ],
)
def test_windows_uptime_restype_keeps_64_bit_tick_count(raw_ms: int) -> None:
    fake = _FakeGetTickCount64(raw_ms)
    fake_kernel = MagicMock()
    fake_kernel.GetTickCount64 = fake
    with patch("colosseum_host.host.collectors.windows.ctypes.windll.kernel32", fake_kernel):
        seconds = windows.uptime_s()
    assert fake.restype is ctypes.c_ulonglong
    assert seconds == pytest.approx(raw_ms / 1000.0)
    assert seconds != pytest.approx(ctypes.c_int(raw_ms).value / 1000.0)


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only path")
def test_windows_counters_raise_and_identity_does_not() -> None:
    from colosseum_host.exceptions import HostCapabilityError

    with pytest.raises(HostCapabilityError, match="network counters"):
        windows.network_interface("Ethernet", include_counters=True)
    fake = NetworkInterface(name="Ethernet", mac="aa:bb:cc:dd:ee:ff", ipv4=["10.0.0.1"])
    with patch.object(windows, "list_network_interfaces", return_value=[fake]):
        found = windows.network_interface("Ethernet", include_counters=False)
    assert found.name == "Ethernet"
    assert found.ipv4 == ["10.0.0.1"]
    assert found.rx_bytes is None


def _sockaddr(family: int, length: int, address: bytes, at: int) -> ctypes.Array[ctypes.c_char]:
    raw = bytearray(length)
    raw[0:2] = family.to_bytes(2, "little")
    raw[at : at + len(address)] = address
    return ctypes.create_string_buffer(bytes(raw))


def _unicast(
    sockaddr: ctypes.Array[ctypes.c_char],
    *,
    prefix: int,
    socklen: int,
    length: int | None = None,
    nxt: object = None,
) -> win_network._IP_ADAPTER_UNICAST_ADDRESS:
    row = win_network._IP_ADAPTER_UNICAST_ADDRESS()
    row.Length = ctypes.sizeof(row) if length is None else length
    row.OnLinkPrefixLength = prefix
    row.Address.lpSockaddr = ctypes.addressof(sockaddr)
    row.Address.iSockaddrLength = socklen
    if nxt is not None:
        row.Next = ctypes.pointer(nxt)
    return row


def _adapters_from(adapter: win_network._IP_ADAPTER_ADDRESSES, result: int = 0):
    def fake(*_args: object) -> int:
        if result == 0:
            ctypes.memmove(
                _args[3],
                ctypes.byref(adapter),
                ctypes.sizeof(adapter),
            )
        return result

    with patch.object(win_network, "_iphlpapi") as api:
        api.return_value.GetAdaptersAddresses.side_effect = fake
        return win_network.list_adapters()


def test_windows_linked_unicast_addresses_stay_on_the_adapter() -> None:
    ipv6_bytes = bytes.fromhex("20010db8000000000000000000000001")
    sa6 = _sockaddr(socket.AF_INET6, 28, ipv6_bytes, 8)
    sa4 = _sockaddr(socket.AF_INET, 16, bytes((10, 1, 2, 3)), 4)
    ipv6 = _unicast(sa6, prefix=64, socklen=28)
    ipv4 = _unicast(sa4, prefix=0, socklen=16, nxt=ipv6)
    adapter = win_network._IP_ADAPTER_ADDRESSES()
    adapter.FriendlyName = "Audit adapter"
    adapter.IfType = 6
    adapter.OperStatus = 1
    adapter.Mtu = 1500
    adapter.FirstUnicastAddress = ctypes.addressof(ipv4)
    found = _adapters_from(adapter)
    assert len(found) == 1
    assert found[0].name == "Audit adapter"
    assert found[0].ipv4 == (win_network.IPv4Endpoint("10.1.2.3", 0),)
    assert found[0].ipv6 == (socket.inet_ntop(socket.AF_INET6, ipv6_bytes),)


def test_windows_ipv4_prefix_keeps_zero_and_reports_unusable() -> None:
    def snapshot(prefix: int, length: int | None = None):
        sockaddr = _sockaddr(socket.AF_INET, 16, bytes((192, 168, 1, 10)), 4)
        unicast = _unicast(sockaddr, prefix=prefix, socklen=16, length=length)
        adapter = win_network._IP_ADAPTER_ADDRESSES()
        adapter.FriendlyName = "Prefix"
        adapter.IfType = 6
        adapter.FirstUnicastAddress = ctypes.addressof(unicast)
        found = _adapters_from(adapter)
        assert len(found) == 1
        assert len(found[0].ipv4) == 1
        return found[0].ipv4[0].prefix, sockaddr, unicast

    assert snapshot(24)[0] == 24
    assert snapshot(0)[0] == 0
    assert snapshot(33)[0] is None
    short = win_network._IP_ADAPTER_UNICAST_ADDRESS.OnLinkPrefixLength.offset
    assert snapshot(24, length=short)[0] is None


def test_windows_adapter_enumeration_failure_is_not_an_empty_inventory() -> None:
    adapter = win_network._IP_ADAPTER_ADDRESSES()
    with pytest.raises(OSError, match="GetAdaptersAddresses failed"):
        _adapters_from(adapter, result=87)
    assert _adapters_from(adapter, result=win_network._ERROR_NO_DATA) == []
