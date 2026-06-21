"""
Project-configuration helpers — loading, validating, and resolving paths.

Extracted from ``packer.py`` so that the orchestration module keeps only
``pack_project()`` / ``_perform_pack()`` as its stable spine.
"""

from __future__ import annotations

import pathlib

try:  # Python 3.11+
    import tomllib  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

from ..domain.errors import ConfigError
from ..domain.models import ProjectConfig, ScriptDefinition
from ..domain.rules import validate_output_dir


def load_project_config(pyproject_path: pathlib.Path) -> ProjectConfig:
    """Parse ``pyproject.toml`` and return a validated ``ProjectConfig``."""
    text = pyproject_path.read_bytes()
    if tomllib is None:
        raise ConfigError("tomllib is not available; Python 3.11+ is required.")

    data = tomllib.loads(text.decode("utf-8"))

    project = data.get("project") or {}
    name = project.get("name")
    if not isinstance(name, str) or not name:
        raise ConfigError("`project.name` must be set in pyproject.toml.")

    requires_python = project.get("requires-python")

    scripts_table = project.get("scripts") or {}
    scripts: list[ScriptDefinition] = []
    for key, value in scripts_table.items():
        if isinstance(value, str):
            scripts.append(ScriptDefinition(name=key, target=value, gui=False))

    gui_table = project.get("gui-scripts") or {}
    for key, value in gui_table.items():
        if isinstance(value, str):
            scripts.append(ScriptDefinition(name=key, target=value, gui=True))

    build_system = data.get("build-system") or {}

    return ProjectConfig(
        root=pyproject_path.parent,
        name=name,
        requires_python=requires_python,
        scripts=scripts,
        build_system=build_system,
    )


def require_project_dir(project_dir: pathlib.Path) -> pathlib.Path:
    """Verify *project_dir* exists and contains ``pyproject.toml``."""
    if not project_dir.is_dir():
        raise ConfigError(f"Project directory does not exist: {project_dir}")
    pyproject = project_dir / "pyproject.toml"
    if not pyproject.is_file():
        raise ConfigError(f"No pyproject.toml found in {project_dir}")
    return pyproject


def resolve_output_dir(
    project_name: str | ProjectConfig,
    project_dir: pathlib.Path,
    output_dir: pathlib.Path | None,
) -> pathlib.Path:
    """Resolve the final output directory, defaulting to ``dist/<name>``."""
    if isinstance(project_name, ProjectConfig):
        project_name = project_name.name
    if output_dir is not None:
        output_dir = output_dir.resolve()
        validate_output_dir(project_dir, output_dir)
        if output_dir == pathlib.Path.home():
            raise ConfigError(
                f"Refusing to use home directory as output directory: {output_dir}"
            )
        return output_dir

    dist_dir = project_dir / "dist"
    return dist_dir / project_name
