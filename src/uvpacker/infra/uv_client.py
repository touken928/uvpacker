from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass

from ..domain.errors import BuildError
from ..domain.sources import DEFAULT_DOWNLOAD_CONFIG, PackDownloadConfig

WINDOWS_AMD64_UV_PLATFORM = "x86_64-pc-windows-msvc"


@dataclass(frozen=True)
class InstallRequest:
    project_dir: pathlib.Path
    target_dir: pathlib.Path
    target_python_version: str
    download: PackDownloadConfig


def install_project_with_uv(
    project_dir: pathlib.Path,
    target_dir: pathlib.Path,
    target_python_version: str,
    *,
    download: PackDownloadConfig = DEFAULT_DOWNLOAD_CONFIG,
) -> tuple[str, ...]:
    """
    Install a project into ``target_dir`` as a Windows amd64 application payload.

    Strategy:
    1. Build the local project into a wheel with the host interpreter.
    2. Reject cross-platform builds for non-pure wheels.
    3. Use `uv pip install` with an explicit target platform so dependency
       resolution always selects Windows amd64 wheels.
    """
    request = InstallRequest(
        project_dir=project_dir,
        target_dir=target_dir,
        target_python_version=target_python_version,
        download=download,
    )
    with tempfile.TemporaryDirectory() as tmp:
        wheel_dir = pathlib.Path(tmp)
        wheel_path = _build_project_wheel(
            request.project_dir, wheel_dir, download=request.download
        )
        _validate_built_wheel(wheel_path)
        top_level_import_names = _discover_top_level_import_names(wheel_path)
        cmd = _build_install_command(
            request=request, wheel_dir=wheel_dir, wheel_path=wheel_path
        )

        try:
            _run_command(cmd, cwd=request.project_dir)
        except BuildError as exc:
            raise BuildError(f"Dependency install failed. {exc}") from exc
    return top_level_import_names


def _build_project_wheel(
    project_dir: pathlib.Path,
    wheel_dir: pathlib.Path,
    *,
    download: PackDownloadConfig = DEFAULT_DOWNLOAD_CONFIG,
) -> pathlib.Path:
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
    except BuildError as exc:
        raise BuildError(f"Wheel build failed. {exc}") from exc

    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise BuildError(
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
        raise BuildError(
            "Cross-platform packaging currently requires the local project to "
            "build a pure-Python wheel. Native-extension projects must be built "
            "on Windows so the project wheel matches win_amd64.",
        )
    if sys.platform == "win32" and platform_tag not in {"any", "win_amd64"}:
        raise BuildError(
            "The built project wheel is not compatible with win_amd64: "
            f"{wheel_path.name}",
        )


def _discover_top_level_import_names(wheel_path: pathlib.Path) -> tuple[str, ...]:
    with zipfile.ZipFile(wheel_path) as wheel:
        names = wheel.namelist()
        try:
            top_level = next(
                name for name in names if name.endswith(".dist-info/top_level.txt")
            )
        except StopIteration:
            top_level = None

        if top_level is not None:
            raw = wheel.read(top_level).decode("utf-8", errors="ignore")
            discovered = tuple(
                line.strip() for line in raw.splitlines() if line.strip()
            )
            if discovered:
                return discovered

        inferred: list[str] = []
        seen: set[str] = set()
        for name in names:
            if name.endswith("/") or ".dist-info/" in name or ".data/" in name:
                continue
            root = pathlib.PurePosixPath(name).parts[0]
            if root.endswith(".py"):
                root = pathlib.PurePosixPath(root).stem
            if not root.isidentifier() or root in seen:
                continue
            seen.add(root)
            inferred.append(root)
        return tuple(inferred)


def _python_major_minor(version: str) -> str:
    parts = version.split(".")
    if len(parts) < 2:
        raise BuildError(f"Invalid Python version {version!r}.")
    return ".".join(parts[:2])


def _build_install_command(
    *,
    request: InstallRequest,
    wheel_dir: pathlib.Path,
    wheel_path: pathlib.Path,
) -> list[str]:
    return [
        "uv",
        "pip",
        "install",
        "--python",
        sys.executable,
        "--target",
        str(request.target_dir),
        "--python-version",
        _python_major_minor(request.target_python_version),
        "--python-platform",
        WINDOWS_AMD64_UV_PLATFORM,
        "--only-binary",
        ":all:",
        "--find-links",
        str(wheel_dir),
        str(wheel_path),
    ]


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
        raise BuildError(f"Cannot run command {cmd[0]!r}: {exc}") from exc

    if proc.returncode == 0:
        return

    stderr = (proc.stderr or "").strip()
    stdout = (proc.stdout or "").strip()
    detail = _tail(stderr or stdout)
    raise BuildError(
        f"Command failed ({cmd[0]}), exit={proc.returncode}. {detail}",
    )


def _tail(text: str, max_lines: int = 6) -> str:
    if not text:
        return "No output."
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "No output."
    return " | ".join(lines[-max_lines:])
