"""Blocking host metric sampler (``col.host.sample``)."""

from __future__ import annotations

import csv
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from colosseum.decorators import (
    VerificationResult,
    command,
    measurement,
    verification,
)
from colosseum.logging import get_logger

from colosseum_host._paths import resolve_artifact_path
from colosseum_host.host.collectors import (
    cpu_utilization,
    disk_rates,
    loadavg,
    meminfo,
    memory_available_mb,
    net_rates,
    process_info,
    thermal_temp_c,
    vmstat,
)

_DOMAIN = "host"
_logger = get_logger("colosseum.host")

_MetricFn = Callable[[dict[str, Any]], float]


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


def _cpu_percent(kwargs: dict[str, Any]) -> float:
    return cpu_utilization(interval_s=float(kwargs.get("cpu_interval_s", 0.1))).percent


_METRIC_READERS: dict[str, _MetricFn] = {
    "memory_available_mb": lambda _kw: memory_available_mb(),
    "mem_total_mb": lambda _kw: meminfo().total_mb,
    "swap_used_mb": lambda _kw: meminfo().swap_used_mb,
    "load1": lambda _kw: loadavg().load1,
    "temp_c": lambda kw: thermal_temp_c(zone=int(kw.get("zone", 0))),
    "cpu_percent": _cpu_percent,
    "proc.rss_mb": lambda kw: process_info(_require_pid(kw)).rss_mb,
    "proc.threads": lambda kw: float(process_info(_require_pid(kw)).threads),
    "proc.fd_count": lambda kw: float(process_info(_require_pid(kw)).fd_count or -1),
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


def _summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "max": 0.0, "last": 0.0, "delta": 0.0, "mean": 0.0}
    return {
        "min": min(values),
        "max": max(values),
        "last": values[-1],
        "delta": values[-1] - values[0],
        "mean": sum(values) / len(values),
    }


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

    series: dict[str, list[float]] = {name: [] for name in metrics}
    started = time.perf_counter()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["elapsed_s", "metric", "value"])
        sample_index = 0
        while True:
            elapsed = time.perf_counter() - started
            if elapsed > duration_s and sample_index > 0:
                break
            for name in metrics:
                value = float(_METRIC_READERS[name](kwargs))
                series[name].append(value)
                writer.writerow([f"{elapsed:.3f}", name, f"{value:.6f}"])
            sample_index += 1
            elapsed = time.perf_counter() - started
            if elapsed >= duration_s:
                break
            remaining = duration_s - elapsed
            time.sleep(min(interval_s, max(0.0, remaining)))

    summaries = {name: _summarize(values) for name, values in series.items()}
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
    path: str = "host_sample.csv",
    pid: int | None = None,
    iface: str | None = None,
    device: str | None = None,
    zone: int = 0,
) -> dict[str, Any]:
    """Sample host metrics for a duration, write a CSV artifact, and return summaries.

    Preferred for embedded capture: one CSV artifact instead of thousands of SQLite rows.
    Supported metric names are listed by ``available_metrics()``.

    :param key: Evidence key used for the command row and summary measurements.
    :type key: str
    :param metrics: Metric names to sample.
    :type metrics: Sequence[str], optional
    :param interval_s: Seconds between samples.
    :type interval_s: float, optional
    :param duration_s: Total sampling duration in seconds.
    :type duration_s: float, optional
    :param path: Relative artifact path under the run directory.
    :type path: str, optional
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
    """
    artifact_path = resolve_artifact_path(path)
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
