Config reference
================

A config row is one TOML table. One profile uses ``[host.profile]``. Use
``[[host.profile]]`` only when the sample shows two or more profile rows.
When the section is present, ``profile_id`` is required. No other key is
required. ``profile_default`` returns ``None`` when the value is missing or
an empty string.

host.profile
------------

.. code-block:: toml

   [host.profile]
   profile_id = 1                      # required integer id
   min_disk_gb = 1.0                   # optional; GB minimum for verify_disk_free_gb when minimum= is omitted
   min_memory_mb = 256                 # optional; MB minimum for verify_memory_available_mb when minimum= is omitted
   python_version_prefix = "3.11"      # optional; verify_python_version prefix when version_prefix= is omitted
   platform = "Windows"                # optional; exact platform.system() string for verify_platform
   disk_path = "."                     # optional; free-space path; disk_free_gb uses the current directory when unset

``verify_platform`` compares the measured ``platform.system()`` string with
``expected_platform`` or, when that argument is omitted, with this
``platform`` value. ``capture_host_profile`` uses ``disk_path`` from the
profile when its own ``disk_path`` argument is omitted.
