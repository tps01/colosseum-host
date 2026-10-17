"""Host plugin errors."""

from __future__ import annotations


class HostError(RuntimeError):
    """Base error for colosseum-host."""


class HostCapabilityError(HostError):
    """Raised when a host API is unavailable on the current platform."""
