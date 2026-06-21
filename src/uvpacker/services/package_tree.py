"""
Package-tree helpers — filesystem operations on the installed ``packages/`` tree.

Extracted from ``packer.py`` so that the orchestration module keeps only
``pack_project()`` / ``_perform_pack()`` as its stable spine.

Bytecode-compilation responsibilities have been moved to ``services.bytecode``.
"""

from __future__ import annotations

import pathlib
import shutil

from ..domain.errors import BuildError


def fail_on_namespace_packages(
    app_dir: pathlib.Path, project_roots: tuple[str, ...]
) -> None:
    """
    Reject directory trees that rely on implicit namespace packages.

    The embedded launcher importer only supports regular packages and modules,
    so a successful build would otherwise produce a broken app at runtime.
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
            if not _contains_python_module_tree(path):
                continue
            rel = path.relative_to(app_dir).as_posix()
            raise BuildError(
                f"Package directory {rel!r} contains Python modules but no __init__.py. "
                "uvpacker does not support namespace packages in embedded launchers; "
                "add __init__.py or ship the project as regular packages."
            )


def _contains_python_module_tree(path: pathlib.Path) -> bool:
    for child in path.iterdir():
        if child.is_file() and child.suffix in {".py", ".pyc"}:
            return True
        if child.is_dir() and _contains_python_module_tree(child):
            return True
    return False


def resolve_project_roots(
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


def existing_project_dirs(
    app_dir: pathlib.Path,
    project_roots: tuple[str, ...],
) -> list[pathlib.Path]:
    return [entry for root in project_roots if (entry := app_dir / root).is_dir()]


def remove_non_runtime_script_shims(app_dir: pathlib.Path) -> None:
    # ``uv pip install --target`` may leave host-style script shims under bin/.
    # They are not used by the packed app, which launches through our own exe shims.
    for name in ("bin", "Scripts"):
        scripts_dir = app_dir / name
        if scripts_dir.is_dir():
            shutil.rmtree(scripts_dir, ignore_errors=True)
