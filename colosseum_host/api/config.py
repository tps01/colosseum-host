"""Host configuration snapshots (``col.host.config``)."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import VerificationResult, command, verification
from colosseum.logging import get_logger

from colosseum_host._paths import resolve_artifact_path
from colosseum_host.host.profile import write_profile

_DOMAIN = "host"
_logger = get_logger("colosseum.host")
_PROFILE_SECTION = "host.profile"


def get_profile(*, profile_id: int | None = None) -> dict[str, Any]:
    """Return the ``[host.profile]`` section dict from the loaded config.

    When ``profile_id`` is omitted, returns the first registered profile item,
    or the raw section table when normalization has no items.

    :param profile_id: Optional ``profile_id`` from the config table.
    :type profile_id: int | None, optional

    :returns: Profile key/value mapping (empty when config is unloaded).
    :rtype: dict[str, Any]
    """
    from colosseum.context import get_context

    ctx = get_context()
    if ctx.config is None:
        return {}
    if profile_id is not None:
        from colosseum.config.loader import ConfigError

        try:
            return dict(ctx.config.get_item(_PROFILE_SECTION, profile_id))
        except ConfigError:
            return {}
    items = ctx.config.list_items(_PROFILE_SECTION)
    if items:
        return dict(items[0])
    section = ctx.config.get_section(_PROFILE_SECTION)
    if isinstance(section, dict):
        return dict(section)
    return {}


def profile_default(key: str, *, profile_id: int | None = None) -> object | None:
    """Return an optional ``[host.profile]`` value, or ``None`` when unset."""
    value = get_profile(profile_id=profile_id).get(key)
    return value if value not in ("", None) else None


@command
def capture_host_profile(*, path: str = "host_profile.json", disk_path: str | None = None) -> str:
    """Save host profile JSON and return its path in the command result.

    Requires artifacts enabled. The command result contains the path; this
    does not create an ``artifact_path`` measurement index row.

    :param path: Relative artifact path under the run directory.
    :type path: str, optional
    :param disk_path: Optional disk path for free-space measurement (default: cwd).
    :type disk_path: str | None, optional

    :returns: Resolved artifact path string.
    :rtype: str
    """
    artifact_path = resolve_artifact_path(path)
    resolved_disk = disk_path
    if resolved_disk is None:
        profile_disk = profile_default("disk_path")
        if profile_disk is not None:
            resolved_disk = str(profile_disk)
    _logger.debug(
        "Writing host profile artifact path=%s disk_path=%s",
        artifact_path,
        resolved_disk,
    )
    write_profile(str(artifact_path), disk_path=resolved_disk)
    return str(artifact_path)


@verification
def verify_bench_config_loaded(*, key: str, optional: bool = False) -> VerificationResult:
    """Verify ``col.config.load_config`` has been called for this run.

    :param key: Verification evidence key (not tied to a measurement source).
    :type key: str
    :param optional: When ``True``, FAIL does not fail the run at ``col.endex()``.
    :type optional: bool, optional

    :returns: VerificationResult with PASS or FAIL status.
    :rtype: VerificationResult
    """
    _ = key
    from colosseum.context import get_context

    ctx = get_context()
    if ctx.config_path is not None:
        return VerificationResult(status="PASS", message="", optional=optional)
    return VerificationResult(
        status="FAIL",
        message="config is not loaded (config_path is unset)",
        optional=optional,
    )
