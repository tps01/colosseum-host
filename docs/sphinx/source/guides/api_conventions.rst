API conventions and failures
============================

Call public APIs through ``import colosseum as col`` and the documented
``col.*`` path. Signatures show defaults and keyword-only arguments (after
``*``). Omitted optional arguments use those defaults; a required argument has
no default. See each callable for its units and driver-specific restrictions.

Commands record actions and re-raise exceptions unless ``optional=True``.
Measurements record returned evidence under ``key``; an exception records a
null ERROR row and re-raises unless ``optional=True``, which returns ``None``.
Verification FAIL/ERROR/BLOCKED outcomes are recorded without aborting later
steps. ``optional=True`` excludes an outcome from the aggregate verdict; it
does not make a later dependent verification optional.

Under ``--dry-run``, OS identity measures (``measure_python_version``,
``measure_platform``, ``measure_machine``, ``measure_hostname``,
``measure_cpu_count``, ``measure_cpu_model``, ``measure_uname``,
``measure_kernel_release``) and ``verify_bench_config_loaded`` use
``dry_run="call"`` so the walk still records local facts. Capture, camera,
sampling, and other I/O stay on ``dry_run="log"``.

Keep measurement keys distinct for separate facts. Instrument IDs and channels
do not distinguish measurements with the same domain, command, key, and row
index. See `evidence and verification <https://tps01.github.io/colosseum-core/guides/measurements_verifications.html>`__
for lookup rules and complete failure examples.

The plugin uses Colosseum's standard run artifacts. See the
`output guide <https://tps01.github.io/colosseum-core/guides/output_artifacts.html>`__
for summaries and SQLite queries. Plugin captures require artifacts enabled.

See :doc:`telemetry_workflows` and the `platform matrix <../readme.html#platform-capability>`__
for Linux-only operations and rate units.
