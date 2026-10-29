"""Blocking host metric sampler (``col.host.sample``)."""

from __future__ import annotations

import csv
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Optional

from colosseum.decorators import (
    VerificationResult,
    command,
    measurement,
    verification,
)
from colosseum.logging import get_logger

from colosseum_host._paths import resolve_artifact_path
from colosseum_host.host.collectors import (
    NetworkInterface,
    cpu_times,
    cpu_utilization,
    cpu_utilization_from_samples,
    disk_rates,
    disk_rates_from_samples,
    diskstats_row,
    loadavg,
    meminfo,
    memory_available_mb,
    net_rates,
    net_rates_from_samples,
    network_interface,
    process_info,
    thermal_temp_c,
    vmstat,
)

_DOMAIN = "host"
_logger = get_logger("colosseum.host")

_MetricFn = Callable[[dict[str, Any]], Optional[float]]

_GAUGE_METRICS = frozenset(
    {
        "memory_available_mb",
        "mem_total_mb",
        "swap_used_mb",
        "load1",
        "temp_c",
        "proc.rss_mb",
        "proc.threads",
        "proc.fd_count",
        "vm.pgfault",
        "vm.oom_kill",
    },
)
_CPU_RATE_METRICS = frozenset({"cpu_percent"})
_NET_RATE_METRICS = frozenset({"net.rx_bps", "net.tx_bps"})
_DISK_RATE_METRICS = frozenset({"disk.read_bps", "disk.write_bps"})
_RATE_METRICS = _CPU_RATE_METRICS | _NET_RATE_METRICS | _DISK_RATE_METRICS


def _require_pid(kwargs: dict[str, Any]) -> int:
    pid = kwargs.get("pid")
    if pid is None:
        raise ValueError("metric requires pid=")
    return int(pid)


def _require_iface(kwargs: dict[str, Any]) -> str:
    iface = kwargs.get("iface")
    if not iface:
        raise ValueError("metric requires iface=")
    return str(iface)


def _require_device(kwargs: dict[str, Any]) -> str:
    device = kwargs.get("device")
    if not device:
        raise ValueError("metric requires device=")
    return str(device)


def _proc_fd_count(kwargs: dict[str, Any]) -> float | None:
    """Open FD count, preserving zero. ``None`` means ``/proc/<pid>/fd`` was unreadable."""
    count = process_info(_require_pid(kwargs)).fd_count
    if count is None:
        return None
    return float(count)


_METRIC_READERS: dict[str, _MetricFn] = {
    "memory_available_mb": lambda _kw: memory_available_mb(),
    "mem_total_mb": lambda _kw: meminfo().total_mb,
    "swap_used_mb": lambda _kw: meminfo().swap_used_mb,
    "load1": lambda _kw: loadavg().load1,
    "temp_c": lambda kw: thermal_temp_c(zone=int(kw.get("zone", 0))),
    "cpu_percent": lambda kw: cpu_utilization(
        interval_s=float(kw.get("cpu_interval_s", 0.1)),
    ).percent,
    "proc.rss_mb": lambda kw: process_info(_require_pid(kw)).rss_mb,
    "proc.threads": lambda kw: float(process_info(_require_pid(kw)).threads),
    "proc.fd_count": _proc_fd_count,
    "net.rx_bps": lambda kw: net_rates(
        iface=_require_iface(kw), interval_s=float(kw.get("net_interval_s", 0.1)),
    ).rx_bps,
    "net.tx_bps": lambda kw: net_rates(
        iface=_require_iface(kw), interval_s=float(kw.get("net_interval_s", 0.1)),
    ).tx_bps,
    "disk.read_bps": lambda kw: disk_rates(
        device=_require_device(kw), interval_s=float(kw.get("disk_interval_s", 0.1)),
    ).read_bps,
    "disk.write_bps": lambda kw: disk_rates(
        device=_require_device(kw), interval_s=float(kw.get("disk_interval_s", 0.1)),
    ).write_bps,
    "vm.pgfault": lambda _kw: float(vmstat().pgfault),
    "vm.oom_kill": lambda _kw: float(vmstat().oom_kill),
}


def available_metrics() -> tuple[str, ...]:
    """Return supported sampler metric names."""
    return tuple(sorted(_METRIC_READERS))


def _summarize(values: list[float | None]) -> dict[str, float] | None:
    """Summarize observed samples.

    ``None`` marks an unavailable sample (for example an unreadable FD count).
    Those samples are left out of min, max, last, delta, and mean so a sentinel
    is never averaged in. When every sample is unavailable, return ``None``
    instead of a zero-filled summary.
    """
    observed = [value for value in values if value is not None]
    if not observed:
        return None
    return {
        "min": min(observed),
        "max": max(observed),
        "last": observed[-1],
        "delta": observed[-1] - observed[0],
        "mean": sum(observed) / len(observed),
    }


def _read_rate_family(
    metrics: Sequence[str],
    kwargs: dict[str, Any],
    *,
    interval_s: float,
) -> dict[str, float]:
    """Sample all requested rate metrics with a single shared sleep for the tick."""
    values: dict[str, float] = {}
    need_cpu = bool(_CPU_RATE_METRICS.intersection(metrics))
    need_net = bool(_NET_RATE_METRICS.intersection(metrics))
    need_disk = bool(_DISK_RATE_METRICS.intersection(metrics))
    if not (need_cpu or need_net or need_disk):
        return values

    cpu_first = cpu_times() if need_cpu else None
    net_first: NetworkInterface | None = None
    net_started = 0.0
    if need_net:
        net_first = network_interface(_require_iface(kwargs), include_counters=True)
        net_started = time.monotonic()
    disk_first: tuple[int, int, int, int] | None = None
    disk_started = 0.0
    if need_disk:
        disk_first = diskstats_row(_require_device(kwargs))
        disk_started = time.monotonic()

    time.sleep(max(0.01, interval_s))

    if need_cpu and cpu_first is not None:
        # CPU percent uses counter deltas, not this wall-clock window.
        cpu = cpu_utilization_from_samples(cpu_first, cpu_times())
        if "cpu_percent" in metrics:
            values["cpu_percent"] = cpu.percent
    if need_net and net_first is not None:
        net_second = network_interface(_require_iface(kwargs), include_counters=True)
        net_elapsed = time.monotonic() - net_started
        net = net_rates_from_samples(
            net_first,
            net_second,
            interval_s=net_elapsed,
        )
        if "net.rx_bps" in metrics:
            values["net.rx_bps"] = net.rx_bps
        if "net.tx_bps" in metrics:
            values["net.tx_bps"] = net.tx_bps
    if need_disk and disk_first is not None:
        device = _require_device(kwargs)
        disk_second = diskstats_row(device)
        disk_elapsed = time.monotonic() - disk_started
        disk = disk_rates_from_samples(
            disk_first,
            disk_second,
            device=device,
            interval_s=disk_elapsed,
        )
        if "disk.read_bps" in metrics:
            values["disk.read_bps"] = disk.read_bps
        if "disk.write_bps" in metrics:
            values["disk.write_bps"] = disk.write_bps
    return values


def _run_sampler(
    *,
    metrics: Sequence[str],
    interval_s: float,
    duration_s: float,
    path: Path,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    unknown = [name for name in metrics if name not in _METRIC_READERS]
    if unknown:
        raise ValueError(f"unsupported sample metrics: {unknown}")
    if duration_s <= 0:
        raise ValueError("duration_s must be > 0")
    if interval_s <= 0:
        raise ValueError("interval_s must be > 0")

    series: dict[str, list[float | None]] = {name: [] for name in metrics}
    started = time.perf_counter()
    path.parent.mkdir(parents=True, exist_ok=True)
    has_rates = bool(_RATE_METRICS.intersection(metrics))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["elapsed_s", "metric", "value"])
        sample_index = 0
        while True:
            elapsed = time.perf_counter() - started
            if elapsed > duration_s and sample_index > 0:
                break

            tick_started = time.perf_counter()
            tick_values: dict[str, float | None] = {}
            for name in metrics:
                if name in _GAUGE_METRICS:
                    tick_values[name] = _METRIC_READERS[name](kwargs)

            if has_rates:
                tick_values.update(_read_rate_family(metrics, kwargs, interval_s=interval_s))
            else:
                remaining_after_gauges = interval_s - (time.perf_counter() - tick_started)
                if remaining_after_gauges > 0:
                    time.sleep(remaining_after_gauges)

            for name in metrics:
                value = tick_values[name]
                series[name].append(value)
                if value is None:
                    # Blank cell: the sample was unavailable, not a measured number.
                    writer.writerow([f"{elapsed:.3f}", name, ""])
                else:
                    writer.writerow([f"{elapsed:.3f}", name, f"{value:.6f}"])

            sample_index += 1
            elapsed = time.perf_counter() - started
            if elapsed >= duration_s:
                break

    summaries = {
        name: summary
        for name, values in series.items()
        if (summary := _summarize(values)) is not None
    }
    return {
        "path": str(path),
        "samples": sample_index,
        "duration_s": round(time.perf_counter() - started, 3),
        "metrics": list(metrics),
        "summaries": summaries,
    }


@command
def capture(
    *,
    key: str,
    metrics: Sequence[str] = ("memory_available_mb", "cpu_percent"),
    interval_s: float = 1.0,
    duration_s: float = 10.0,
    path: str | None = None,
    pid: int | None = None,
    iface: str | None = None,
    device: str | None = None,
    zone: int = 0,
) -> dict[str, Any]:
    """Sample host metrics for a duration, write a CSV artifact, and return summaries.

    Metrics ``net.rx_bps``, ``net.tx_bps``, ``disk.read_bps``, and
    ``disk.write_bps`` use bytes per second. Check the platform matrix for
    Linux-only metrics. Verify capture summaries with the ``verify_*`` APIs.


    Preferred for embedded capture: one CSV artifact instead of thousands of SQLite rows.
    Supported metric names are listed by ``available_metrics()``. Requires
    artifacts enabled. CSV is saved as a file; compact summary measurements
    use ``{key}.{metric}`` keys, without a CSV artifact-index measurement.

    When ``path`` is omitted, the file is ``host_sample_{key}.csv`` so two
    captures with different evidence keys do not overwrite each other. An
    explicit ``path`` is used as given and replaces any existing file there.

    Rate metrics (``cpu_percent``, ``net.*``, ``disk.*``) share a single
    ``interval_s`` sleep per tick so wall time stays near ``interval_s``, not
    ``N * nested_interval``. Byte and I/O rates divide by the monotonic time
    between the two snapshots. CPU percent still uses counter deltas.

    Unavailable gauge samples (``proc.fd_count`` when ``/proc/<pid>/fd`` cannot
    be read) are blank in the CSV and omitted from summaries. A metric with no
    observed samples is left out of ``summaries`` and is not recorded, so a
    later summary verifier reports a missing measurement instead of a numeric
    pass. A measured zero is kept.

    :param key: Evidence key used for the command row, summary measurements,
        and the default CSV name.
    :type key: str
    :param metrics: Metric names to sample.
    :type metrics: Sequence[str], optional
    :param interval_s: Seconds between samples (also the requested rate window).
    :type interval_s: float, optional
    :param duration_s: Total sampling duration in seconds.
    :type duration_s: float, optional
    :param path: Relative artifact path under the run directory. Omit it to
        write ``host_sample_{key}.csv``. Pass a path to choose the file,
        including when that file should be overwritten.
    :type path: str | None, optional
    :param pid: Process id for ``proc.*`` metrics.
    :type pid: int | None, optional
    :param iface: Interface name for ``net.*`` metrics.
    :type iface: str | None, optional
    :param device: Block device name for ``disk.*`` metrics (for example ``mmcblk0``).
    :type device: str | None, optional
    :param zone: Thermal zone index for ``temp_c``.
    :type zone: int, optional

    :returns: Capture result with path, sample count, and per-metric summaries.
    :rtype: dict[str, Any]


    Pair with verify_max/verify_delta_max using the full summary key, or with
    verify_cpu_max_percent/verify_rss_delta_mb using the capture key.
    See the telemetry workflow and platform matrix.
    """
    artifact_path = resolve_artifact_path(path if path is not None else f"host_sample_{key}.csv")
    _logger.debug(
        "Host sample capture key=%s metrics=%s interval_s=%s duration_s=%s path=%s",
        key,
        tuple(metrics),
        interval_s,
        duration_s,
        artifact_path,
    )
    kwargs: dict[str, Any] = {"zone": zone}
    if pid is not None:
        kwargs["pid"] = pid
    if iface is not None:
        kwargs["iface"] = iface
    if device is not None:
        kwargs["device"] = device
    result = _run_sampler(
        metrics=tuple(metrics),
        interval_s=interval_s,
        duration_s=duration_s,
        path=Path(artifact_path),
        kwargs=kwargs,
    )
    # Persist compact numeric summaries as measurements for verifiers.
    for metric_name, summary in result["summaries"].items():
        measure_summary(
            key=f"{key}.{metric_name}",
            metric=metric_name,
            summary=summary,
        )
    return result


@measurement
def measure_summary(*, key: str, metric: str, summary: dict[str, float]) -> dict[str, Any]:
    """Record a sampler summary dictionary (min/max/last/delta/mean).

    Normally called by ``capture``; exposed for tests and custom samplers.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param metric: Metric name the summary describes.
    :type metric: str
    :param summary: Summary mapping with ``min``, ``max``, ``last``, ``delta``, ``mean``.
    :type summary: dict[str, float]

    :returns: Summary mapping including ``metric``.
    :rtype: dict[str, Any]
    """
    _ = key
    payload: dict[str, Any] = dict(summary)
    payload["metric"] = metric
    return payload


def _summary_field(row_value: object, field: str) -> float | None:
    if not isinstance(row_value, dict) or field not in row_value:
        return None
    return float(row_value[field])


@verification
def verify_delta_max(
    *,
    key: str,
    maximum: float,
    optional: bool = False,
) -> VerificationResult:
    """Verify ``delta`` from a prior ``measure_summary`` is at most ``maximum``.

    Use with sampler keys such as ``{capture_key}.proc.rss_mb`` for leak hunts.

    :param key: Measurement key shared with ``measure_summary``.
    :type key: str
    :param maximum: Maximum allowed delta.
    :type maximum: float
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    from colosseum.context import get_context
    from colosseum.decorators import missing_measurement_result

    row = get_context().db.get_measurement(
        _DOMAIN, "sample.measure_summary", key, row_index=0,
    )
    if row is None or row.value is None:
        return missing_measurement_result(key=key, optional=optional)
    actual = _summary_field(row.value, "delta")
    if actual is None:
        return VerificationResult(
            status="ERROR",
            message="summary measurement missing delta",
            optional=optional,
            actual=row.value,
        )
    if actual <= maximum:
        return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
    return VerificationResult(
        status="FAIL",
        message=f"expected delta <= {maximum}, got {actual}",
        optional=optional,
        actual=actual,
    )


@verification
def verify_max(
    *,
    key: str,
    maximum: float,
    optional: bool = False,
) -> VerificationResult:
    """Verify ``max`` from a prior ``measure_summary`` is at most ``maximum``.

    :param key: Measurement key shared with ``measure_summary``.
    :type key: str
    :param maximum: Maximum allowed peak value.
    :type maximum: float
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    from colosseum.context import get_context
    from colosseum.decorators import missing_measurement_result

    row = get_context().db.get_measurement(
        _DOMAIN, "sample.measure_summary", key, row_index=0,
    )
    if row is None or row.value is None:
        return missing_measurement_result(key=key, optional=optional)
    actual = _summary_field(row.value, "max")
    if actual is None:
        return VerificationResult(
            status="ERROR",
            message="summary measurement missing max",
            optional=optional,
            actual=row.value,
        )
    if actual <= maximum:
        return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
    return VerificationResult(
        status="FAIL",
        message=f"expected max <= {maximum}, got {actual}",
        optional=optional,
        actual=actual,
    )


@verification
def verify_rss_delta_mb(
    *,
    key: str,
    maximum: float,
    optional: bool = False,
) -> VerificationResult:
    """Verify RSS delta for a capture key (expects ``{key}.proc.rss_mb`` summary).

    :param key: Capture key passed to ``capture`` (not the full summary key).
    :type key: str
    :param maximum: Maximum allowed RSS growth in megabytes.
    :type maximum: float
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    return verify_delta_max(key=f"{key}.proc.rss_mb", maximum=maximum, optional=optional)


@verification
def verify_temp_max_c(
    *,
    key: str,
    maximum: float,
    optional: bool = False,
) -> VerificationResult:
    """Verify peak temperature for a capture key (expects ``{key}.temp_c`` summary).

    :param key: Capture key passed to ``capture``.
    :type key: str
    :param maximum: Maximum allowed temperature in Celsius.
    :type maximum: float
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    return verify_max(key=f"{key}.temp_c", maximum=maximum, optional=optional)


@verification
def verify_cpu_max_percent(
    *,
    key: str,
    maximum: float,
    optional: bool = False,
) -> VerificationResult:
    """Verify peak CPU percent for a capture key (expects ``{key}.cpu_percent`` summary).

    :param key: Capture key passed to ``capture``.
    :type key: str
    :param maximum: Maximum allowed CPU percent.
    :type maximum: float
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    return verify_max(key=f"{key}.cpu_percent", maximum=maximum, optional=optional)
