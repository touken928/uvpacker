from __future__ import annotations

import dataclasses
import io
import pathlib
import re
import shutil
import subprocess
import zipfile
from typing import Any, Mapping

try:  # Python 3.11+
    import tomllib  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

from .. import launcher as exe_launcher
from ..domain.errors import BuildError, ConfigError
from ..domain.sources import DEFAULT_DOWNLOAD_CONFIG, PackDownloadConfig
from ..infra import runtime_client, uv_client
from ..view.ui import info, kv, step, success, warn


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
    step(1, 5, "Preparing embedded runtime...")
    runtime_client.download_and_extract_embedded_runtime(
        python_version,
        layout.runtime,
        download=download,
    )
    _patch_embedded_runtime_config(layout.runtime)

    step(2, 5, "Installing project and dependencies into packages/...")
    project_roots = uv_client.install_project_with_uv(
        project_dir=project_dir,
        target_dir=layout.packages,
        target_python_version=python_version,
        download=download,
    )
    _remove_non_runtime_script_shims(layout.packages)
    package_roots = _resolve_project_roots(layout.packages, project_roots, cfg.name)
    _warn_missing_package_inits(layout.packages, package_roots)

    step(
        3,
        5,
        "Stripping source .py files for the target project (bytecode-only payload)...",
    )
    # Use the same Python minor version as the embedded runtime when compiling
    # bytecode via `uv run`, so that .pyc files match the target environment.
    py_parts = python_version.split(".")
    target_minor = ".".join(py_parts[:2]) if len(py_parts) >= 2 else python_version
    _strip_source_to_pyc(
        app_dir=layout.packages,
        project_roots=package_roots,
        target_python_minor=target_minor,
    )

    step(4, 5, "Embedding the target project into launcher payloads...")
    project_archive = _embed_project_archive(
        layout.packages,
        package_roots,
        cfg.name,
    )

    step(5, 5, "Generating launchers...")
    _create_exe_launchers(
        scripts=cfg.scripts,
        launchers_dir=layout.root,
        archive=project_archive,
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


def _warn_missing_package_inits(
    app_dir: pathlib.Path, project_roots: tuple[str, ...]
) -> None:
    """
    Emit a warning when a directory holds Python modules but has no ``__init__.py``.

    Such layouts rely on implicit/namespace packages (PEP 420); shipping a
    bytecode-only tree is safer with explicit ``__init__.py`` files for normal
    packages.
    """
    for root in project_roots:
        pkg_dir = app_dir / root
        if not pkg_dir.is_dir():
            continue
        candidates = [pkg_dir]
        candidates.extend(p for p in pkg_dir.rglob("*") if p.is_dir())
        for path in sorted(candidates, key=lambda p: str(p)):
            if (path / "__init__.py").is_file():
                continue
            has_direct_py = any(
                child.is_file() and child.suffix == ".py" for child in path.iterdir()
            )
            if not has_direct_py:
                continue
            rel = path.relative_to(app_dir).as_posix()
            warn(
                f"Package directory {rel!r} contains .py files but no __init__.py; "
                "add __init__.py if this should be a regular package.",
            )


def _resolve_project_roots(
    app_dir: pathlib.Path,
    discovered_roots: tuple[str, ...],
    project_name: str,
) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(discovered_roots))
    if normalized:
        return normalized

    fallback = [project_name, project_name.replace("-", "_")]
    existing: list[str] = []
    for root in fallback:
        if (
            (app_dir / root).is_dir()
            or (app_dir / f"{root}.py").is_file()
            or (app_dir / f"{root}.pyc").is_file()
        ):
            existing.append(root)
    return tuple(dict.fromkeys(existing))


def _strip_source_to_pyc(
    app_dir: pathlib.Path,
    project_roots: tuple[str, ...],
    target_python_minor: str,
) -> None:
    """
    Compile the target project's sources to .pyc using the target Python version
    via ``uv run``, then remove the corresponding .py files.

    This is a best-effort obfuscation step: it avoids shipping readable source
    files for the target project, but does not make reverse engineering
    impossible.
    """
    target_dirs = _existing_project_dirs(app_dir, project_roots) or [app_dir]

    for pkg_dir in target_dirs:
        _compile_directory_tree_to_pyc(pkg_dir, target_python_minor)
        _remove_python_sources(pkg_dir)

    for root in project_roots:
        module_py = app_dir / f"{root}.py"
        if module_py.is_file():
            _compile_module_to_pyc(module_py, app_dir, target_python_minor)
            try:
                module_py.unlink()
            except OSError:
                continue


def _existing_project_dirs(
    app_dir: pathlib.Path,
    project_roots: tuple[str, ...],
) -> list[pathlib.Path]:
    return [entry for root in project_roots if (entry := app_dir / root).is_dir()]


def _compile_directory_tree_to_pyc(
    pkg_dir: pathlib.Path,
    target_python_minor: str,
) -> None:
    info(
        f"Compiling .py files in {pkg_dir.name!r} to .pyc using "
        f"Python {target_python_minor} via `uv run`...",
    )
    _run_uv_python(
        target_python_minor=target_python_minor,
        cwd=pkg_dir,
        python_args=["-m", "compileall", "-b", str(pkg_dir)],
        failure_message=(
            f"'uv run --no-project --python {target_python_minor} python -m compileall' "
            f"failed for {pkg_dir.name!r}"
        ),
    )


def _compile_module_to_pyc(
    module_py: pathlib.Path,
    app_dir: pathlib.Path,
    target_python_minor: str,
) -> None:
    compiled = module_py.with_suffix(".pyc")
    if compiled.is_file():
        return

    info(
        f"Compiling module {module_py.name!r} to .pyc using "
        f"Python {target_python_minor} via `uv run`...",
    )
    _run_uv_python(
        target_python_minor=target_python_minor,
        cwd=app_dir,
        python_args=["-m", "py_compile", str(module_py)],
        failure_message=(
            f"'uv run --no-project --python {target_python_minor} python -m py_compile' "
            f"failed for module {module_py.name!r}"
        ),
    )


def _run_uv_python(
    *,
    target_python_minor: str,
    cwd: pathlib.Path,
    python_args: list[str],
    failure_message: str,
) -> None:
    # Avoid the packer's own `requires-python` (e.g. 3.12) when the target
    # project uses a different minor (e.g. 3.10) for bytecode compilation.
    cmd = [
        "uv",
        "run",
        "--no-project",
        "--python",
        target_python_minor,
        "python",
        *python_args,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise BuildError(f"Failed to invoke 'uv' from {cwd}: {exc}") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise BuildError(f"{failure_message}: {detail}")


def _remove_python_sources(pkg_dir: pathlib.Path) -> None:
    for py_file in pkg_dir.rglob("*.py"):
        try:
            py_file.unlink()
        except OSError:
            # Best-effort: if we cannot delete a file, continue.
            continue


def _embed_project_archive(
    app_dir: pathlib.Path,
    project_roots: tuple[str, ...],
    project_name: str,
) -> bytes:
    archive = _build_project_archive(app_dir, project_roots)
    _remove_project_roots(app_dir, project_roots)
    _remove_project_dist_info(app_dir, project_name)
    return archive


def _build_project_archive(
    app_dir: pathlib.Path, project_roots: tuple[str, ...]
) -> bytes:
    if not project_roots:
        raise BuildError(
            "Could not determine which installed package roots belong to the project."
        )

    buffer = io.BytesIO()
    seen = False
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for root in project_roots:
            pkg_dir = app_dir / root
            if pkg_dir.is_dir():
                for file_path in sorted(
                    path for path in pkg_dir.rglob("*") if path.is_file()
                ):
                    _validate_embeddable_file(root, file_path.relative_to(app_dir))
                    archive.write(file_path, file_path.relative_to(app_dir).as_posix())
                    seen = True
                continue

            for suffix in (".pyc", ".py"):
                module_path = app_dir / f"{root}{suffix}"
                if module_path.is_file():
                    _validate_embeddable_file(root, module_path.relative_to(app_dir))
                    archive.write(
                        module_path, module_path.relative_to(app_dir).as_posix()
                    )
                    seen = True
                    break

    if not seen:
        raise BuildError("Failed to collect any project files for launcher embedding.")
    return buffer.getvalue()


def _validate_embeddable_file(root: str, relative_path: pathlib.Path) -> None:
    unsupported_suffixes = {".pyd", ".dll", ".so", ".dylib"}
    if relative_path.suffix.lower() in unsupported_suffixes:
        raise BuildError(
            "The project package cannot be embedded purely in-memory because "
            f"{relative_path.as_posix()!r} under root {root!r} is a native binary.",
        )


def _remove_project_roots(
    app_dir: pathlib.Path, project_roots: tuple[str, ...]
) -> None:
    for root in project_roots:
        pkg_dir = app_dir / root
        if pkg_dir.is_dir():
            shutil.rmtree(pkg_dir, ignore_errors=True)
            continue

        for suffix in (".pyc", ".py"):
            module_path = app_dir / f"{root}{suffix}"
            if module_path.is_file():
                try:
                    module_path.unlink()
                except OSError:
                    pass


def _remove_project_dist_info(app_dir: pathlib.Path, project_name: str) -> None:
    target = _normalize_distribution_name(project_name)
    for dist_info in app_dir.glob("*.dist-info"):
        metadata = dist_info / "METADATA"
        if not metadata.is_file():
            continue
        try:
            declared_name = _read_metadata_name(metadata)
        except OSError:
            continue
        if declared_name is None:
            continue
        if _normalize_distribution_name(declared_name) == target:
            shutil.rmtree(dist_info, ignore_errors=True)


def _remove_non_runtime_script_shims(app_dir: pathlib.Path) -> None:
    # `uv pip install --target` may leave host-style script shims under bin/.
    # They are not used by the packed app, which launches through our own exe shims.
    for name in ("bin", "Scripts"):
        scripts_dir = app_dir / name
        if scripts_dir.is_dir():
            shutil.rmtree(scripts_dir, ignore_errors=True)


def _read_metadata_name(metadata_path: pathlib.Path) -> str | None:
    with metadata_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("Name:"):
                return line.partition(":")[2].strip()
    return None


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _create_exe_launchers(
    scripts: list[ScriptDefinition],
    launchers_dir: pathlib.Path,
    archive: bytes,
) -> None:
    """
    Generate Windows `.exe` launchers backed by a small C shim.

    Console entries use a PE console template; ``[project.gui-scripts]`` entries
    use a Windows/GUI subsystem template (no console window).

    These launchers are optional: if the bundled ``console.exe`` / ``gui.exe``
    templates are missing from the package, the corresponding launchers are
    skipped.
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
            archive=archive,
        )
        if created is None:
            kind = "GUI" if script.gui else "console"
            info(
                f"Failed to create executable launcher for script {script.name!r} "
                f"({kind} template missing).",
            )
