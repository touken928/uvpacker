from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from uvpacker.infra import uv_client
from uvpacker.domain.errors import BuildError
from uvpacker.launcher import FOOTER_STRUCT, MAGIC, PAYLOAD_VERSION, _make_payload
from uvpacker.services import packer


def test_make_payload_appends_archive_then_metadata_then_footer() -> None:
    archive = b"PK\x03\x04payload"
    payload = _make_payload({"module": "demo.main", "func": "main"}, archive=archive)

    footer = payload[-FOOTER_STRUCT.size :]
    magic, metadata_size, archive_size, version = FOOTER_STRUCT.unpack(footer)

    assert magic == MAGIC
    assert archive_size == len(archive)
    assert version == PAYLOAD_VERSION
    assert payload[:archive_size] == archive

    metadata = json.loads(payload[archive_size : archive_size + metadata_size].decode("utf-8"))
    assert metadata == {"module": "demo.main", "func": "main"}


def test_discover_top_level_import_names_prefers_top_level_txt(tmp_path: Path) -> None:
    wheel_path = tmp_path / "demo-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel_path, "w") as wheel:
        wheel.writestr("demo-0.1.0.dist-info/top_level.txt", "demo\nhelper_mod\n")
        wheel.writestr("ignored.py", "print('x')\n")

    assert uv_client._discover_top_level_import_names(wheel_path) == ("demo", "helper_mod")


def test_build_project_archive_and_remove_roots(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    pkg_dir = packages / "demo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.pyc").write_bytes(b"pkg")
    (pkg_dir / "data.txt").write_text("hello", encoding="utf-8")
    (packages / "helper_mod.pyc").write_bytes(b"mod")

    archive = packer._build_project_archive(packages, ("demo", "helper_mod"))

    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        assert sorted(bundle.namelist()) == [
            "demo/__init__.pyc",
            "demo/data.txt",
            "helper_mod.pyc",
        ]
        assert bundle.read("demo/data.txt") == b"hello"

    packer._remove_project_roots(packages, ("demo", "helper_mod"))

    assert not pkg_dir.exists()
    assert not (packages / "helper_mod.pyc").exists()


def test_build_project_archive_rejects_native_extensions(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    pkg_dir = packages / "demo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.pyc").write_bytes(b"pkg")
    (pkg_dir / "fast.pyd").write_bytes(b"native")

    with pytest.raises(BuildError, match="cannot be embedded purely in-memory"):
        packer._build_project_archive(packages, ("demo",))


def test_remove_project_dist_info_only_removes_target_project(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    own = packages / "demo_app-0.1.0.dist-info"
    dep = packages / "requests-2.32.0.dist-info"
    own.mkdir(parents=True)
    dep.mkdir(parents=True)
    (own / "METADATA").write_text("Metadata-Version: 2.1\nName: demo-app\n", encoding="utf-8")
    (dep / "METADATA").write_text("Metadata-Version: 2.1\nName: requests\n", encoding="utf-8")

    packer._remove_project_dist_info(packages, "demo_app")

    assert not own.exists()
    assert dep.exists()


def test_remove_non_runtime_script_shims_removes_bin_and_scripts(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    (packages / "bin").mkdir(parents=True)
    (packages / "Scripts").mkdir(parents=True)
    (packages / "bin" / "uvicorn").write_text("shim", encoding="utf-8")
    (packages / "Scripts" / "uvicorn.exe").write_bytes(b"exe")
    (packages / "requests").mkdir(parents=True)

    packer._remove_non_runtime_script_shims(packages)

    assert not (packages / "bin").exists()
    assert not (packages / "Scripts").exists()
    assert (packages / "requests").exists()
