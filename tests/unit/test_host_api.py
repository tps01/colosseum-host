"""Host plugin measurement and verification APIs."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from colosseum_host._paths import resolve_artifact_path
from colosseum_host.api import bench, config, net, proc, sample, system
from colosseum_host.api._verify import verify_maximum, verify_minimum
from colosseum_host.host.collectors import linux
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


def test_verify_memory_uses_host_profile_default(ctx) -> None:
    from colosseum.config.loader import ConfigStore
    from colosseum.config.sections import ConfigSectionSpec

    system.measure_memory_available_mb(key="mem")
    ctx.config = ConfigStore(
        _raw={"host": {"profile": {"profile_id": 1, "min_memory_mb": 0.0}}},
        _normalized={
            "host.profile": {1: {"profile_id": 1, "min_memory_mb": 0.0}},
        },
        _specs={
            "host.profile": ConfigSectionSpec(
                "host.profile",
                "profile_id",
                required_keys=(),
                optional_keys=("min_memory_mb",),
            ),
        },
    )
    result = system.verify_memory_available_mb(key="mem")
    assert result.status == "PASS"
    assert config.get_profile(profile_id=1)["min_memory_mb"] == 0.0


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


def test_sim_backend_without_display_marker_is_rejected_when_required(ctx) -> None:
    class SimLibrary:
        __module__ = "pyvisa_sim.highlevel"

        def __str__(self) -> str:
            return "Visa Library at unset"

    mock_rm = MagicMock()
    mock_rm.return_value.visalib = SimLibrary()
    with patch("pyvisa.ResourceManager", mock_rm):
        bench.measure_visa_backend(key="visa")
    assert bench.verify_visa_available(key="visa", allow_sim=True).status == "PASS"
    assert bench.verify_visa_available(key="visa", allow_sim=False).status == "FAIL"


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


def test_artifact_path_rejects_sibling_prefix_and_traversal(ctx, tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    other = tmp_path / "run-other"
    other.mkdir()
    ctx.output_dir = run
    ctx.runtime_ready = True

    with pytest.raises(ValueError, match="inside the active output directory"):
        resolve_artifact_path("../run-other/evidence.csv")
    assert not (other / "evidence.csv").exists()

    with pytest.raises(ValueError, match="inside the active output directory"):
        resolve_artifact_path("../outside.csv")
    assert not (tmp_path / "outside.csv").exists()

    nested = resolve_artifact_path("nested/evidence.csv")
    assert nested.is_relative_to(run.resolve())
    assert nested.parent.is_dir()


def test_summarize_omits_unavailable_samples() -> None:
    assert sample._summarize([0.0, None, 4.0]) == {
        "min": 0.0,
        "max": 4.0,
        "last": 4.0,
        "delta": 4.0,
        "mean": 2.0,
    }
    assert sample._summarize([None, None]) is None
    assert sample._summarize([0.0])["mean"] == 0.0


def test_fd_count_zero_passes_and_unavailable_errors(ctx) -> None:
    zero = ProcessInfo(pid=1, name="audit", rss_mb=1.0, threads=1, fd_count=0)
    missing = ProcessInfo(pid=1, name="audit", rss_mb=1.0, threads=1, fd_count=None)
    with patch("colosseum_host.api.proc.process_info", return_value=zero):
        assert proc.measure_fd_count(key="fd-zero", pid=1) == 0.0
    assert proc.verify_fd_count(key="fd-zero", maximum=0).status == "PASS"
    with patch("colosseum_host.api.proc.process_info", return_value=missing):
        assert proc.measure_fd_count(key="fd-missing", pid=1) is None
    unavailable = proc.verify_fd_count(key="fd-missing", maximum=0)
    assert unavailable.status == "ERROR"
    assert "unavailable" in unavailable.message
    with patch("colosseum_host.api.sample.process_info", return_value=zero):
        assert sample._METRIC_READERS["proc.fd_count"]({"pid": 1}) == 0.0
    with patch("colosseum_host.api.sample.process_info", return_value=missing):
        assert sample._METRIC_READERS["proc.fd_count"]({"pid": 1}) is None


def test_capture_fd_zero_is_summarized_and_unavailable_is_not(ctx) -> None:
    zero = ProcessInfo(pid=1, name="audit", rss_mb=1.0, threads=1, fd_count=0)
    missing = ProcessInfo(pid=1, name="audit", rss_mb=1.0, threads=1, fd_count=None)
    with (
        patch("colosseum_host.api.sample.process_info", return_value=zero),
        patch("colosseum_host.api.sample.time.sleep", return_value=None),
    ):
        observed = sample.capture(
            key="fd-zero",
            metrics=("proc.fd_count",),
            interval_s=0.01,
            duration_s=0.01,
            pid=1,
            path="fd-zero.csv",
        )
    assert observed["summaries"]["proc.fd_count"]["min"] == 0.0
    assert observed["summaries"]["proc.fd_count"]["mean"] == 0.0
    assert "-1" not in Path(observed["path"]).read_text(encoding="utf-8")

    with (
        patch("colosseum_host.api.sample.process_info", return_value=missing),
        patch("colosseum_host.api.sample.time.sleep", return_value=None),
    ):
        unavailable = sample.capture(
            key="fd-missing",
            metrics=("proc.fd_count",),
            interval_s=0.01,
            duration_s=0.01,
            pid=1,
            path="fd-missing.csv",
        )
    assert "proc.fd_count" not in unavailable["summaries"]
    text = Path(unavailable["path"]).read_text(encoding="utf-8")
    assert "proc.fd_count" in text
    assert "-1" not in text
    missing_summary = sample.verify_max(key="fd-missing.proc.fd_count", maximum=0)
    assert missing_summary.status == "ERROR"


def _counter_iface(name: str, rx_bytes: int) -> NetworkInterface:
    return NetworkInterface(
        name=name,
        rx_bytes=rx_bytes,
        tx_bytes=0,
        rx_packets=0,
        tx_packets=0,
        rx_errors=0,
        tx_errors=0,
        rx_dropped=0,
        tx_dropped=0,
    )


def test_read_rate_family_uses_elapsed_not_requested_sleep() -> None:
    clock = {"now": 0.0}

    def monotonic() -> float:
        return clock["now"]

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    def iface(*_args: object, **_kwargs: object) -> NetworkInterface:
        clock["now"] += 0.1
        return _counter_iface("audit", int(clock["now"] * 100))

    with (
        patch.object(sample.time, "monotonic", monotonic),
        patch.object(sample.time, "sleep", sleep),
        patch.object(sample, "network_interface", side_effect=iface),
        patch.object(sample, "net_rates_from_samples", side_effect=linux.net_rates_from_samples),
    ):
        rates = sample._read_rate_family(("net.rx_bps",), {"iface": "audit"}, interval_s=0.1)
    assert rates["net.rx_bps"] == pytest.approx(100.0)


def test_read_rate_family_disk_uses_delayed_wakeup() -> None:
    clock = {"now": 0.0}
    seen: dict[str, float] = {}

    def monotonic() -> float:
        return clock["now"]

    def sleep(_seconds: float) -> None:
        clock["now"] += 0.5

    def diskstats(_device: str) -> tuple[int, int, int, int]:
        return (0, int(clock["now"] * 2), 0, 0)

    def rates(
        first: tuple[int, int, int, int],
        second: tuple[int, int, int, int],
        *,
        device: str,
        interval_s: float,
    ):
        seen["interval_s"] = interval_s
        return linux.disk_rates_from_samples(
            first, second, device=device, interval_s=interval_s,
        )

    with (
        patch.object(sample.time, "monotonic", monotonic),
        patch.object(sample.time, "sleep", sleep),
        patch.object(sample, "diskstats_row", side_effect=diskstats),
        patch.object(sample, "disk_rates_from_samples", side_effect=rates),
    ):
        result = sample._read_rate_family(
            ("disk.read_bps",),
            {"device": "sda"},
            interval_s=0.1,
        )
    assert seen["interval_s"] == pytest.approx(0.5)
    assert result["disk.read_bps"] == pytest.approx(1024.0)


def test_default_capture_paths_are_unique_per_key(ctx) -> None:
    current = {"value": 111.0}

    def reader(_kwargs: dict) -> float:
        return current["value"]

    with (
        patch.dict(sample._METRIC_READERS, {"memory_available_mb": reader}, clear=False),
        patch("colosseum_host.api.sample.time.sleep", return_value=None),
    ):
        first = sample.capture(
            key="alpha",
            metrics=("memory_available_mb",),
            interval_s=0.01,
            duration_s=0.01,
        )
        current["value"] = 222.0
        second = sample.capture(
            key="beta",
            metrics=("memory_available_mb",),
            interval_s=0.01,
            duration_s=0.01,
        )
        current["value"] = 333.0
        replaced = sample.capture(
            key="gamma",
            metrics=("memory_available_mb",),
            interval_s=0.01,
            duration_s=0.01,
            path="shared.csv",
        )
        current["value"] = 444.0
        sample.capture(
            key="delta",
            metrics=("memory_available_mb",),
            interval_s=0.01,
            duration_s=0.01,
            path="shared.csv",
        )

    first_text = Path(first["path"]).read_text(encoding="utf-8")
    second_text = Path(second["path"]).read_text(encoding="utf-8")
    shared_text = Path(replaced["path"]).read_text(encoding="utf-8")
    assert Path(first["path"]).name == "host_sample_alpha.csv"
    assert Path(second["path"]).name == "host_sample_beta.csv"
    assert "111.000000" in first_text
    assert "111.000000" not in second_text
    assert "222.000000" in second_text
    assert Path(first["path"]) != Path(second["path"])
    assert "333.000000" not in shared_text
    assert "444.000000" in shared_text


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only counters")
def test_measure_counters_raises_on_windows(ctx) -> None:
    from colosseum_host.exceptions import HostCapabilityError

    with pytest.raises(HostCapabilityError, match="network counters"):
        net.measure_counters(key="counters", iface="Ethernet")


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only counters")
def test_measure_interface_does_not_request_counters_on_windows(ctx) -> None:
    fake = NetworkInterface(name="Ethernet", mac="aa:bb:cc:dd:ee:ff", ipv4=["10.0.0.1"])
    with patch("colosseum_host.api.net.network_interface", return_value=fake) as iface:
        recorded = net.measure_interface(key="eth", iface="Ethernet")
    iface.assert_called_once_with("Ethernet", include_counters=False)
    assert recorded["name"] == "Ethernet"
    assert recorded["rx_bytes"] is None
