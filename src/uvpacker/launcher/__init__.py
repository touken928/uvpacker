from __future__ import annotations

import json
import struct
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

MAGIC = b"UVPKLAUN"
FOOTER_STRUCT = struct.Struct("<8sII")

TEMPLATE_CONSOLE = "console.exe"
TEMPLATE_GUI = "gui.exe"


def _get_package_dir() -> Path:
    return Path(resources.files(__package__))


def get_template_exe(gui: bool) -> Path | None:
    """Return a prebuilt launcher template bundled with the wheel, if any."""
    pkg = _get_package_dir()
    name = TEMPLATE_GUI if gui else TEMPLATE_CONSOLE
    candidate = pkg / name
    return candidate if candidate.is_file() else None


def ensure_template_exe(gui: bool) -> Path | None:
    """Return path to bundled ``console.exe`` or ``gui.exe``, or None if missing."""
    return get_template_exe(gui=gui)


def _make_payload(config: Mapping[str, Any]) -> bytes:
    data = json.dumps(config, separators=(",", ":")).encode("utf-8")
    footer = FOOTER_STRUCT.pack(MAGIC, len(data), 0)
    return data + footer


def build_launcher_for_script(
    launchers_dir: Path,
    script_name: str,
    module: str,
    func: str | None,
    *,
    gui: bool = False,
) -> Path | None:
    """
    Build a Windows .exe launcher for a console or GUI script entry.

    Returns the path to the created launcher, or None if no template is available.
    """
    template = ensure_template_exe(gui=gui)
    if template is None:
        return None

    config = {
        "module": module,
        "func": func or "main",
    }
    base = template.read_bytes()
    payload = _make_payload(config)

    target = launchers_dir / f"{script_name}.exe"
    target.write_bytes(base + payload)
    return target

