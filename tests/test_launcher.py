from __future__ import annotations

import json
import posixpath as _pp
from pathlib import Path

import pytest

from uvpacker import launcher
from uvpacker.domain.errors import ConfigError
from uvpacker.launcher._payload import _make_payload
from uvpacker.launcher._payload import MAGIC, TRAILER_STRUCT


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

    def test_rejects_path_traversal_script_name(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="Invalid script name"):
            launcher.build_launcher_for_script(
                launchers_dir=tmp_path,
                script_name="../evil",
                module="demo.main",
                func="main",
                gui=False,
                archive=b"payload",
            )


class _MockArchive:
    """Minimal mock archive duplicating the embedded _MemZip surface for tests."""

    def __init__(self) -> None:
        self._dirs: set[str] = {"", "pkg", "pkg/sub", "pkg/sub/deep"}
        self._files: set[str] = {
            "pkg/__init__.py",
            "pkg/mod.py",
            "pkg/sub/__init__.py",
            "pkg/sub/deep/asset.txt",
            "data.txt",
        }

    def is_dir(self, path: str) -> bool:
        return path.strip("/") in self._dirs

    def is_file(self, path: str) -> bool:
        return path.strip("/") in self._files

    def children(self, path: str) -> list[str]:
        prefix = path.strip("/")
        prefix = prefix + "/" if prefix else ""
        names: set[str] = set()
        for name in self._files:
            if not name.startswith(prefix) or name == prefix:
                continue
            tail = name[len(prefix) :]
            if tail:
                names.add(tail.split("/", 1)[0])
        for name in self._dirs:
            if not name:
                continue
            entry = name + "/"
            if not entry.startswith(prefix) or entry == prefix:
                continue
            tail = entry[len(prefix) :].strip("/")
            if tail:
                names.add(tail.split("/", 1)[0])
        return sorted(names)

    def read(self, path: str) -> bytes:
        return b"content"


class _MemTraversable:
    """Mirrors the embedded _MemTraversable in launcher.c's INIT_SCRIPT."""

    def __init__(self, archive: _MockArchive, path: str) -> None:
        self._archive = archive
        self._path = path.strip("/")

    @property
    def name(self) -> str:
        return "" if not self._path else self._path.rsplit("/", 1)[-1]

    def is_dir(self) -> bool:
        return self._archive.is_dir(self._path)

    def is_file(self) -> bool:
        return self._archive.is_file(self._path)

    def iterdir(self):
        if not self.is_dir():
            return iter(())
        return iter(
            _MemTraversable(self._archive, _pp.join(self._path, child) if self._path else child)
            for child in self._archive.children(self._path)
        )

    def joinpath(self, *children: str) -> _MemTraversable:
        new_path = self._path
        for child in children:
            new_path = _pp.join(new_path, child) if new_path else child
        return _MemTraversable(self._archive, new_path)

    def __truediv__(self, child: str) -> _MemTraversable:
        return self.joinpath(child)


class TestTraversableCompat:
    """Validates _MemTraversable joinpath / truediv behavior."""

    def setup_method(self) -> None:
        self.archive = _MockArchive()

    def test_joinpath_single_arg(self) -> None:
        t = _MemTraversable(self.archive, "pkg/mod")
        child = t.joinpath("submod")
        assert child._path == "pkg/mod/submod"

    def test_joinpath_multi_arg(self) -> None:
        t = _MemTraversable(self.archive, "pkg")
        child = t.joinpath("sub", "deep", "asset.txt")
        assert child._path == "pkg/sub/deep/asset.txt"

    def test_joinpath_empty_root(self) -> None:
        t = _MemTraversable(self.archive, "")
        child = t.joinpath("data.txt")
        assert child._path == "data.txt"

    def test_joinpath_empty_root_multi(self) -> None:
        t = _MemTraversable(self.archive, "")
        child = t.joinpath("pkg", "sub", "asset.txt")
        assert child._path == "pkg/sub/asset.txt"

    def test_truediv_single(self) -> None:
        t = _MemTraversable(self.archive, "pkg")
        child = t / "mod.py"
        assert child._path == "pkg/mod.py"
        assert child.is_file()

    def test_truediv_chain(self) -> None:
        t = _MemTraversable(self.archive, "")
        child = t / "pkg" / "sub" / "deep" / "asset.txt"
        assert child._path == "pkg/sub/deep/asset.txt"
        assert child.is_file()

    def test_truediv_from_joinpath(self) -> None:
        """__truediv__ delegates to joinpath, matching semantics."""
        t = _MemTraversable(self.archive, "pkg")
        via_join = t.joinpath("sub", "deep")
        via_div = t / "sub" / "deep"
        assert via_join._path == via_div._path
        assert via_join._path == "pkg/sub/deep"

    def test_iterdir_resolution_via_joinpath(self) -> None:
        """iterdir children resolve correctly when combined with joinpath."""
        t = _MemTraversable(self.archive, "pkg")
        children = list(t.iterdir())
        assert all(isinstance(c, _MemTraversable) for c in children)
        assert {c.name for c in children} == {"__init__.py", "mod.py", "sub"}
