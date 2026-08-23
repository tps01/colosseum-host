"""Host network identity and counters (``col.host.net``)."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import VerificationResult, measurement, verification
from colosseum.logging import get_logger

from colosseum_host.host.collectors import list_network_interfaces, net_rates, network_interface
from colosseum_host.host.network_bindings import list_ipv4_network_bindings

_DOMAIN = "host"
_logger = get_logger("colosseum.host")


@measurement
def measure_bindings(*, key: str, include_loopback: bool = False) -> list[dict[str, str | int]]:
    """Record local IPv4 address/subnet bindings.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param include_loopback: Include loopback addresses when ``True``.
    :type include_loopback: bool, optional

    :returns: List of binding dicts with ``interface``, ``address``, ``network``, ``prefix``.
    :rtype: list[dict[str, str | int]]
    """
    _ = key
    bindings = [
        binding.as_dict()
        for binding in list_ipv4_network_bindings(include_loopback=include_loopback)
    ]
    _logger.debug(
        "IPv4 bindings count=%s include_loopback=%s",
        len(bindings),
        include_loopback,
    )
    return bindings


@measurement
def measure_interfaces(*, key: str, include_loopback: bool = False) -> list[dict[str, Any]]:
    """Record local network interfaces as a list of dictionaries.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param include_loopback: Include loopback interfaces when ``True``.
    :type include_loopback: bool, optional

    :returns: List of interface dictionaries (name, MAC, IPs, counters).
    :rtype: list[dict[str, Any]]
    """
    _ = key
    return [
        iface.as_dict()
        for iface in list_network_interfaces(include_loopback=include_loopback)
    ]


@measurement
def measure_interface(*, key: str, iface: str) -> dict[str, Any]:
    """Record a single network interface snapshot.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param iface: Interface name (for example ``eth0``).
    :type iface: str

    :returns: Interface dictionary.
    :rtype: dict[str, Any]
    """
    _ = key
    return network_interface(iface).as_dict()


@measurement
def measure_mac(*, key: str, iface: str) -> str:
    """Record the MAC address for an interface.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param iface: Interface name.
    :type iface: str

    :returns: MAC address string, or empty string if unavailable.
    :rtype: str
    """
    _ = key
    return network_interface(iface, include_counters=False).mac or ""


@measurement
def measure_ipv4(*, key: str, iface: str) -> list[str]:
    """Record IPv4 addresses for an interface.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param iface: Interface name.
    :type iface: str

    :returns: List of IPv4 address strings.
    :rtype: list[str]
    """
    _ = key
    return list(network_interface(iface, include_counters=False).ipv4 or [])


@measurement
def measure_ipv6(*, key: str, iface: str) -> list[str]:
    """Record IPv6 addresses for an interface.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param iface: Interface name.
    :type iface: str

    :returns: List of IPv6 address strings.
    :rtype: list[str]
    """
    _ = key
    return list(network_interface(iface, include_counters=False).ipv6 or [])


@measurement
def measure_operstate(*, key: str, iface: str) -> str:
    """Record interface operational state.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param iface: Interface name.
    :type iface: str

    :returns: Operstate string (for example ``up`` / ``down``), or empty.
    :rtype: str
    """
    _ = key
    return network_interface(iface, include_counters=False).operstate or ""


@measurement
def measure_counters(*, key: str, iface: str) -> dict[str, int | None]:
    """Record rx/tx byte, packet, error, and drop counters for an interface.

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param iface: Interface name.
    :type iface: str

    :returns: Counter mapping.
    :rtype: dict[str, int | None]
    """
    _ = key
    data = network_interface(iface, include_counters=True).as_dict()
    return {
        name: data.get(name)
        for name in (
            "rx_bytes",
            "tx_bytes",
            "rx_packets",
            "tx_packets",
            "rx_errors",
            "tx_errors",
            "rx_dropped",
            "tx_dropped",
        )
    }


@measurement
def measure_rates(*, key: str, iface: str, interval_s: float = 0.2) -> dict[str, Any]:
    """Record interface byte/packet rates over a short interval (Linux only).

    :param key: Unique measurement key within domain ``host``.
    :type key: str
    :param iface: Interface name.
    :type iface: str
    :param interval_s: Sample interval in seconds.
    :type interval_s: float, optional

    :returns: Rate mapping including error/drop totals at end of interval.
    :rtype: dict[str, Any]
    """
    _ = key
    return net_rates(iface=iface, interval_s=interval_s).as_dict()


@verification
def verify_operstate_up(
    *,
    key: str,
    optional: bool = False,
) -> VerificationResult:
    """Verify a prior ``measure_operstate`` result is ``up``.

    :param key: Measurement key shared with ``measure_operstate``.
    :type key: str
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    from colosseum.context import get_context
    from colosseum.decorators import missing_measurement_result

    row = get_context().db.get_measurement(_DOMAIN, "net.measure_operstate", key, row_index=0)
    if row is None or row.value is None:
        return missing_measurement_result(key=key, optional=optional)
    actual = str(row.value)
    if actual == "up":
        return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
    return VerificationResult(
        status="FAIL",
        message=f"expected operstate 'up', got {actual!r}",
        optional=optional,
        actual=actual,
    )


@verification
def verify_rx_errors(
    *,
    key: str,
    maximum: int = 0,
    optional: bool = False,
) -> VerificationResult:
    """Verify ``rx_errors`` from a prior ``measure_counters`` is at most ``maximum``.

    :param key: Measurement key shared with ``measure_counters``.
    :type key: str
    :param maximum: Maximum allowed receive errors (default ``0``).
    :type maximum: int, optional
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    from colosseum.context import get_context
    from colosseum.decorators import missing_measurement_result

    row = get_context().db.get_measurement(_DOMAIN, "net.measure_counters", key, row_index=0)
    if row is None or row.value is None:
        return missing_measurement_result(key=key, optional=optional)
    value = row.value
    if not isinstance(value, dict) or value.get("rx_errors") is None:
        return VerificationResult(
            status="ERROR",
            message="counters measurement missing rx_errors",
            optional=optional,
            actual=value,
        )
    actual = int(value["rx_errors"])
    if actual <= maximum:
        return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
    return VerificationResult(
        status="FAIL",
        message=f"expected rx_errors <= {maximum}, got {actual}",
        optional=optional,
        actual=actual,
    )
