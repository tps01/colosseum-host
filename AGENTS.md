# AGENTS.md

Baseline expectations for AI agents in this plugin repository.

## Purpose

- This is a first-party Colosseum plugin. Development, packaging, and usage
  follow the same entry-point specification as third-party plugins.
- Runtime dependencies are declared in `pyproject.toml`; depend only on
  `colosseum-core` (plugins must not depend on each other).
- User import remains `import colosseum as col`; this package registers
  namespaces via `colosseum.plugins`.

## Layout helpers

- `colosseum_host/host/network/`: shared Win/Linux adapter enumeration
  (`list_adapters`). Collectors build `NetworkInterface` rows; 
  `host/network_bindings` projects subnet strings. Do not re-duplicate
  GetAdaptersAddresses ctypes layouts or Linux ioctl helpers.
- `colosseum_host/api/_verify.py`: factory helpers for scalar measurement
  compares (`minimum_verifier` / `maximum_verifier`), including optional
  `[host.profile]` default keys.
- `colosseum_host/api/config.get_profile`: reads `[host.profile]` for verify
  threshold defaults and `disk_path`.
- `colosseum_host/exceptions.py`: `HostCapabilityError` for Linux-only ops on
  Windows (no stub catalogs of unsupported commands).
- Keep `_paths.py` local; do not move it into core.

## Change discipline

Prefer focused, compact changes. Do not commit unless asked. Read `RULES.md` at
task start.

## Footprint

Follow the workspace **Minimizing footprint** section (top-level `AGENTS.md`).
Inventory
existing code before adding files; prefer merge, relocate, or delete over new
modules.
Keep plugin-only helpers local (e.g. `_paths.py`, `_cache.py`). Do not expand
core for
single-plugin needs.

## Workflow

When completing changes, increment the package version in `pyproject.toml` using
semantic versioning. Agents cannot increment the major number.

When finishing a development session: `python scripts/cleanup.py --dry-run`,
then
`python scripts/cleanup.py` if the list looks right. See workspace `AGENTS.md`
(**Simulated annealing**, **End-of-development cleanup**).
