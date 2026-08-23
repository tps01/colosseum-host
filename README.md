# Colosseum Host

First-party Colosseum plugin providing `col.host.*` for bench-PC prerequisites
and Linux-first local telemetry (identity, gauges, and interval sampling).

## Install

```bash
pip install colosseum-host
```

The default install includes the runtime dependencies used for VISA backend
reporting and serial-port enumeration. A system VISA implementation (such as
NI-VISA or Keysight IO Libraries) is still required to inspect that vendor's
VISA backend. VISA is optional for embedded Linux capture; use `col.host.system`,
`col.host.net`, `col.host.proc`, and `col.host.sample` without it.

## Usage

```python
import colosseum as col

col.config.load_config("examples/configs/bench.host.sim.toml")
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

## Develop

```bash
pip install -e ../colosseum-core
pip install -e ".[test,static]"
python -m pytest
ruff check colosseum_host tests examples
mypy
```
