"""Launcher subsystem — template resolution and executable assembly."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any, cast

from ..domain.errors import ConfigError
from ._payload import _make_payload

TEMPLATE_CONSOLE = "console.exe"
TEMPLATE_GUI = "gui.exe"


def _get_package_dir() -> Path:
    return Path(cast(Any, resources.files(__package__)))


def get_template_exe(gui: bool) -> Path | None:
    """Return a prebuilt launcher template bundled with the wheel, if any."""
    pkg = _get_package_dir()
    name = TEMPLATE_GUI if gui else TEMPLATE_CONSOLE
    candidate = pkg / name
    return candidate if candidate.is_file() else None


def build_launcher_for_script(
    launchers_dir: Path,
    script_name: str,
    module: str,
    func: str | None,
    *,
    gui: bool = False,
    archive: bytes = b"",
) -> Path | None:
    """
    Build a Windows ``.exe`` launcher for a console or GUI script entry.

    Returns the path to the created launcher, or ``None`` if no template is
    available for the requested subsystem.
    """
    template = get_template_exe(gui=gui)
    if template is None:
        return None

    if Path(script_name).name != script_name or script_name in {"", ".", ".."}:
        raise ConfigError(f"Invalid script name {script_name!r} in pyproject.toml.")

    config = {
        "module": module,
        "func": func or "main",
    }
    base = template.read_bytes()
    payload = _make_payload(config, archive=archive)

    target = launchers_dir / f"{script_name}.exe"
    target.write_bytes(base + payload)
    return target
