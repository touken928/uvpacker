from __future__ import annotations

import dataclasses
import pathlib
import shutil
import subprocess
import sys
from typing import Any, Mapping

try:  # Python 3.11+
    import tomllib  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

from .. import launcher as exe_launcher
from ..domain.errors import BuildError, ConfigError
from ..domain.sources import DEFAULT_DOWNLOAD_CONFIG, PackDownloadConfig
from ..infra import runtime_client, uv_client
from ..view.ui import info, kv, step, success


@dataclasses.dataclass(frozen=True)
class ScriptDefinition:
    name: str
    target: str
    # True when from [project.gui-scripts] (Windows subsystem, no console).
    gui: bool = False


@dataclasses.dataclass(frozen=True)
class ProjectConfig:
    root: pathlib.Path
    name: str
    requires_python: str | None
    scripts: list[ScriptDefinition]
    build_system: Mapping[str, Any]


@dataclasses.dataclass(frozen=True)
class PackLayout:
    root: pathlib.Path
    runtime: pathlib.Path
    packages: pathlib.Path


def pack_project(
    project_dir: pathlib.Path,
    output_dir: pathlib.Path | None = None,
    *,
    download: PackDownloadConfig | None = None,
) -> None:
    """
    High-level entrypoint for packing a Python project.

    This function:
    - Parses ``pyproject.toml`` in ``project_dir``
    - Validates that ``[project.scripts]`` and/or ``[project.gui-scripts]`` and
      ``[build-system]`` are present
    - Resolves the target Python version
    - Obtains the embedded runtime (cached under ~/.cache/uvpacker/embed), installs deps via uv, and prepares a
      relocatable application directory.

    Pass ``download`` to override the embedded-runtime source; by default
    uvpacker always uses python.org.
    """
    project_dir = project_dir.resolve()
    pyproject = _require_project_dir(project_dir)

    cfg = _load_project_config(pyproject)
    _validate_project_config(cfg)
    kv("Project", cfg.name)

    dl = download if download is not None else DEFAULT_DOWNLOAD_CONFIG
    _log_download_sources(dl)

    target_python = _resolve_target_python_version(cfg, download=dl)
    kv("Python", f"{target_python} (win_amd64 embedded)")

    resolved_output = _resolve_output_dir(cfg, project_dir, output_dir)
    kv("Output", resolved_output)
    layout = _prepare_layout(resolved_output)

    _perform_pack(
        cfg=cfg,
        project_dir=project_dir,
        layout=layout,
        python_version=target_python,
        download=dl,
    )


def _load_project_config(pyproject_path: pathlib.Path) -> ProjectConfig:
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


def _validate_project_config(cfg: ProjectConfig) -> None:
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
    if not cfg.build_system:
        raise ConfigError(
            "No [build-system] table found in pyproject.toml; "
            "uvpack relies on it to reproduce the build environment.",
        )

    # Delegate requires-python format validation to runtime parser so there is
    # a single source of truth for version constraints.
    runtime_client.require_exact_minor_from_requires(cfg.requires_python)


def _require_project_dir(project_dir: pathlib.Path) -> pathlib.Path:
    if not project_dir.is_dir():
        raise ConfigError(f"Project directory does not exist: {project_dir}")
    pyproject = project_dir / "pyproject.toml"
    if not pyproject.is_file():
        raise ConfigError(f"No pyproject.toml found in {project_dir}")
    return pyproject


def _log_download_sources(download: PackDownloadConfig) -> None:
    if download == DEFAULT_DOWNLOAD_CONFIG:
        return
    info(f"Non-default embed index {download.embed_listing_url()!r}.")


def _resolve_target_python_version(
    cfg: ProjectConfig,
    *,
    download: PackDownloadConfig,
) -> str:
    info("Resolving target Python runtime...")
    minor = runtime_client.require_exact_minor_from_requires(cfg.requires_python)
    return runtime_client.resolve_latest_embed_for_minor(minor, download=download)


def _resolve_output_dir(
    cfg: ProjectConfig,
    project_dir: pathlib.Path,
    output_dir: pathlib.Path | None,
) -> pathlib.Path:
    if output_dir is not None:
        return output_dir

    dist_dir = project_dir / "dist"
    return dist_dir / cfg.name


def _prepare_layout(output_dir: pathlib.Path) -> PackLayout:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    embedded_dir = output_dir / "runtime"
    app_dir = output_dir / "packages"
    embedded_dir.mkdir()
    app_dir.mkdir()
    return PackLayout(root=output_dir, runtime=embedded_dir, packages=app_dir)


def _perform_pack(
    cfg: ProjectConfig,
    project_dir: pathlib.Path,
    layout: PackLayout,
    python_version: str,
    *,
    download: PackDownloadConfig,
) -> None:
    step(1, 4, "Preparing embedded runtime...")
    runtime_client.download_and_extract_embedded_runtime(
        python_version,
        layout.runtime,
        download=download,
    )
    _patch_embedded_runtime_config(layout.runtime)

    step(2, 4, "Installing project and dependencies into packages/...")
    uv_client.install_project_with_uv(
        project_dir=project_dir,
        target_dir=layout.packages,
        target_python_version=python_version,
        download=download,
    )

    step(3, 4, "Stripping source .py files for the target project (bytecode-only payload)...")
    # Use the same Python minor version as the embedded runtime when compiling
    # bytecode via `uv run`, so that .pyc files match the target environment.
    py_parts = python_version.split(".")
    target_minor = ".".join(py_parts[:2]) if len(py_parts) >= 2 else python_version
    _strip_source_to_pyc(
        app_dir=layout.packages,
        project_name=cfg.name,
        target_python_minor=target_minor,
    )

    step(4, 4, "Generating launchers...")
    _create_exe_launchers(
        scripts=cfg.scripts,
        launchers_dir=layout.root,
    )
    success("Done.")


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


def _strip_source_to_pyc(
    app_dir: pathlib.Path,
    project_name: str,
    target_python_minor: str,
) -> None:
    """
    Compile the target project's sources to .pyc using the target Python version
    via ``uv run``, then remove the corresponding .py files.

    This is a best-effort obfuscation step: it avoids shipping readable source
    files for the target project, but does not make reverse engineering
    impossible.
    """
    # Heuristic: prefer the normalized distribution name (hyphens -> underscores).
    dist_name = project_name
    candidates = {dist_name, dist_name.replace("-", "_")}

    target_dirs: list[pathlib.Path] = []
    for entry in app_dir.iterdir():
        if entry.is_dir() and entry.name in candidates:
            target_dirs.append(entry)

    # Fallback: if we cannot identify a specific package directory, operate on
    # the entire app_dir.
    if not target_dirs:
        target_dirs = [app_dir]

    for pkg_dir in target_dirs:
        info(
            f"Compiling .py files in {pkg_dir.name!r} to .pyc using "
            f"Python {target_python_minor} via `uv run`...",
        )
        cmd = [
            "uv",
            "run",
            "--python",
            target_python_minor,
            "python",
            "-m",
            "compileall",
            "-b",
            str(pkg_dir),
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(pkg_dir),
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise BuildError(
                f"Failed to invoke 'uv' to compile bytecode for {pkg_dir.name!r}: {exc}",
            ) from exc

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise BuildError(
                f"'uv run --python {target_python_minor} python -m compileall' "
                f"failed for {pkg_dir.name!r}: {detail}",
            )

        # Remove .py sources now that .pyc files exist.
        for py_file in pkg_dir.rglob("*.py"):
            try:
                py_file.unlink()
            except OSError:
                # Best-effort: if we cannot delete a file, continue.
                continue


def _create_exe_launchers(
    scripts: list[ScriptDefinition],
    launchers_dir: pathlib.Path,
) -> None:
    """
    Generate Windows `.exe` launchers backed by a small C shim.

    Console entries use a PE console template; ``[project.gui-scripts]`` entries
    use a Windows/GUI subsystem template (no console window).

    These launchers are optional: if no template is available (for example when
    running on a non-Windows host without mingw), the corresponding launchers
    are skipped.
    """
    for script in scripts:
        module, _, func = script.target.partition(":")
        if not module:
            continue
        created = exe_launcher.build_launcher_for_script(
            launchers_dir=launchers_dir,
            script_name=script.name,
            module=module,
            func=func or "main",
            gui=script.gui,
        )
        if created is None:
            kind = "GUI" if script.gui else "console"
            info(
                f"Failed to create executable launcher for script {script.name!r} "
                f"({kind} template missing).",
            )
