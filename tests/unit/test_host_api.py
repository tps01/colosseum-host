"""Host plugin measurement and verification APIs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from colosseum_host.api import bench, config, net, proc, sample, system
from colosseum_host.api._verify import verify_maximum, verify_minimum
from colosseum_host.host.collectors.types import (
    CpuUtilization,
    LoadAverage,
    MemInfo,
    NetworkInterface,
    ProcessInfo,
    VmStat,
)


def test_measure_python_version_records_host_domain(ctx) -> None:
    system.measure_python_version(key="py")
    row = ctx.db.get_measurement("host", "system.measure_python_version", "py", row_index=0)
    assert row is not None
    assert row.value


def test_verify_memory_minimum_pass_and_fail(ctx) -> None:
    system.measure_memory_available_mb(key="mem")
    pass_result = verify_minimum(
        domain="host",
        command="system.measure_memory_available_mb",
        key="mem",
        minimum=0.0,
    )
    assert pass_result.status == "PASS"
    fail_result = verify_minimum(
        domain="host",
        command="system.measure_memory_available_mb",
        key="mem",
        minimum=1e12,
    )
    assert fail_result.status == "FAIL"


def test_verify_python_version_prefix(ctx) -> None:
    system.measure_python_version(key="py")
    result = system.verify_python_version(key="py", version_prefix="3.")
    assert result.status == "PASS"


def test_verify_platform_exact(ctx) -> None:
    system.measure_platform(key="plat")
    row = ctx.db.get_measurement("host", "system.measure_platform", "plat", row_index=0)
    result = system.verify_platform(key="plat", expected_platform=str(row.value))
    assert result.status == "PASS"


def test_measure_visa_backend(ctx) -> None:
    mock_rm = MagicMock()
    mock_rm.return_value.visalib = "@sim"
    with patch("pyvisa.ResourceManager", mock_rm):
        bench.measure_visa_backend(key="visa")
    row = ctx.db.get_measurement("host", "bench.measure_visa_backend", "visa", row_index=0)
    assert row is not None
    assert "@sim" in str(row.value)


def test_verify_visa_available_allows_sim_by_default(ctx) -> None:
    mock_rm = MagicMock()
    mock_rm.return_value.visalib = "@sim"
    with patch("pyvisa.ResourceManager", mock_rm):
        bench.measure_visa_backend(key="visa")
    result = bench.verify_visa_available(key="visa")
    assert result.status == "PASS"


def test_capture_host_profile_writes_artifact(ctx) -> None:
    written = config.capture_host_profile(path="host_profile.json")
    path = Path(written)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert text.strip().startswith("{")
    assert "network_interfaces" in text
    assert "kernel" in text


def test_verify_bench_config_loaded_without_config(ctx) -> None:
    result = config.verify_bench_config_loaded(key="cfg")
    assert result.status == "FAIL"


def test_verify_bench_config_loaded_with_config(ctx, tmp_path) -> None:
    ctx.config_path = tmp_path / "config.toml"
    result = config.verify_bench_config_loaded(key="cfg")
    assert result.status == "PASS"


def test_measure_meminfo(ctx) -> None:
    fake = MemInfo(total_mb=1000, available_mb=400, swap_total_mb=200, swap_free_mb=50)
    with patch("colosseum_host.api.system.meminfo", return_value=fake):
        system.measure_meminfo(key="mem")
    row = ctx.db.get_measurement("host", "system.measure_meminfo", "mem", row_index=0)
    assert row is not None
    assert row.value["available_mb"] == 400


def test_measure_loadavg(ctx) -> None:
    fake = LoadAverage(load1=0.1, load5=0.2, load15=0.3)
    with patch("colosseum_host.api.system.loadavg", return_value=fake):
        system.measure_loadavg(key="load")
    row = ctx.db.get_measurement("host", "system.measure_loadavg", "load", row_index=0)
    assert row is not None
    assert row.value["load1"] == 0.1


def test_measure_mac_and_ipv4(ctx) -> None:
    fake = NetworkInterface(name="eth0", mac="aa:bb:cc:dd:ee:ff", ipv4=["192.168.1.10"], ipv6=[])
    with patch("colosseum_host.api.net.network_interface", return_value=fake):
        net.measure_mac(key="mac", iface="eth0")
        net.measure_ipv4(key="ip", iface="eth0")
    mac = ctx.db.get_measurement("host", "net.measure_mac", "mac", row_index=0)
    ip = ctx.db.get_measurement("host", "net.measure_ipv4", "ip", row_index=0)
    assert mac is not None and mac.value == "aa:bb:cc:dd:ee:ff"
    assert ip is not None and ip.value == ["192.168.1.10"]


def test_measure_rss_mb(ctx) -> None:
    fake = ProcessInfo(pid=7, name="app", rss_mb=12.5, threads=2, fd_count=8)
    with patch("colosseum_host.api.proc.process_info", return_value=fake):
        proc.measure_rss_mb(key="rss", pid=7)
    row = ctx.db.get_measurement("host", "proc.measure_rss_mb", "rss", row_index=0)
    assert row is not None
    assert row.value == 12.5


def test_verify_maximum_helper(ctx) -> None:
    system.measure_memory_available_mb(key="mem")
    result = verify_maximum(
        domain="host",
        command="system.measure_memory_available_mb",
        key="mem",
        maximum=1e12,
    )
    assert result.status == "PASS"


def test_measure_vmstat_and_oom_verify(ctx) -> None:
    fake = VmStat(pgfault=10, pgpgin=1, pgpgout=2, oom_kill=0)
    with patch("colosseum_host.api.system.vmstat", return_value=fake):
        system.measure_vmstat(key="vm")
    assert system.verify_oom_kill(key="vm", maximum=0).status == "PASS"


def test_measure_cpu_percent(ctx) -> None:
    fake = CpuUtilization(
        percent=33.0,
        user_percent=20.0,
        system_percent=13.0,
        idle_percent=67.0,
        iowait_percent=0.0,
        irq_percent=0.0,
        steal_percent=0.0,
    )
    with patch("colosseum_host.api.system.cpu_utilization", return_value=fake):
        system.measure_cpu_percent(key="cpu")
    row = ctx.db.get_measurement("host", "system.measure_cpu_percent", "cpu", row_index=0)
    assert row is not None
    assert row.value == 33.0


def test_sample_capture_writes_csv_and_summaries(ctx, tmp_path) -> None:
    values = {"memory_available_mb": [100.0, 90.0, 80.0]}

    def fake_reader(name: str):
        seq = values[name]

        def _read(_kwargs: dict) -> float:
            if len(seq) > 1:
                return seq.pop(0)
            return seq[0]

        return _read

    with (
        patch.dict(
            sample._METRIC_READERS,
            {"memory_available_mb": fake_reader("memory_available_mb")},
            clear=False,
        ),
        patch("colosseum_host.api.sample.time.sleep", return_value=None),
    ):
        result = sample.capture(
            key="stress",
            metrics=("memory_available_mb",),
            interval_s=0.01,
            duration_s=0.03,
            path="sample.csv",
        )
    path = Path(result["path"])
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "elapsed_s,metric,value" in text
    assert "memory_available_mb" in text
    summary = ctx.db.get_measurement(
        "host", "sample.measure_summary", "stress.memory_available_mb", row_index=0,
    )
    assert summary is not None
    assert summary.value["delta"] == -20.0
    assert sample.verify_delta_max(key="stress.memory_available_mb", maximum=0.0).status == "PASS"
    assert sample.verify_max(key="stress.memory_available_mb", maximum=100.0).status == "PASS"
