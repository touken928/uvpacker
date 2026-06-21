from __future__ import annotations

import re
from pathlib import Path

from .errors import ConfigError
from .models import ProjectConfig


def require_exact_minor_from_requires(requires_python: str | None) -> str:
    """Extract the X.Y minor version from a '==X.Y.*' requires-python spec."""
    if requires_python is None:
        raise ConfigError(
            "`project.requires-python` must be set and use the '==X.Y.*' format.",
        )

    m = re.fullmatch(r"==(\d+\.\d+)\.\*", requires_python.strip())
    if not m:
        raise ConfigError(
            "uvpack requires `project.requires-python` to be an exact minor "
            "constraint of the form '==X.Y.*', for example '==3.11.*'.",
        )
    return m.group(1)


def validate_script_name(name: str) -> None:
    invalid_chars = set('<>:"/\\|?*')
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if not name or name in {".", ".."}:
        raise ConfigError(f"Invalid script name {name!r} in pyproject.toml.")
    if any(ord(ch) < 32 for ch in name):
        raise ConfigError(
            f"Invalid script name {name!r}; launcher names must not contain control characters."
        )
    if any(ch in invalid_chars for ch in name):
        raise ConfigError(
            f"Invalid script name {name!r}; launcher names must be valid Windows filenames."
        )
    if name.endswith((" ", ".")):
        raise ConfigError(
            f"Invalid script name {name!r}; launcher names must not end with space or '.'."
        )
    if name.split(".", 1)[0].upper() in reserved_names:
        raise ConfigError(
            f"Invalid script name {name!r}; launcher names must not use reserved Windows device names."
        )


def validate_output_dir_name(name: str) -> None:
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ConfigError(
            f"Invalid project.name {name!r}; default output directory name must be a single path segment."
        )


def validate_output_dir(project_dir: Path, output_dir: Path) -> None:
    if output_dir == project_dir:
        raise ConfigError(
            f"Output directory must not be the project directory: {output_dir}"
        )
    if output_dir == Path(output_dir.anchor):
        raise ConfigError(f"Refusing to use filesystem root as output directory: {output_dir}")
    if output_dir in project_dir.parents:
        raise ConfigError(
            f"Output directory must not contain the project directory: {output_dir}"
        )


def validate_project_config(cfg: ProjectConfig) -> None:
    validate_output_dir_name(cfg.name)
    if not cfg.scripts:
        raise ConfigError(
            "No [project.scripts] or [project.gui-scripts] defined in pyproject.toml; "
            "at least one entry is required.",
        )
    names = [s.name for s in cfg.scripts]
    if len(names) != len(set(names)):
        raise ConfigError(
            "Duplicate script names between [project.scripts] and [project.gui-scripts]; "
            "each name must be unique.",
        )
    for script in cfg.scripts:
        validate_script_name(script.name)
    if not cfg.build_system:
        raise ConfigError(
            "No [build-system] table found in pyproject.toml; "
            "uvpack relies on it to reproduce the build environment.",
        )

    # Delegate requires-python format validation to the pure function so there is
    # a single source of truth for version constraints.
    require_exact_minor_from_requires(cfg.requires_python)


def validate_embeddable_file(root: str, relative_path: Path) -> None:
    unsupported_suffixes = {".pyd", ".dll", ".so", ".dylib"}
    if relative_path.suffix.lower() in unsupported_suffixes:
        from .errors import BuildError

        raise BuildError(
            "The project package cannot be embedded purely in-memory because "
            f"{relative_path.as_posix()!r} under root {root!r} is a native binary.",
        )
