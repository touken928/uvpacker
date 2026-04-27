from __future__ import annotations

import json
from pathlib import Path

import pytest

from uvpacker import launcher
from uvpacker.launcher import MAGIC, TRAILER_STRUCT, _make_payload


class TestGetTemplateExe:
    def test_console_template_exists(self) -> None:
        template = launcher.get_template_exe(gui=False)
        assert template is not None
        assert template.name == "console.exe"

    def test_gui_template_exists(self) -> None:
        template = launcher.get_template_exe(gui=True)
        assert template is not None
        assert template.name == "gui.exe"


class TestMakePayload:
    def test_payload_structure_with_archive(self) -> None:
        archive = b"zip_data" * 10
        config = {"module": "pkg.mod", "func": "entry"}
        payload = _make_payload(config, archive=archive)

        trailer = payload[-TRAILER_STRUCT.size :]
        json_len, magic = TRAILER_STRUCT.unpack(trailer)
        assert magic == MAGIC

        assert payload[: len(archive)] == archive
        meta_bytes = payload[len(archive) : len(archive) + json_len]
        metadata = json.loads(meta_bytes.decode("utf-8"))
        assert metadata["module"] == "pkg.mod"
        assert metadata["func"] == "entry"
        assert metadata["archive_size"] == len(archive)
        assert "uvpacker" in metadata

    def test_payload_structure_without_archive(self) -> None:
        config = {"module": "app.main", "func": "run"}
        payload = _make_payload(config)

        trailer = payload[-TRAILER_STRUCT.size :]
        json_len, magic = TRAILER_STRUCT.unpack(trailer)
        assert magic == MAGIC

        meta_bytes = payload[:json_len]
        metadata = json.loads(meta_bytes.decode("utf-8"))
        assert metadata["module"] == "app.main"
        assert metadata["func"] == "run"
        assert metadata["archive_size"] == 0


class TestBuildLauncherForScript:
    def test_creates_console_exe(self, tmp_path: Path) -> None:
        result = launcher.build_launcher_for_script(
            launchers_dir=tmp_path,
            script_name="myapp",
            module="demo.main",
            func="main",
            gui=False,
            archive=b"test_archive",
        )
        assert result is not None
        assert result == tmp_path / "myapp.exe"
        assert result.is_file()
        # The file should be larger than the template alone
        template = launcher.get_template_exe(gui=False)
        assert template is not None
        assert result.stat().st_size > template.stat().st_size

    def test_creates_gui_exe(self, tmp_path: Path) -> None:
        result = launcher.build_launcher_for_script(
            launchers_dir=tmp_path,
            script_name="viewer",
            module="app.viewer",
            func="display",
            gui=True,
            archive=b"gui_archive",
        )
        assert result is not None
        assert result == tmp_path / "viewer.exe"
        assert result.is_file()

    def test_default_func_main(self, tmp_path: Path) -> None:
        result = launcher.build_launcher_for_script(
            launchers_dir=tmp_path,
            script_name="test",
            module="mod.main",
            func=None,
            gui=False,
            archive=b"data",
        )
        assert result is not None
        # Read back and verify the func is "main"
        data = result.read_bytes()
        trailer = data[-TRAILER_STRUCT.size :]
        json_len, magic = TRAILER_STRUCT.unpack(trailer)
        meta_bytes = data[len(data) - TRAILER_STRUCT.size - json_len : len(data) - TRAILER_STRUCT.size]
        metadata = json.loads(meta_bytes.decode("utf-8"))
        assert metadata["func"] == "main"

    def test_returns_none_when_template_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_get_template(gui: bool) -> None:
            return None
        monkeypatch.setattr(launcher, "get_template_exe", fake_get_template)
        result = launcher.build_launcher_for_script(
            launchers_dir=tmp_path,
            script_name="noexe",
            module="mod",
            func="main",
            gui=False,
        )
        assert result is None

    def test_gui_exe_size(self, tmp_path: Path) -> None:
        console = launcher.build_launcher_for_script(
            launchers_dir=tmp_path,
            script_name="cli",
            module="m",
            func="m",
            gui=False,
            archive=b"x",
        )
        gui = launcher.build_launcher_for_script(
            launchers_dir=tmp_path,
            script_name="viewer",
            module="v",
            func="v",
            gui=True,
            archive=b"x",
        )
        assert console is not None
        assert gui is not None
        # Both templates exist but differ in size (subsystem)
        assert console.stat().st_size != gui.stat().st_size
