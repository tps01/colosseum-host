Getting started
===============

Install the ``colosseum-host`` wheel into the same virtual environment as
``colosseum-core``. This plugin checks the **bench PC** (disk, memory, Python,
platform) and samples host telemetry.

1. Config
---------

::

   [host.profile]
   profile_id = 1
   min_disk_gb = 1
   min_memory_mb = 256

Profile keys feed the matching ``col.host.system.verify_*`` helpers. See
``examples/configs/config.host.sim.toml``.

2. Procedure + verification
---------------------------

::

   import colosseum as col

   def main() -> None:
       col.host.system.measure_python_version(key="py")
       col.host.system.verify_python_version(key="py")  # uses profile when set
       col.host.system.verify_disk_free_gb(profile_id=1)
       col.host.system.verify_memory_available_mb(profile_id=1)

Optional sampling while an external workload runs::

   col.host.sample.capture(
       key="stress",
       metrics=("memory_available_mb", "cpu_percent"),
       interval_s=1.0,
       duration_s=10.0,
   )

3. Run
------

::

   colosseum run bench_check.py -g config.host.sim.toml

A short copy-out stub is ``host/bench_prerequisites/`` in
`colosseum-library <https://github.com/tps01/colosseum-library>`__.
Framework docs: `core hub <https://tps01.github.io/colosseum-core/>`__.
