"""
Payload/archive helpers — building the embedded zip and cleaning up package dirs.

Extracted from ``packer.py`` so that the orchestration module keeps only
``pack_project()`` / ``_perform_pack()`` as its stable spine.

Launcher-exe assembly lives in the sibling ``launcher_build`` module.
"""

from __future__ import annotations

import io
import pathlib
import re
import shutil
import zipfile

from ..domain.errors import BuildError
from ..domain.rules import validate_embeddable_file


def embed_project_archive(
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
                    validate_embeddable_file(root, file_path.relative_to(app_dir))
                    archive.write(file_path, file_path.relative_to(app_dir).as_posix())
                    seen = True
                continue

            for suffix in (".pyc", ".py"):
                module_path = app_dir / f"{root}{suffix}"
                if module_path.is_file():
                    validate_embeddable_file(root, module_path.relative_to(app_dir))
                    archive.write(
                        module_path, module_path.relative_to(app_dir).as_posix()
                    )
                    seen = True
                    break

    if not seen:
        raise BuildError("Failed to collect any project files for launcher embedding.")
    return buffer.getvalue()


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


def _read_metadata_name(metadata_path: pathlib.Path) -> str | None:
    with metadata_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("Name:"):
                return line.partition(":")[2].strip()
    return None


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()



