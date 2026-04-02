from __future__ import annotations

import json
import struct
import subprocess
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any, Mapping

MAGIC = b"UVPKLAUN"
FOOTER_STRUCT = struct.Struct("<8sII")

TEMPLATE_CONSOLE = "launcher_console.exe"
TEMPLATE_GUI = "launcher_gui.exe"


def _get_package_dir() -> Path:
    return Path(resources.files(__package__))


def get_template_exe(gui: bool) -> Path | None:
    """Return a prebuilt launcher template bundled with the wheel, if any."""
    pkg = _get_package_dir()
    name = TEMPLATE_GUI if gui else TEMPLATE_CONSOLE
    candidate = pkg / name
    return candidate if candidate.is_file() else None


def _compile_one_template(
    *,
    src_dir: Path,
    out_name: str,
    extra_cc_args: list[str],
) -> Path | None:
    source = src_dir / "launcher.c"
    if not source.is_file():
        return None

    cc = "x86_64-w64-mingw32-gcc"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / out_name
        cmd = [
            cc,
            "-municode",
            "-O2",
            "-static",
            "-s",
            *extra_cc_args,
            "-o",
            str(out),
            str(source),
        ]
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError:
            return None

        if proc.returncode != 0 or not out.is_file():
            return None

        target = src_dir / out_name
        target.write_bytes(out.read_bytes())
        return target


def _compile_template_exes_with_mingw() -> tuple[Path | None, Path | None]:
    """
    Compile launcher.c twice: console and GUI (Windows subsystem) templates.

    Failures are treated as missing templates by callers.
    """
    src_dir = _get_package_dir()
    console = _compile_one_template(
        src_dir=src_dir,
        out_name=TEMPLATE_CONSOLE,
        extra_cc_args=[],
    )
    gui = _compile_one_template(
        src_dir=src_dir,
        out_name=TEMPLATE_GUI,
        extra_cc_args=["-mwindows", "-DUVPACKER_GUI_SUBSYSTEM"],
    )
    return console, gui


def ensure_template_exe(gui: bool) -> Path | None:
    """
    Ensure a launcher template exists for the requested subsystem and return its path.

    Preference order:
    1. Bundled template in the package (``launcher_console.exe`` / ``launcher_gui.exe``).
    2. Best-effort compilation via mingw (development / CI), which builds both templates.
    """
    exe = get_template_exe(gui=gui)
    if exe is not None:
        return exe
    console_built, gui_built = _compile_template_exes_with_mingw()
    if gui:
        return gui_built
    return console_built or get_template_exe(gui=False)


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

