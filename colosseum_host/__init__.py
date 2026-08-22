"""Colosseum host plugin (bench PC prerequisites and local telemetry)."""

__colosseum_domain__ = "host"

__version__ = "0.3.1"

from colosseum.config.sections import ConfigSectionSpec
from colosseum.logging import get_logger
from colosseum.plugins.registry import PluginRegistry

_logger = get_logger("colosseum.host")


def register(registry: PluginRegistry) -> None:
    from colosseum_host import api

    registry.register_namespace("host", api)
    _logger.debug("Registered col.host namespace")
    registry.register_config_section(
        ConfigSectionSpec(
            "host.profile",
            "profile_id",
            required_keys=(),
            optional_keys=(
                "min_disk_gb",
                "min_memory_mb",
                "python_version_prefix",
                "platform",
                "disk_path",
            ),
        )
    )
