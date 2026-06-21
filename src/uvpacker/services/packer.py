"""
Packer orchestration — high-level ``pack_project()`` and the step-driven
``_perform_pack()`` spine.

Implementation details live in sibling modules:

* ``project_config`` — loading ``pyproject.toml``, resolving paths
* ``package_tree`` — filesystem operations on the installed ``packages/`` tree
* ``payload_archive`` — building the embedded zip and cleaning up package dirs
* ``launcher_build`` — writing launcher ``.exe`` shims from C templates
"""

from __future__ import annotations

import pathlib
import shutil

from ..domain.models import PackLayout, ProjectConfig
from ..domain.rules import require_exact_minor_from_requires, validate_project_config
from ..domain.sources import DEFAULT_DOWNLOAD_CONFIG, PackDownloadConfig
from ..infra import runtime_client, uv_client
from ..view.ui import info, kv, step, success

# Import extracted implementations that the orchestration spine needs.
from .bytecode import strip_source_to_pyc as _strip_source_to_pyc
from .package_tree import (
    fail_on_namespace_packages as _fail_on_namespace_packages,
    remove_non_runtime_script_shims as _remove_non_runtime_script_shims,
    resolve_project_roots as _resolve_project_roots,
)

from .launcher_build import create_exe_launchers as _create_exe_launchers
from .payload_archive import embed_project_archive as _embed_project_archive

from .project_config import (
    load_project_config as _load_project_config,
    require_project_dir as _require_project_dir,
    resolve_output_dir as _resolve_output_dir,
)

# ---------------------------------------------------------------------------
# Orchestration spine
# ---------------------------------------------------------------------------


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
    validate_project_config(cfg)
    kv("Project", cfg.name)

    dl = download if download is not None else DEFAULT_DOWNLOAD_CONFIG
    _log_download_sources(dl)

    target_python = _resolve_target_python_version(cfg, download=dl)
    kv("Python", f"{target_python} (win_amd64 embedded)")

    resolved_output = _resolve_output_dir(cfg.name, project_dir, output_dir)
    kv("Output", resolved_output)
    layout = _prepare_layout(resolved_output)

    _perform_pack(
        cfg=cfg,
        project_dir=project_dir,
        layout=layout,
        python_version=target_python,
        download=dl,
    )


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
    _fail_on_namespace_packages(layout.packages, package_roots)

    step(
        3,
        5,
        "Stripping source .py files for the target project (bytecode-only payload)...",
    )
    # Use the same Python minor version as the embedded runtime when compiling
    # bytecode via ``uv run``, so that .pyc files match the target environment.
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


# ---------------------------------------------------------------------------
# Helpers that remain in the orchestration module
# ---------------------------------------------------------------------------


def _resolve_target_python_version(
    cfg: ProjectConfig,
    *,
    download: PackDownloadConfig,
) -> str:
    info("Resolving target Python runtime...")
    minor = require_exact_minor_from_requires(cfg.requires_python)
    return runtime_client.resolve_latest_embed_for_minor(minor, download=download)


def _log_download_sources(download: PackDownloadConfig) -> None:
    if download == DEFAULT_DOWNLOAD_CONFIG:
        return
    info(f"Non-default embed index {download.embed_listing_url()!r}.")


def _prepare_layout(output_dir: pathlib.Path) -> PackLayout:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    embedded_dir = output_dir / "runtime"
    app_dir = output_dir / "packages"
    embedded_dir.mkdir()
    app_dir.mkdir()
    return PackLayout(root=output_dir, runtime=embedded_dir, packages=app_dir)


def _patch_embedded_runtime_config(embedded_dir: pathlib.Path) -> None:
    """
    Adjust embedded runtime configuration to make it suitable for relocatable use.

    For now this ensures that a ``python._pth`` exists and adds an entry for
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
