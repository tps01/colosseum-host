# Colosseum Host

First-party Colosseum plugin providing `col.host.*` for bench-PC prerequisites
and Linux-first local telemetry (identity, gauges, and interval sampling).

## Install

```bash
pip install colosseum-host
```

This requires `colosseum-core` 0.16.4+ and registers the `host` namespace
through the `colosseum.plugins` entry point.

The default install always includes `pyserial` and `pyvisa` (packaging policy).
A system VISA implementation (such as NI-VISA or Keysight IO Libraries) is what
is optional: without a vendor VISA library you can still use
`col.host.system`, `col.host.net`, `col.host.proc`, and `col.host.sample`.
`col.host.bench.measure_visa_backend` needs the vendor stack to inspect that
backend.

## Platform capability

| Area | Windows | Linux |
| --- | --- | --- |
| Identity (python/platform/hostname/cpu count) | yes | yes |
| Disk free / memory gauges | yes | yes |
| Serial port list / IPv4 bindings / iface identity | yes | yes |
| VISA backend probe | yes (vendor VISA optional) | yes (vendor VISA optional) |
| Load average, thermal, process/CPU/vmstat rates | `HostCapabilityError` | yes |
| Sample rate metrics (`cpu_percent`, `net.*`, `disk.*`) | `HostCapabilityError` | yes |

Linux-only APIs stay on the public surface; on Windows they raise
`colosseum_host.exceptions.HostCapabilityError` with a clear message.

## `[host.profile]` defaults

Optional keys in `[host.profile]` supply threshold defaults when verify kwargs
are omitted (explicit kwargs still win):

| Key | Used by |
| --- | --- |
| `min_disk_gb` | `col.host.system.verify_disk_free_gb` |
| `min_memory_mb` | `col.host.system.verify_memory_available_mb` |
| `python_version_prefix` | `col.host.system.verify_python_version` |
| `platform` | `col.host.system.verify_platform` |
| `disk_path` | `col.host.config.capture_host_profile` (default path) |

Read the section with `col.host.config.get_profile(profile_id=…)`.

## Usage

```python
import colosseum as col

col.config.load_config("examples/configs/config.host.sim.toml")
col.host.system.measure_python_version(key="py")
col.host.net.measure_mac(key="eth0", iface="eth0")
col.host.net.measure_bindings(key="bindings")
col.host.config.capture_host_profile(path="host_profile.json")
col.endex()
```

Sample metrics while an external workload runs (stress-ng, iperf, …):

```python
col.host.sample.capture(
    key="stress",
    metrics=("memory_available_mb", "cpu_percent", "temp_c", "proc.rss_mb"),
    interval_s=1.0,
    duration_s=60.0,
    pid=app_pid,
)
col.host.sample.verify_rss_delta_mb(key="stress", maximum=8.0)
```

Each sampler tick waits about `interval_s` once. Rate metrics that need an
interval (`cpu_percent`, `net.*`, `disk.*`) share that single sleep per tick
instead of nesting one sleep per metric.

## Expected artifacts

Normal CLI runs write `summary.json`, `summary.txt`, `execution.sqlite`, and
`debug.log` under the run output directory. When metadata is loaded (see
`examples/configs/metadata.yaml`), core also emits a WATS-format
`wats_<datetime>_<script>.json` report alongside those files.

## Develop

```bash
pip install -e ../colosseum-core
pip install -e .
python -m pytest
ruff check colosseum_host tests examples
mypy
```
