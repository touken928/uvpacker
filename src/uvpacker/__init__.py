"""
uvpacker: Windows-oriented CLI packer for Python projects using uv and the
official Python Embedded Runtime.

This package exposes a single public entrypoint: :func:`main`, which is wired
from `pyproject.toml` via `[project.scripts]`.
"""

from __future__ import annotations

from importlib.metadata import version

# Set before importing submodules that transitively import `uvpacker.launcher`,
# which reads `__version__` for embedded exe metadata.
__version__ = version("uvpacker")

from .app.cli import main

__all__ = ["main", "__version__"]
