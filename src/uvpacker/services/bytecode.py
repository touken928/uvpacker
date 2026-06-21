"""
Bytecode compilation — invoking the target Python version via ``uv run`` to
compile project sources to ``.pyc`` and remove the original ``.py`` files.

Extracted from ``services.package_tree`` so that module stays focused on
package-tree and namespace-discovery operations.
"""

from __future__ import annotations

import pathlib

from ..domain.errors import BuildError
from ..infra.uv_compile import run_uv_python
from ..view.ui import info


def strip_source_to_pyc(
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
    try:
        run_uv_python(
            target_python_minor=target_python_minor,
            cwd=cwd,
            python_args=python_args,
        )
    except BuildError as exc:
        raise BuildError(f"{failure_message}: {exc}") from exc


def _remove_python_sources(pkg_dir: pathlib.Path) -> None:
    for py_file in pkg_dir.rglob("*.py"):
        try:
            py_file.unlink()
        except OSError:
            continue
