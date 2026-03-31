from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

from .errors import UvPackError


WINDOWS_AMD64_UV_PLATFORM = "x86_64-pc-windows-msvc"


def install_project_with_uv(
    project_dir: pathlib.Path,
    target_dir: pathlib.Path,
    target_python_version: str,
) -> None:
    """
    Install a project into ``target_dir`` as a Windows amd64 application payload.

    Strategy:
    1. Build the local project into a wheel with the host interpreter.
    2. Reject cross-platform builds for non-pure wheels.
    3. Use `uv pip install` with an explicit target platform so dependency
       resolution always selects Windows amd64 wheels.
    """
    with tempfile.TemporaryDirectory() as tmp:
        wheel_dir = pathlib.Path(tmp)
        wheel_path = _build_project_wheel(project_dir, wheel_dir)
        _validate_built_wheel(wheel_path)

        cmd = [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--target",
            str(target_dir),
            "--python-version",
            _python_major_minor(target_python_version),
            "--python-platform",
            WINDOWS_AMD64_UV_PLATFORM,
            "--only-binary",
            ":all:",
            "--find-links",
            str(wheel_dir),
            str(wheel_path),
        ]

        try:
            _run_command(cmd, cwd=project_dir)
        except UvPackError as exc:
            raise UvPackError(f"Dependency install failed. {exc}") from exc


def _build_project_wheel(project_dir: pathlib.Path, wheel_dir: pathlib.Path) -> pathlib.Path:
    cmd = [
        "uv",
        "build",
        "--wheel",
        "--out-dir",
        str(wheel_dir),
        str(project_dir),
    ]

    try:
        _run_command(cmd, cwd=project_dir)
    except UvPackError as exc:
        raise UvPackError(f"Wheel build failed. {exc}") from exc

    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise UvPackError(
            "Expected exactly one wheel for the local project build, "
            f"found {len(wheels)}.",
        )
    return wheels[0]


def _validate_built_wheel(wheel_path: pathlib.Path) -> None:
    """
    A non-Windows host cannot safely produce Windows-native extension wheels.

    We therefore require the local project wheel to be pure Python (`*-any.whl`)
    unless the build host is already Windows.
    """
    platform_tag = wheel_path.stem.split("-")[-1]
    if sys.platform != "win32" and platform_tag != "any":
        raise UvPackError(
            "Cross-platform packaging currently requires the local project to "
            "build a pure-Python wheel. Native-extension projects must be built "
            "on Windows so the project wheel matches win_amd64.",
        )
    if sys.platform == "win32" and platform_tag not in {"any", "win_amd64"}:
        raise UvPackError(
            "The built project wheel is not compatible with win_amd64: "
            f"{wheel_path.name}",
        )


def _python_major_minor(version: str) -> str:
    parts = version.split(".")
    if len(parts) < 2:
        raise UvPackError(f"Invalid Python version {version!r}.")
    return ".".join(parts[:2])


def _run_command(cmd: list[str], cwd: pathlib.Path) -> None:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise UvPackError(f"Cannot run command {cmd[0]!r}: {exc}") from exc

    if proc.returncode == 0:
        return

    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    detail = _tail(stderr or stdout)
    raise UvPackError(
        f"Command failed ({cmd[0]}), exit={proc.returncode}. {detail}",
    )


def _tail(text: str, max_lines: int = 6) -> str:
    if not text:
        return "No output."
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "No output."
    return " | ".join(lines[-max_lines:])

