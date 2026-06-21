"""
Tests for namespace-package validation, targeting ``services.package_tree``
directly instead of the deprecated ``packer._fail_on_namespace_packages`` alias.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uvpacker.domain.errors import BuildError
from uvpacker.services.package_tree import fail_on_namespace_packages


def test_namespace_packages_raise_for_dir_with_py_modules(tmp_path: Path) -> None:
    app_dir = tmp_path / "packages"
    pkg = app_dir / "demo"
    pkg.mkdir(parents=True)
    (pkg / "main.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(BuildError, match=r"no __init__\.py"):
        fail_on_namespace_packages(app_dir, ("demo",))


def test_namespace_packages_raise_for_nested_subpackage(tmp_path: Path) -> None:
    app_dir = tmp_path / "packages"
    outer = app_dir / "demo"
    sub = outer / "nested"
    sub.mkdir(parents=True)
    (outer / "__init__.py").write_text("", encoding="utf-8")
    (sub / "mod.py").write_text("y = 2\n", encoding="utf-8")

    with pytest.raises(BuildError, match="demo/nested"):
        fail_on_namespace_packages(app_dir, ("demo",))


def test_namespace_package_root_without_direct_py_still_raises(tmp_path: Path) -> None:
    app_dir = tmp_path / "packages"
    root = app_dir / "acme"
    sub = root / "foo"
    sub.mkdir(parents=True)
    (sub / "__init__.py").write_text("", encoding="utf-8")
    (sub / "mod.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(BuildError, match="acme"):
        fail_on_namespace_packages(app_dir, ("acme",))


def test_namespace_packages_quiet_when_init_present(tmp_path: Path) -> None:
    app_dir = tmp_path / "packages"
    pkg = app_dir / "demo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "main.py").write_text("x = 1\n", encoding="utf-8")

    fail_on_namespace_packages(app_dir, ("demo",))


def test_namespace_packages_skip_single_file_module_root(tmp_path: Path) -> None:
    app_dir = tmp_path / "packages"
    app_dir.mkdir()
    (app_dir / "demo.py").write_text("def main():\n    pass\n", encoding="utf-8")

    fail_on_namespace_packages(app_dir, ("demo",))
