from __future__ import annotations

from pathlib import Path

import pytest

from uvpacker.services import packer


def test_warn_missing_package_inits_emits_for_dir_with_py_modules(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_dir = tmp_path / "packages"
    pkg = app_dir / "demo"
    pkg.mkdir(parents=True)
    (pkg / "main.py").write_text("x = 1\n", encoding="utf-8")

    packer._warn_missing_package_inits(app_dir, ("demo",))

    text = capsys.readouterr().out
    assert "[uvpacker]" in text
    assert "WARN" in text
    assert "demo" in text
    assert "__init__.py" in text


def test_warn_missing_package_inits_nested_subpackage(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_dir = tmp_path / "packages"
    outer = app_dir / "demo"
    sub = outer / "nested"
    sub.mkdir(parents=True)
    (outer / "__init__.py").write_text("", encoding="utf-8")
    (sub / "mod.py").write_text("y = 2\n", encoding="utf-8")

    packer._warn_missing_package_inits(app_dir, ("demo",))

    text = capsys.readouterr().out
    assert "WARN" in text
    assert "demo/nested" in text


def test_warn_missing_package_inits_quiet_when_init_present(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_dir = tmp_path / "packages"
    pkg = app_dir / "demo"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "main.py").write_text("x = 1\n", encoding="utf-8")

    packer._warn_missing_package_inits(app_dir, ("demo",))

    assert "WARN" not in capsys.readouterr().out


def test_warn_missing_package_inits_skips_single_file_module_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_dir = tmp_path / "packages"
    app_dir.mkdir()
    (app_dir / "demo.py").write_text("def main():\n    pass\n", encoding="utf-8")

    packer._warn_missing_package_inits(app_dir, ("demo",))

    assert "WARN" not in capsys.readouterr().out
