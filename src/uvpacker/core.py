from __future__ import annotations

import dataclasses
import pathlib
import re
import shutil
import sys
from typing import Any, Mapping

try:  # Python 3.11+
    import tomllib  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

from . import launcher as exe_launcher
from . import runtime, uvclient
from .errors import UvPackError
from .ui import info


@dataclasses.dataclass(frozen=True)
class ScriptDefinition:
    name: str
    target: str


@dataclasses.dataclass(frozen=True)
class ProjectConfig:
    root: pathlib.Path
    name: str
    requires_python: str | None
    scripts: list[ScriptDefinition]
    build_system: Mapping[str, Any]


def pack_project(
    project_dir: pathlib.Path,
    output_dir: pathlib.Path | None = None,
) -> None:
    """
    High-level entrypoint for packing a Python project.

    This function:
    - Parses ``pyproject.toml`` in ``project_dir``
    - Validates that ``[project.scripts]`` and ``[build-system]`` are present
    - Resolves the target Python version
    - Downloads the embedded runtime, installs deps via uv, and prepares a
      relocatable application directory.
    """
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        raise UvPackError(f"Project directory does not exist: {project_dir}")

    pyproject = project_dir / "pyproject.toml"
    if not pyproject.is_file():
        raise UvPackError(f"No pyproject.toml found in {project_dir}")

    cfg = _load_project_config(pyproject)
    _validate_project_config(cfg)
    info(f"Project: {cfg.name}")

    info("Resolving target Python runtime...")
    minor = runtime.require_exact_minor_from_requires(cfg.requires_python)
    target_python = runtime.resolve_latest_embed_for_minor(minor)
    info(f"Using Python {target_python} (win_amd64 embedded)")

    resolved_output = _resolve_output_dir(cfg, project_dir, output_dir)
    info(f"Output: {resolved_output}")

    _perform_pack(
        cfg=cfg,
        project_dir=project_dir,
        output_dir=resolved_output,
        python_version=target_python,
    )


def _load_project_config(pyproject_path: pathlib.Path) -> ProjectConfig:
    text = pyproject_path.read_bytes()
    if tomllib is None:
        raise UvPackError("tomllib is not available; Python 3.11+ is required.")

    data = tomllib.loads(text.decode("utf-8"))

    project = data.get("project") or {}
    name = project.get("name")
    if not isinstance(name, str) or not name:
        raise UvPackError("`project.name` must be set in pyproject.toml.")

    requires_python = project.get("requires-python")

    scripts_table = project.get("scripts") or {}
    scripts: list[ScriptDefinition] = []
    for key, value in scripts_table.items():
        if isinstance(value, str):
            scripts.append(ScriptDefinition(name=key, target=value))

    build_system = data.get("build-system") or {}

    return ProjectConfig(
        root=pyproject_path.parent,
        name=name,
        requires_python=requires_python,
        scripts=scripts,
        build_system=build_system,
    )


def _validate_project_config(cfg: ProjectConfig) -> None:
    if not cfg.scripts:
        raise UvPackError(
            "No [project.scripts] defined in pyproject.toml; "
            "at least one console script entry is required.",
        )
    if not cfg.build_system:
        raise UvPackError(
            "No [build-system] table found in pyproject.toml; "
            "uvpack relies on it to reproduce the build environment.",
        )

    # 版本策略约束：必须采用 `==X.Y.*` 形式，确保次版本固定，由 uvpack 解析出
    # 对应的最新补丁版本。
    if not cfg.requires_python:
        raise UvPackError(
            "`project.requires-python` must be set and use the '==X.Y.*' format.",
        )

    pattern = r"^==\d+\.\d+\.\*$"
    if not re.fullmatch(pattern, cfg.requires_python.strip()):
        raise UvPackError(
            "uvpack requires `project.requires-python` to be an exact minor "
            "constraint of the form '==X.Y.*', for example '==3.11.*'.",
        )


def _resolve_output_dir(
    cfg: ProjectConfig,
    project_dir: pathlib.Path,
    output_dir: pathlib.Path | None,
) -> pathlib.Path:
    if output_dir is not None:
        return output_dir

    dist_dir = project_dir / "dist"
    return dist_dir / cfg.name


def _perform_pack(
    cfg: ProjectConfig,
    project_dir: pathlib.Path,
    output_dir: pathlib.Path,
    python_version: str,
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    embedded_dir = output_dir / "runtime"
    app_dir = output_dir / "packages"
    embedded_dir.mkdir()
    app_dir.mkdir()

    info("Step 1/3: Downloading embedded runtime...")
    runtime.download_and_extract_embedded_runtime(python_version, embedded_dir)
    _patch_embedded_runtime_config(embedded_dir)

    info("Step 2/3: Installing project and dependencies...")
    uvclient.install_project_with_uv(
        project_dir=project_dir,
        target_dir=app_dir,
        target_python_version=python_version,
    )

    info("Step 3/3: Generating launchers...")
    _create_exe_launchers(
        scripts=cfg.scripts,
        launchers_dir=output_dir,
    )
    info("Done.")


def _patch_embedded_runtime_config(embedded_dir: pathlib.Path) -> None:
    """
    Adjust embedded runtime configuration to make it suitable for relocatable use.

    For now this ensures that a `python._pth` exists and adds an entry for
    the application directory where uv-installed packages live.
    """
    pth = next(embedded_dir.glob("python*.pth"), None)
    if pth is None:
        # Some embedded builds use pythonXY._pth naming.
        pth = next(embedded_dir.glob("python*._pth"), None)

    if pth is None:
        # Best-effort, not fatal; user can adjust manually.
        return

    content = pth.read_text(encoding="utf-8")
    # Add a relative search path for the "packages" directory one level up.
    rel_app = "..\\packages"
    if rel_app not in content:
        content = content.rstrip() + "\n" + rel_app + "\n"
        pth.write_text(content, encoding="utf-8")


def _create_cmd_launchers(
    scripts: list[ScriptDefinition],
    embedded_dir: pathlib.Path,
    app_dir: pathlib.Path,
    launchers_dir: pathlib.Path,
) -> None:
    """
    Generate simple `.cmd` launchers that:
    - set up PATH to include the embedded runtime
    - execute the appropriate console script via the embedded Python.

    A future version can replace these with compiled .exe shims if desired.
    """
    for script in scripts:
        launcher_path = launchers_dir / f"{script.name}.cmd"
        module, _, func = script.target.partition(":")
        if not module:
            # Skip invalid entry.
            continue

        # Execute the configured callable `module:func` via a tiny `-c` stub so
        # that we do not require the presence of a `__main__` module/package.
        target_call = f"from {module} import {func or 'main'} as _f; raise SystemExit(_f())"
        cmd_content = textwrap.dedent(
            f"""\
            @echo off
            setlocal
            set "UVPACK_APP=%~dp0packages"
            "%~dp0runtime\\python.exe" -c "{target_call}" %*
            endlocal
            """,
        )
        launcher_path.write_text(cmd_content, encoding="utf-8")


def _create_exe_launchers(
    scripts: list[ScriptDefinition],
    launchers_dir: pathlib.Path,
) -> None:
    """
    Generate Windows `.exe` launchers backed by a small C shim.

    These launchers are optional: if no template is available (for example when
    running on a non-Windows host without mingw), this step is silently skipped
    and `.cmd` launchers are still generated.
    """
    template = exe_launcher.ensure_template_exe()
    if template is None:
        info("Executable launchers not created: no launcher.exe template available.")
        return

    for script in scripts:
        module, _, func = script.target.partition(":")
        if not module:
            continue
        created = exe_launcher.build_launcher_for_script(
            launchers_dir=launchers_dir,
            script_name=script.name,
            module=module,
            func=func or "main",
        )
        if created is None:
            info(f"Failed to create executable launcher for script {script.name!r}.")

