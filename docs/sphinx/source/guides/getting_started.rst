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
   python_version_prefix = "3."

Profile keys feed the matching ``col.host.system.verify_*`` helpers. See
``examples/configs/config.host.sim.toml``.
Despite its historical filename, that file contains thresholds: host reads the
real local PC and has no simulation driver. Verifiers use the first profile;
explicit limit arguments override its defaults.

2. Procedure + verification
---------------------------

.. literalinclude:: ../../../../examples/bench_check.py
   :language: python

Optional sampling while an external workload runs (Linux; ``cpu_percent`` is
not supported on Windows)::

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
