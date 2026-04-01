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


def _get_package_dir() -> Path:
    return Path(resources.files(__package__))


def get_template_exe() -> Path | None:
    """
    Return the path to a prebuilt launcher.exe bundled with the wheel, if any.
    """
    candidate = _get_package_dir() / "launcher.exe"
    return candidate if candidate.is_file() else None


def _compile_template_exe_with_mingw() -> Path | None:
    """
    Compile launcher.c into a Windows x86_64 launcher.exe using mingw, if available.

    This is a best-effort helper for development and CI; failures are treated as
    "no template available" by callers.
    """
    src_dir = _get_package_dir()
    source = src_dir / "launcher.c"
    if not source.is_file():
        return None

    cc = "x86_64-w64-mingw32-gcc"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "launcher.exe"
        cmd = [
            cc,
            "-municode",
            "-O2",
            "-static",
            "-s",
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

        # Copy into the package directory so subsequent calls can reuse it.
        target = src_dir / "launcher.exe"
        target.write_bytes(out.read_bytes())
        return target


def ensure_template_exe() -> Path | None:
    """
    Ensure a launcher.exe template is available and return its path.

    Preference order:
    1. Bundled launcher.exe in the package.
    2. Best-effort compilation via mingw (development / CI).
    """
    exe = get_template_exe()
    if exe is not None:
        return exe
    return _compile_template_exe_with_mingw()


def _make_payload(config: Mapping[str, Any]) -> bytes:
    data = json.dumps(config, separators=(",", ":")).encode("utf-8")
    footer = FOOTER_STRUCT.pack(MAGIC, len(data), 0)
    return data + footer


def build_launcher_for_script(
    launchers_dir: Path,
    script_name: str,
    module: str,
    func: str | None,
) -> Path | None:
    """
    Build a Windows .exe launcher for a given console script.

    Returns the path to the created launcher, or None if no template is available.
    """
    template = ensure_template_exe()
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


