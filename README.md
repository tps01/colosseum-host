# Colosseum Host

First-party Colosseum plugin providing `col.host.*` (bench PC prerequisites).

## Install

```bash
pip install colosseum-core colosseum-shared
pip install -e ".[test]"
```

Requires `colosseum-core` 0.15.x and `colosseum-shared` 0.1.x.

## Usage

```python
import colosseum as col

col.config.load_config("examples/configs/bench.host.sim.toml")
col.host.system.measure_python_version(key="py")
col.endex()
```

## Develop

```bash
pip install -e ../colosseum-core -e ../colosseum-shared -e ".[test,static]"
pytest
```
