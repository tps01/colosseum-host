"""Unit-tier pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import colosseum.context as context_module
import pytest


@pytest.fixture
def ctx(tmp_path: Path) -> Iterator[context_module.RuntimeContext]:
    ctx = context_module.init_context(test_case_name="unit")
    ctx.output_dir = tmp_path
    ctx.db.initialize(tmp_path / "execution.sqlite")
    try:
        yield ctx
    finally:
        ctx.db.close()
