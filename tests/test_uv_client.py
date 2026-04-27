from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

from uvpacker.domain.errors import BuildError
from uvpacker.domain.sources import DEFAULT_DOWNLOAD_CONFIG
from uvpacker.infra import uv_client


class TestPythonMajorMinor:
    def test_three_part_version(self) -> None:
        assert uv_client._python_major_minor("3.12.1") == "3.12"

    def test_two_part_version(self) -> None:
        assert uv_client._python_major_minor("3.12") == "3.12"

    def test_nightly_suffix(self) -> None:
        assert uv_client._python_major_minor("3.13.0a1") == "3.13"

    def test_invalid_version_raises(self) -> None:
        with pytest.raises(BuildError, match="Invalid Python version"):
            uv_client._python_major_minor("3")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(BuildError, match="Invalid Python version"):
            uv_client._python_major_minor("")


class TestTail:
    def test_short_output(self) -> None:
        result = uv_client._tail("line1\nline2\nline3")
        assert result == "line1 | line2 | line3"

    def test_truncates_to_last_six_lines(self) -> None:
        lines = "\n".join(f"line{i}" for i in range(10))
        result = uv_client._tail(lines)
        parts = result.split(" | ")
        assert len(parts) == 6
        assert parts == ["line4", "line5", "line6", "line7", "line8", "line9"]

    def test_empty_string(self) -> None:
        assert uv_client._tail("") == "No output."

    def test_whitespace_only(self) -> None:
        assert uv_client._tail("  \n  \t  \n") == "No output."

    def test_single_line(self) -> None:
        assert uv_client._tail("only line") == "only line"

    def test_custom_max_lines(self) -> None:
        lines = "\n".join(str(i) for i in range(20))
        result = uv_client._tail(lines, max_lines=3)
        assert result == "17 | 18 | 19"


class TestValidateBuiltWheel:
    def test_pure_python_wheel_non_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        wheel = Path("/tmp/demo-0.1.0-py3-none-any.whl")
        uv_client._validate_built_wheel(wheel)  # should not raise

    def test_pure_python_wheel_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        wheel = Path("/tmp/demo-0.1.0-py3-none-any.whl")
        uv_client._validate_built_wheel(wheel)  # should not raise

    def test_non_any_wheel_on_linux_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        wheel = Path("/tmp/demo-0.1.0-cp312-abi3-linux_x86_64.whl")
        with pytest.raises(BuildError, match="Cross-platform packaging"):
            uv_client._validate_built_wheel(wheel)

    def test_non_any_wheel_on_macos_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        wheel = Path("/tmp/demo-0.1.0-cp312-abi3-macosx_11_0_arm64.whl")
        with pytest.raises(BuildError, match="Cross-platform packaging"):
            uv_client._validate_built_wheel(wheel)

    def test_win_amd64_wheel_on_windows_passes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        wheel = Path("/tmp/demo-0.1.0-cp312-cp312-win_amd64.whl")
        uv_client._validate_built_wheel(wheel)  # should not raise

    def test_non_win_amd64_wheel_on_windows_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        wheel = Path("/tmp/demo-0.1.0-cp312-abi3-win32.whl")
        with pytest.raises(BuildError, match="not compatible with win_amd64"):
            uv_client._validate_built_wheel(wheel)


class TestDiscoverTopLevelImportNames:
    def test_top_level_txt_preferred(self, tmp_path: Path) -> None:
        wheel_path = tmp_path / "demo-0.1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, "w") as wheel:
            wheel.writestr("demo-0.1.0.dist-info/top_level.txt", "demo\n")
            wheel.writestr("demo/__init__.py", "pass\n")
        result = uv_client._discover_top_level_import_names(wheel_path)
        assert result == ("demo",)

    def test_no_top_level_txt_infers_from_files(self, tmp_path: Path) -> None:
        wheel_path = tmp_path / "demo-0.1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, "w") as wheel:
            wheel.writestr("demo-0.1.0.dist-info/METADATA", "Name: demo\n")
            wheel.writestr("demo/__init__.py", "pass\n")
            wheel.writestr("demo/core.py", "pass\n")
            wheel.writestr("helper.py", "pass\n")
        result = uv_client._discover_top_level_import_names(wheel_path)
        assert set(result) == {"demo", "helper"}

    def test_empty_top_level_txt_falls_back(self, tmp_path: Path) -> None:
        wheel_path = tmp_path / "demo-0.1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, "w") as wheel:
            wheel.writestr("demo-0.1.0.dist-info/top_level.txt", "\n")
            wheel.writestr("demo/__init__.py", "pass\n")
        result = uv_client._discover_top_level_import_names(wheel_path)
        assert result == ("demo",)

    def test_empty_txt_with_only_dist_info_falls_back(self, tmp_path: Path) -> None:
        wheel_path = tmp_path / "demo-0.1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, "w") as wheel:
            wheel.writestr("demo-0.1.0.dist-info/WHEEL", "Wheel-Version: 1.0\n")
            # only dist-info and data dirs, no source files
        result = uv_client._discover_top_level_import_names(wheel_path)
        assert result == ()

    def test_single_py_file_module(self, tmp_path: Path) -> None:
        wheel_path = tmp_path / "demo-0.1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, "w") as wheel:
            wheel.writestr("mymodule.py", "def main(): pass\n")
        result = uv_client._discover_top_level_import_names(wheel_path)
        assert result == ("mymodule",)


class TestBuildInstallCommand:
    def test_constructs_correct_command(self, tmp_path: Path) -> None:
        request = uv_client.InstallRequest(
            project_dir=tmp_path / "proj",
            target_dir=tmp_path / "target",
            target_python_version="3.12.1",
            download=DEFAULT_DOWNLOAD_CONFIG,
        )
        wheel_dir = tmp_path / "wheels"
        wheel_path = wheel_dir / "demo-0.1.0-py3-none-any.whl"

        cmd = uv_client._build_install_command(
            request=request,
            wheel_dir=wheel_dir,
            wheel_path=wheel_path,
        )
        assert cmd[0] == "uv"
        assert cmd[1] == "pip"
        assert cmd[2] == "install"
        assert cmd[3] == "--python"
        assert cmd[5] == "--target"
        assert cmd[6] == str(request.target_dir)
        assert cmd[7] == "--python-version"
        assert cmd[8] == "3.12"
        assert cmd[9] == "--python-platform"
        assert cmd[10] == "x86_64-pc-windows-msvc"
        assert cmd[11] == "--only-binary"
        assert cmd[12] == ":all:"
        assert cmd[13] == "--find-links"
        assert cmd[14] == str(wheel_dir)
        assert cmd[15] == str(wheel_path)


class TestRunCommand:
    def test_success(self) -> None:
        uv_client._run_command(["echo", "hello"], cwd=Path.cwd())  # should not raise

    def test_failure_raises(self) -> None:
        with pytest.raises(BuildError, match="Command failed"):
            uv_client._run_command(
                ["python", "-c", "import sys; sys.exit(1)"],
                cwd=Path.cwd(),
            )

    def test_missing_executable_raises(self) -> None:
        with pytest.raises(BuildError, match="Cannot run command"):
            uv_client._run_command(
                ["/definitely/not/an/executable_xyz"],
                cwd=Path.cwd(),
            )


class TestInstallRequest:
    def test_dataclass_fields(self, tmp_path: Path) -> None:
        req = uv_client.InstallRequest(
            project_dir=tmp_path / "proj",
            target_dir=tmp_path / "target",
            target_python_version="3.12.3",
            download=DEFAULT_DOWNLOAD_CONFIG,
        )
        assert req.project_dir == tmp_path / "proj"
        assert req.target_python_version == "3.12.3"
        assert req.download == DEFAULT_DOWNLOAD_CONFIG

    def test_frozen_dataclass(self, tmp_path: Path) -> None:
        req = uv_client.InstallRequest(
            project_dir=tmp_path / "proj",
            target_dir=tmp_path / "target",
            target_python_version="3.12.3",
            download=DEFAULT_DOWNLOAD_CONFIG,
        )
        with pytest.raises(Exception):
            req.target_python_version = "3.11.0"  # type: ignore[misc]
