# Colosseum Host

First-party Colosseum plugin providing `col.host.*` (bench PC prerequisites).

## Install

```bash
pip install colosseum-host
```

The default install includes the runtime dependencies used for VISA backend
reporting and serial-port enumeration. A system VISA implementation (such as
NI-VISA or Keysight IO Libraries) is still required to inspect that vendor's
VISA backend.

## Usage

```python
import colosseum as col

col.config.load_config("examples/configs/bench.host.sim.toml")
col.host.system.measure_python_version(key="py")
col.endex()
```

## Develop

```bash
pip install -e ../colosseum-core
pip install -e ".[test,static]"
python -m pytest
ruff check colosseum_host tests examples
mypy
```
