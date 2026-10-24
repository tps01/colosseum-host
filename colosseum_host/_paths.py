"""Output path helpers for host plugin artifacts."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from colosseum.context import get_context
from colosseum.runner.paths import ensure_output_dir

if TYPE_CHECKING:
    from pathlib import Path


def resolve_artifact_path(relative_path: str) -> Path:
    ctx = get_context()
    output_dir = ensure_output_dir(ctx, logical_name=ctx.test_case_name)
    root = output_dir.resolve()
    candidate = (output_dir / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Artifact path must remain inside the active output directory")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return cast("Path", candidate)
