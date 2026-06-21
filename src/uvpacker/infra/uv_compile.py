from __future__ import annotations

import pathlib

from .uv_client import _run_command


def run_uv_python(
    *,
    target_python_minor: str,
    cwd: pathlib.Path,
    python_args: list[str],
) -> None:
    """Run target-minor Python via ``uv run --no-project``."""
    cmd = [
        "uv",
        "run",
        "--no-project",
        "--python",
        target_python_minor,
        "python",
        *python_args,
    ]
    _run_command(cmd, cwd=cwd)
