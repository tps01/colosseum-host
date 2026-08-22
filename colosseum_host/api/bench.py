"""Bench-runtime prerequisites (``col.host.bench``)."""

from __future__ import annotations

import pyvisa
from colosseum.decorators import VerificationResult, measurement, verification
from colosseum.logging import get_logger

from colosseum_host.host.collectors import serial_ports_csv

_DOMAIN = "host"
_logger = get_logger("colosseum.host")


@measurement
def measure_visa_backend(*, key: str) -> str:
    """Report the active PyVISA backend string.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: VISA backend identifier, or empty string if no backend can be opened.
    :rtype: str
    """
    _ = key
    try:
        rm = pyvisa.ResourceManager()
        backend = str(rm.visalib)
        _logger.debug("VISA backend=%s", backend)
        return backend
    except Exception:
        _logger.debug("VISA backend unavailable", exc_info=True)
        return ""


@measurement
def measure_serial_ports(*, key: str) -> str:
    """List serial ports as a comma-separated string.

    :param key: Unique measurement key within domain ``host``.
    :type key: str

    :returns: Comma-separated port names (platform-specific).
    :rtype: str
    """
    _ = key
    return serial_ports_csv()


@verification
def verify_visa_available(
    *,
    key: str,
    allow_sim: bool = True,
    optional: bool = False,
) -> VerificationResult:
    """Verify a prior ``measure_visa_backend`` result is non-empty and optionally not simulated.

    :param key: Measurement key shared with ``measure_visa_backend``.
    :type key: str
    :param allow_sim: When ``False``, fail if the backend name contains ``@sim``.
    :type allow_sim: bool, optional
    :param optional: When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS, FAIL, or ERROR status.
    :rtype: VerificationResult
    """
    from colosseum.context import require_context
    from colosseum.decorators import missing_measurement_result

    row = require_context().db.get_measurement(
        _DOMAIN, "bench.measure_visa_backend", key, row_index=0
    )
    if row is None or row.value is None:
        return missing_measurement_result(key=key, optional=optional)
    backend = str(row.value).strip()
    if not backend:
        return VerificationResult(
            status="FAIL",
            message="VISA backend is empty",
            optional=optional,
            actual=backend,
        )
    if not allow_sim and "@sim" in backend.lower():
        return VerificationResult(
            status="FAIL",
            message=(
                f"VISA backend {backend!r} is simulated; hardware suite requires a real backend"
            ),
            optional=optional,
            actual=backend,
        )
    return VerificationResult(status="PASS", message="", optional=optional, actual=backend)
