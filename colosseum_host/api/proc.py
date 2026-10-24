"""Host process telemetry (``col.host.proc``)."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import VerificationResult, measurement, verification
from colosseum.logging import get_logger

from colosseum_host.api._verify import maximum_verifier
from colosseum_host.host.collectors import find_pids_by_comm, process_info

_DOMAIN = "host"
_logger = get_logger("colosseum.host")


def _resolve_pid(*, pid: int | None, comm: str | None) -> int:
    if pid is not None:
        _logger.debug("Resolved process pid=%s", pid)
        return int(pid)
    if comm is None:
        raise ValueError("either pid= or comm= is required")
    matches = find_pids_by_comm(comm)
    if not matches:
        raise OSError(f"no process found with comm={comm!r}")
    if len(matches) > 1:
        raise OSError(f"multiple processes found with comm={comm!r}: {matches}")
    _logger.debug("Resolved process comm=%s pid=%s", comm, matches[0])
    return matches[0]


@measurement
def measure_info(
    *,
    key: str,
    pid: int | None = None,
    comm: str | None = None,
) -> dict[str, Any]:
    """Record process RSS/threads/fd facts by pid or unique ``comm`` (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param pid: Process id.
    :type pid: int | None, optional
    :param comm: Process ``comm`` name when ``pid`` is omitted (must be unique).
    :type comm: str | None, optional

    :returns: Process info dictionary.
    :rtype: dict[str, Any]
    """
    _ = key
    return process_info(_resolve_pid(pid=pid, comm=comm)).as_dict()


@measurement
def measure_rss_mb(
    *,
    key: str,
    pid: int | None = None,
    comm: str | None = None,
) -> float:
    """Record process resident set size in megabytes (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param pid: Process id.
    :type pid: int | None, optional
    :param comm: Process ``comm`` name when ``pid`` is omitted (must be unique).
    :type comm: str | None, optional

    :returns: RSS in megabytes.
    :rtype: float
    """
    _ = key
    return process_info(_resolve_pid(pid=pid, comm=comm)).rss_mb


@measurement
def measure_threads(
    *,
    key: str,
    pid: int | None = None,
    comm: str | None = None,
) -> float:
    """Record process thread count (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param pid: Process id.
    :type pid: int | None, optional
    :param comm: Process ``comm`` name when ``pid`` is omitted (must be unique).
    :type comm: str | None, optional

    :returns: Thread count as float.
    :rtype: float
    """
    _ = key
    return float(process_info(_resolve_pid(pid=pid, comm=comm)).threads)


@measurement
def measure_fd_count(
    *,
    key: str,
    pid: int | None = None,
    comm: str | None = None,
) -> float | None:
    """Record open file-descriptor count for a process (Linux only).

    A count of zero is a real observation. When ``/proc/<pid>/fd`` cannot be
    read the result is ``None``; ``verify_fd_count`` then returns ERROR rather
    than comparing a sentinel to the limit.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param pid: Process id.
    :type pid: int | None, optional
    :param comm: Process ``comm`` name when ``pid`` is omitted (must be unique).
    :type comm: str | None, optional

    :returns: FD count as float, or ``None`` when unreadable.
    :rtype: float | None
    """
    _ = key
    count = process_info(_resolve_pid(pid=pid, comm=comm)).fd_count
    if count is None:
        return None
    return float(count)


@measurement
def measure_pids_by_comm(*, key: str, comm: str) -> list[int]:
    """List process ids matching a ``comm`` name (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param comm: Process ``comm`` name.
    :type comm: str

    :returns: Sorted list of matching pids.
    :rtype: list[int]
    """
    _ = key
    return find_pids_by_comm(comm)


verify_rss_mb = maximum_verifier(
    "measure_rss_mb",
    name="verify_rss_mb",
    unit="MB",
    domain=_DOMAIN,
)


@verification
def verify_fd_count(
    *,
    key: str,
    maximum: float,
    optional: bool = False,
) -> VerificationResult:
    """Require a prior ``measure_fd_count`` to be at most ``maximum``.

    Zero is a valid count. A missing row or a null value means the FD count
    was not observed and is ERROR, not a numeric pass.

    :param key: Measurement key shared with ``measure_fd_count``.
    :type key: str
    :param maximum: Maximum allowed open file descriptors.
    :type maximum: float
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    from colosseum.context import get_context
    from colosseum.decorators import missing_measurement_result

    row = get_context().db.get_measurement(_DOMAIN, "proc.measure_fd_count", key, row_index=0)
    if row is None:
        return missing_measurement_result(key=key, optional=optional)
    if row.value is None:
        return VerificationResult(
            status="ERROR",
            message="file-descriptor count unavailable",
            optional=optional,
            actual=None,
        )
    actual = float(str(row.value))
    if actual <= maximum:
        return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
    return VerificationResult(
        status="FAIL",
        message=f"expected <= {maximum}, got {actual}",
        optional=optional,
        actual=actual,
    )
