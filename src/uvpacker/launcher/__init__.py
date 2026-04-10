from __future__ import annotations

import json
import struct
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

MAGIC = b"UVPKLAUN"
"""Embedded payload layout: ``zip_bytes | utf8_json | trailer``.

The trailer is ``struct.pack('<I8s', len(json_bytes), MAGIC)`` (12 bytes): JSON
length (uint32 LE) then the 8-byte magic. All semantic fields live in JSON
(``uvpacker`` release version, ``archive_size``, ``module``, ``func``, ...).
"""
TRAILER_STRUCT = struct.Struct("<I8s")

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


def _make_payload(config: Mapping[str, Any], archive: bytes = b"") -> bytes:
    from .. import __version__ as uvpacker_version

    meta: dict[str, Any] = dict(config)
    meta["uvpacker"] = uvpacker_version
    meta["archive_size"] = len(archive)
    data = json.dumps(meta, separators=(",", ":")).encode("utf-8")
    trailer = TRAILER_STRUCT.pack(len(data), MAGIC)
    return archive + data + trailer


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
    Build a Windows .exe launcher for a console or GUI script entry.

    Returns the path to the created launcher, or None if no template is available.
    """
    template = get_template_exe(gui=gui)
    if template is None:
        return None

    config = {
        "module": module,
        "func": func or "main",
    }
    base = template.read_bytes()
    payload = _make_payload(config, archive=archive)

    target = launchers_dir / f"{script_name}.exe"
    target.write_bytes(base + payload)
    return target
