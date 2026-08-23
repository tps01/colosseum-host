"""Host system facts and prerequisite verifiers (``col.host.system``)."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import VerificationResult, measurement, verification

from colosseum_host.api._verify import maximum_verifier, minimum_verifier
from colosseum_host.host.collectors import (
    common,
    cpu_utilization,
    disk_rates,
    loadavg,
    meminfo,
    memory_available_mb,
    thermal_temp_c,
    uname_release,
    uname_string,
    uptime_s,
    vmstat,
)

_DOMAIN = "host"


@measurement
def measure_python_version(*, key: str) -> str:
    """Record the interpreter version string.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: ``platform.python_version()`` value.
    :rtype: str
    """
    _ = key
    return common.python_version()


@measurement
def measure_platform(*, key: str) -> str:
    """Record ``platform.system()``.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Platform name string.
    :rtype: str
    """
    _ = key
    return common.platform_name()


@measurement
def measure_machine(*, key: str) -> str:
    """Record machine hardware type.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Machine identifier string.
    :rtype: str
    """
    _ = key
    return common.machine()


@measurement
def measure_hostname(*, key: str) -> str:
    """Record network hostname.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Hostname string.
    :rtype: str
    """
    _ = key
    return common.hostname()


@measurement
def measure_cpu_count(*, key: str) -> float:
    """Record logical CPU count.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: CPU count as float.
    :rtype: float
    """
    _ = key
    return common.cpu_count()


@measurement
def measure_cpu_model(*, key: str) -> str:
    """Record best-effort CPU model string.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: CPU model string, or empty string if unavailable.
    :rtype: str
    """
    _ = key
    return common.cpu_model() or ""


@measurement
def measure_uname(*, key: str) -> str:
    """Record a uname-style kernel/OS identity string.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Kernel/OS identity string.
    :rtype: str
    """
    _ = key
    return uname_string()


@measurement
def measure_kernel_release(*, key: str) -> str:
    """Record the kernel release string.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Kernel release (Linux) or OS version (Windows).
    :rtype: str
    """
    _ = key
    return uname_release()


@measurement
def measure_loadavg(*, key: str) -> dict[str, float]:
    """Record 1/5/15-minute load averages (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Mapping with ``load1``, ``load5``, and ``load15``.
    :rtype: dict[str, float]
    """
    _ = key
    return loadavg().as_dict()


@measurement
def measure_memory_available_mb(*, key: str) -> float:
    """Record available system memory.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Available memory in megabytes.
    :rtype: float
    """
    _ = key
    return memory_available_mb()


@measurement
def measure_meminfo(*, key: str) -> dict[str, float]:
    """Record total/available memory and swap usage.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Mapping with ``total_mb``, ``available_mb``, swap fields.
    :rtype: dict[str, float]
    """
    _ = key
    return meminfo().as_dict()


@measurement
def measure_disk_free_gb(*, key: str, path: str | None = None) -> float:
    """Record free disk space.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param path: Path to check (default: current working directory).
    :type path: str | None, optional

    :returns: Free space in gigabytes.
    :rtype: float
    """
    _ = key
    return common.disk_free_gb(path)


@measurement
def measure_uptime_s(*, key: str) -> float:
    """Record system uptime.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Uptime in seconds.
    :rtype: float
    """
    _ = key
    return uptime_s()


@measurement
def measure_thermal_temp_c(*, key: str, zone: int = 0) -> float:
    """Record a thermal zone temperature in Celsius (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param zone: Thermal zone index (default ``0``).
    :type zone: int, optional

    :returns: Temperature in degrees Celsius.
    :rtype: float
    """
    _ = key
    return thermal_temp_c(zone=zone)


@measurement
def measure_cpu_percent(*, key: str, interval_s: float = 0.2) -> float:
    """Record overall CPU utilization percent over a short interval (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param interval_s: Sample interval in seconds.
    :type interval_s: float, optional

    :returns: Busy CPU percentage.
    :rtype: float
    """
    _ = key
    return cpu_utilization(interval_s=interval_s).percent


@measurement
def measure_cpu_utilization(*, key: str, interval_s: float = 0.2) -> dict[str, float]:
    """Record CPU utilization breakdown over a short interval (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param interval_s: Sample interval in seconds.
    :type interval_s: float, optional

    :returns: Mapping with overall and per-state percentages.
    :rtype: dict[str, float]
    """
    _ = key
    return cpu_utilization(interval_s=interval_s).as_dict()


@measurement
def measure_vmstat(*, key: str) -> dict[str, int]:
    """Record selected ``/proc/vmstat`` counters (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Mapping with ``pgfault``, ``pgpgin``, ``pgpgout``, ``oom_kill``.
    :rtype: dict[str, int]
    """
    _ = key
    return vmstat().as_dict()


@measurement
def measure_disk_rates(
    *,
    key: str,
    device: str,
    interval_s: float = 0.2,
) -> dict[str, Any]:
    """Record block-device I/O rates over a short interval (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param device: Block device name (for example ``mmcblk0`` or ``sda``).
    :type device: str
    :param interval_s: Sample interval in seconds.
    :type interval_s: float, optional

    :returns: Mapping with read/write bps and iops.
    :rtype: dict[str, Any]
    """
    _ = key
    return disk_rates(device=device, interval_s=interval_s).as_dict()


verify_memory_available_mb = minimum_verifier(
    "measure_memory_available_mb",
    name="verify_memory_available_mb",
    unit="MB",
    domain=_DOMAIN,
)
verify_disk_free_gb = minimum_verifier(
    "measure_disk_free_gb",
    name="verify_disk_free_gb",
    unit="GB",
    domain=_DOMAIN,
)
verify_thermal_temp_c = maximum_verifier(
    "measure_thermal_temp_c",
    name="verify_thermal_temp_c",
    unit="C",
    domain=_DOMAIN,
)
verify_cpu_percent = maximum_verifier(
    "measure_cpu_percent",
    name="verify_cpu_percent",
    unit="%",
    domain=_DOMAIN,
)


@verification
def verify_python_version(
    *,
    key: str,
    version_prefix: str,
    optional: bool = False,
) -> VerificationResult:
    """Verify a prior ``measure_python_version`` result starts with a prefix.

    :param key: Measurement key shared with ``measure_python_version``.
    :type key: str
    :param version_prefix: Required version prefix (for example ``3.11``).
    :type version_prefix: str
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    from colosseum.context import get_context
    from colosseum.decorators import missing_measurement_result

    row = get_context().db.get_measurement(
        _DOMAIN, "system.measure_python_version", key, row_index=0
    )
    if row is None or row.value is None:
        return missing_measurement_result(key=key, optional=optional)
    actual = str(row.value)
    if actual.startswith(version_prefix):
        return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
    return VerificationResult(
        status="FAIL",
        message=f"expected python version prefix {version_prefix!r}, got {actual!r}",
        optional=optional,
        actual=actual,
    )


@verification
def verify_platform(
    *,
    key: str,
    expected_platform: str,
    optional: bool = False,
) -> VerificationResult:
    """Verify a prior ``measure_platform`` result matches exactly.

    :param key: Measurement key shared with ``measure_platform``.
    :type key: str
    :param expected_platform: Expected ``platform.system()`` string.
    :type expected_platform: str
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    from colosseum.context import get_context
    from colosseum.decorators import missing_measurement_result

    row = get_context().db.get_measurement(_DOMAIN, "system.measure_platform", key, row_index=0)
    if row is None or row.value is None:
        return missing_measurement_result(key=key, optional=optional)
    actual = str(row.value)
    if actual == expected_platform:
        return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
    return VerificationResult(
        status="FAIL",
        message=f"expected platform {expected_platform!r}, got {actual!r}",
        optional=optional,
        actual=actual,
    )


@verification
def verify_oom_kill(
    *,
    key: str,
    maximum: int = 0,
    optional: bool = False,
) -> VerificationResult:
    """Verify ``oom_kill`` from a prior ``measure_vmstat`` is at most ``maximum``.

    :param key: Measurement key shared with ``measure_vmstat``.
    :type key: str
    :param maximum: Maximum allowed OOM kill count (default ``0``).
    :type maximum: int, optional
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    from colosseum.context import get_context
    from colosseum.decorators import missing_measurement_result

    row = get_context().db.get_measurement(_DOMAIN, "system.measure_vmstat", key, row_index=0)
    if row is None or row.value is None:
        return missing_measurement_result(key=key, optional=optional)
    value: Any = row.value
    if not isinstance(value, dict) or "oom_kill" not in value:
        return VerificationResult(
            status="ERROR",
            message="vmstat measurement missing oom_kill",
            optional=optional,
            actual=value,
        )
    actual = int(value["oom_kill"])
    if actual <= maximum:
        return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
    return VerificationResult(
        status="FAIL",
        message=f"expected oom_kill <= {maximum}, got {actual}",
        optional=optional,
        actual=actual,
    )
