"""Portable local-PC prerequisite check; reads real host facts, not a simulator.

Run from this repository root::

    colosseum run examples/bench_check.py -g examples/configs/config.host.example.toml

Expected: three measurements, three PASS verifications, and the normal core
evidence files. Disk and memory thresholds describe this bench, not a DUT.
"""

from __future__ import annotations

from pathlib import Path

import colosseum as col


def main() -> None:
    col.config.load_config(str(Path(__file__).with_name("configs") / "config.host.example.toml"))
    col.host.system.measure_python_version(key="py")
    col.host.system.verify_python_version(key="py")
    col.host.system.measure_disk_free_gb(key="disk")
    col.host.system.verify_disk_free_gb(key="disk")
    col.host.system.measure_memory_available_mb(key="memory")
    col.host.system.verify_memory_available_mb(key="memory")


if __name__ == "__main__":
    main()
    col.endex()
