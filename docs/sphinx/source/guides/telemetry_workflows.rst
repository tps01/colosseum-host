Host prerequisite and telemetry workflows
=========================================

The host plugin reads the **real local machine**. The historical
``config.host.sim.toml`` filename supplies thresholds, not synthetic readings.
Run the portable prerequisite script from the repository root::

   colosseum run examples/bench_check.py -g examples/configs/config.host.sim.toml

.. literalinclude:: ../../../../examples/bench_check.py
   :language: python

The expected result is three measurement/verification pairs, using Python 3.x,
at least 1 GB of disk and 256 MB of available memory. These are example bench
requirements; adjust the profile to your station. Verifiers use the first
configured profile. ``get_profile(profile_id=...)`` selects a profile for your
own code, but ``verify_*`` calls do not accept ``profile_id``. Explicit limits
override defaults, e.g. ``verify_disk_free_gb(key="disk", minimum=5.0)``.

Discover interfaces before selecting one
----------------------------------------

Inside a configured procedure (Windows or Linux)::

   col.host.net.measure_interfaces(key="interfaces")
   col.host.net.measure_bindings(key="bindings")
   col.host.config.capture_host_profile(path="host/profile.json")

Inspect the returned interface rows or SQLite before choosing ``iface``. Linux
``eth0`` is only an example; Windows adapter names differ. Profile capture saves
JSON and returns its active-run path in the command result. It does not create
a measurement artifact-index row. File captures require artifacts enabled;
ordinary system measurements can run with ``--no-artifacts``.

Process sampling (Linux)
------------------------

This complete ``main`` starts and cleans up its own workload, so the PID is
defined and remains alive during collection. Put it in a script importing
``subprocess``, ``sys``, and ``colosseum as col``; run through the CLI with the
profile above. The sleeping Python process is expected to stay below 8 threads
and an 8 MB RSS delta in this short example::

   def main() -> None:
       with subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"]) as workload:
           try:
               col.host.proc.measure_info(key="workload", pid=workload.pid)
               col.host.proc.measure_rss_mb(key="rss", pid=workload.pid)
               col.host.sample.capture(key="idle", metrics=("proc.rss_mb", "proc.threads"), pid=workload.pid, interval_s=0.2, duration_s=1.0, path="host/idle.csv")
               col.host.sample.verify_rss_delta_mb(key="idle", maximum=8.0)
               col.host.sample.verify_max(key="idle.proc.threads", maximum=8.0)
           finally:
               workload.terminate()

Use ``pid=`` for a known process, or ``comm=`` when the process name is unique.
A process that exits or a name matching multiple processes cannot provide a
reliable sample. ``available_metrics()`` lists accepted metric strings, not a
promise of support on every OS.

Rate windows and summary keys (Linux)
-------------------------------------

With an existing interface and block device, use their Linux names (for example
``iface="eth0"``, ``device="nvme0n1"`` after checking your machine)::

   col.host.net.measure_counters(key="link_counters", iface="eth0")
   col.host.net.verify_rx_errors(key="link_counters", maximum=0)
   col.host.net.measure_rates(key="link_rates", iface="eth0", interval_s=0.2)
   col.host.sample.capture(key="traffic", metrics=("cpu_percent", "net.rx_bps", "net.tx_bps", "disk.read_bps", "disk.write_bps"), iface="eth0", device="nvme0n1", interval_s=1.0, duration_s=5.0, path="host/traffic.csv")
   col.host.sample.verify_cpu_max_percent(key="traffic", maximum=95.0)
   col.host.sample.verify_max(key="traffic.net.rx_bps", maximum=125000000.0)

Rate metrics share one interval wait per tick. ``*_bps`` here is **bytes per
second**, not bits per second. Sampler measurements use ``{capture_key}.{metric}``
and contain ``min``, ``max``, ``mean``, ``last`` and ``delta``. Generic
``verify_max`` / ``verify_delta_max`` take that full key; convenience CPU/RSS/
temperature verifiers take the capture key and append the metric themselves.
The example's network maximum is a bench limit to tailor, not a throughput test.

CPU/process/rate/thermal APIs are Linux-first and raise ``HostCapabilityError``
on Windows when unsupported. ``temp_c`` also requires an existing thermal zone;
``proc.*`` needs a live PID, ``net.*`` an interface, and ``disk.*`` a block
device. None of these examples requires a VISA backend or contacts instruments.
