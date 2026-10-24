# Colosseum Host

## Documentation

API reference (GitHub Pages): https://tps01.github.io/colosseum-host/

Framework hub: https://tps01.github.io/colosseum-core/

First-party Colosseum plugin providing `col.host.*` for local-machine
prerequisites and Linux-first telemetry (identity, gauges, and interval
sampling)—useful on lab controllers, CI hosts, and embedded Linux targets alike.

## Install

Download the wheel from [GitHub Releases](https://github.com/tps01/colosseum-host/releases)
and install it in the same environment as core. Replace `<version>` with
the downloaded filename. For development, use `python -m pip install -e .`.

```bash
python -m pip install "./colosseum_host-<version>-py3-none-any.whl"
```

This requires `colosseum-core` `>=0.17.0,<0.18` and registers the `host` namespace
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
| Interface counters (`measure_counters`) | `HostCapabilityError` | yes |
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

Read a selected profile with `col.host.config.get_profile(profile_id=…)`.
System verifiers use the first profile when limits are omitted; they do not
accept `profile_id`. Explicit limit kwargs take priority.

## Usage

```python
import colosseum as col

col.config.load_config("examples/configs/config.host.sim.toml")
col.host.system.measure_python_version(key="py")
col.host.system.verify_python_version(key="py")
col.host.net.measure_interfaces(key="interfaces")
col.host.net.measure_bindings(key="bindings")
col.host.config.capture_host_profile(path="host_profile.json")
col.endex()
```

The config supplies thresholds for the real local host; its historical "sim"
filename does not imply a simulator. A portable, complete prerequisite check is
`colosseum run examples/bench_check.py -g examples/configs/config.host.sim.toml`.

On **Linux**, sample an existing external workload (set `app_pid` to its live PID
first; `temp_c` also requires a thermal zone):

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
instead of nesting one sleep per metric. Byte and I/O rates divide by the
monotonic time between snapshots, so a slow read is not reported as extra
throughput. CPU percent still comes from counter deltas.

Omitting `path` writes `host_sample_<key>.csv`, so captures with different
evidence keys keep separate series. Pass `path` to choose a file; that path
is overwritten when reused.

## Cameras

`col.host.camera` uses OpenCV (Apache 2.0) for local webcams on Windows and
Linux. The normal install includes `opencv-python-headless`; no GUI or external
video encoder is required. A working OS camera driver and device permissions
are required.

```python
col.host.camera.take_picture(path="camera.jpg", device=0)
col.host.camera.start_recording(path="camera.avi", device=0, fps=30.0)
try:
    # Run the operations you want to record here.
    col.host.system.measure_hostname(key="host")
finally:
    col.host.camera.stop_recording(device=0)
```

Pictures (JPEG/PNG) and MJPEG/AVI videos are saved under the active run output
directory. Paths are returned as command results. Reusing a path overwrites its
contents. Each camera supports one recording at a time; stop it before taking a
picture. Always stop recording before `col.endex()` so the file is finalized.
Camera read/open failures and snapshot write failures raise errors; recording
worker failures are raised by `stop_recording`. Frame rate is a target and
throughput depends on the camera and host. A stalled camera driver can delay
`stop_recording` until its pending read returns.

## Expected artifacts

Normal CLI runs write `summary.json`, `summary.txt`, `execution.sqlite`, and
`debug.log` under the run output directory. Reports are opt-in: add
`--report wats` to the run command to write `wats_<datetime>_<script>.json`,
or `--report junit` for `junit.xml`. Loading `metadata.yaml` enriches an
enabled report; it does not enable reporting. See the
[core reporting guide](https://tps01.github.io/colosseum-core/guides/output_artifacts.html).

## Develop

```bash
pip install -e ../colosseum-core
pip install -e .
python -m pytest
ruff check colosseum_host tests examples
mypy
```

See [telemetry workflows](https://tps01.github.io/colosseum-host/guides/telemetry_workflows.html)
for a complete subprocess/PID recipe, interface discovery, rate windows and
summary-key conventions.
