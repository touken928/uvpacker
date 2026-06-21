from __future__ import annotations

import pathlib

import pytest

from uvpacker.domain.errors import BuildError, ConfigError
from uvpacker.domain.models import ProjectConfig, ScriptDefinition
from uvpacker.domain.rules import (
    require_exact_minor_from_requires,
    validate_embeddable_file,
    validate_output_dir,
    validate_output_dir_name,
    validate_project_config,
    validate_script_name,
)


class TestRequireExactMinorFromRequires:
    def test_valid_exact_minor(self) -> None:
        assert require_exact_minor_from_requires("==3.12.*") == "3.12"

    def test_valid_with_spaces(self) -> None:
        assert require_exact_minor_from_requires(" ==3.11.* ") == "3.11"

    def test_none_raises(self) -> None:
        with pytest.raises(ConfigError, match="must be set"):
            require_exact_minor_from_requires(None)

    def test_non_exact_spec_raises(self) -> None:
        with pytest.raises(ConfigError, match="exact minor"):
            require_exact_minor_from_requires(">=3.12")

    def test_caret_spec_raises(self) -> None:
        with pytest.raises(ConfigError, match="exact minor"):
            require_exact_minor_from_requires("^3.12")

    def test_wildcard_missing_raises(self) -> None:
        with pytest.raises(ConfigError, match="exact minor"):
            require_exact_minor_from_requires("==3.12")


class TestValidateScriptName:
    def test_valid_name(self) -> None:
        validate_script_name("my-script")  # should not raise

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ConfigError, match="Invalid script name"):
            validate_script_name("")

    def test_dot_name_raises(self) -> None:
        with pytest.raises(ConfigError, match="Invalid script name"):
            validate_script_name(".")

    def test_dotdot_name_raises(self) -> None:
        with pytest.raises(ConfigError, match="Invalid script name"):
            validate_script_name("..")

    def test_control_chars_raises(self) -> None:
        with pytest.raises(ConfigError, match="control characters"):
            validate_script_name("demo\x00app")

    def test_invalid_chars_raises(self) -> None:
        with pytest.raises(ConfigError, match="valid Windows filenames"):
            validate_script_name("../evil")

    def test_ending_space_raises(self) -> None:
        with pytest.raises(ConfigError, match="must not end with space"):
            validate_script_name("script ")

    def test_ending_dot_raises(self) -> None:
        with pytest.raises(ConfigError, match="must not end with"):
            validate_script_name("script.")

    def test_reserved_windows_name_raises(self) -> None:
        with pytest.raises(ConfigError, match="reserved Windows device names"):
            validate_script_name("CON")

    def test_reserved_windows_name_with_extension_raises(self) -> None:
        with pytest.raises(ConfigError, match="reserved Windows device names"):
            validate_script_name("CON.txt")


class TestValidateOutputDirName:
    def test_valid_name(self) -> None:
        validate_output_dir_name("my-app")  # should not raise

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ConfigError, match="single path segment"):
            validate_output_dir_name("")

    def test_name_with_slash_raises(self) -> None:
        with pytest.raises(ConfigError, match="single path segment"):
            validate_output_dir_name("a/b")

    def test_name_with_backslash_raises(self) -> None:
        with pytest.raises(ConfigError, match="single path segment"):
            validate_output_dir_name("a\\b")


class TestValidateOutputDir:
    def test_rejects_project_dir(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(ConfigError, match="must not be the project directory"):
            validate_output_dir(tmp_path, tmp_path)

    def test_rejects_output_containing_project(self, tmp_path: pathlib.Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        with pytest.raises(ConfigError, match="must not contain"):
            validate_output_dir(project_dir, tmp_path)

    def test_rejects_root(self, tmp_path: pathlib.Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        with pytest.raises(ConfigError, match="filesystem root"):
            validate_output_dir(project_dir, pathlib.Path("/"))

    def test_rejects_home(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: home_dir))
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        validate_output_dir(project_dir, home_dir)

    def test_valid_output(self, tmp_path: pathlib.Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        output_dir = tmp_path / "dist" / "my-app"
        validate_output_dir(project_dir, output_dir)  # should not raise


class TestValidateProjectConfig:
    def _make_cfg(
        self,
        *,
        name: str = "demo",
        requires_python: str | None = "==3.12.*",
        scripts: list[ScriptDefinition] | None = None,
        build_system: dict | None = None,
    ) -> ProjectConfig:
        if scripts is None:
            scripts = [ScriptDefinition(name="demo", target="demo.main:main")]
        if build_system is None:
            build_system = {"requires": ["uv_build"], "build-backend": "uv_build"}
        return ProjectConfig(
            root=pathlib.Path("/fake"),
            name=name,
            requires_python=requires_python,
            scripts=scripts,
            build_system=build_system,
        )

    def test_valid_config(self) -> None:
        cfg = self._make_cfg()
        validate_project_config(cfg)  # should not raise

    def test_no_scripts_raises(self) -> None:
        cfg = self._make_cfg(scripts=[])
        with pytest.raises(ConfigError, match="No .*scripts"):
            validate_project_config(cfg)

    def test_duplicate_script_names_raises(self) -> None:
        cfg = self._make_cfg(
            scripts=[
                ScriptDefinition(name="app", target="a:main", gui=False),
                ScriptDefinition(name="app", target="b:main", gui=True),
            ]
        )
        with pytest.raises(ConfigError, match="Duplicate script names"):
            validate_project_config(cfg)

    def test_no_build_system_raises(self) -> None:
        cfg = self._make_cfg(build_system={})
        with pytest.raises(ConfigError, match="No .*build-system"):
            validate_project_config(cfg)

    def test_none_requires_python_raises(self) -> None:
        cfg = self._make_cfg(requires_python=None)
        with pytest.raises(ConfigError, match="must be set"):
            validate_project_config(cfg)

    def test_invalid_requires_python_format_raises(self) -> None:
        cfg = self._make_cfg(requires_python=">=3.10")
        with pytest.raises(ConfigError, match="exact minor"):
            validate_project_config(cfg)

    def test_invalid_script_name_raises(self) -> None:
        cfg = self._make_cfg(
            scripts=[ScriptDefinition(name="../evil", target="demo.main:main")]
        )
        with pytest.raises(ConfigError, match="Invalid script name"):
            validate_project_config(cfg)

    def test_reserved_windows_script_name_raises(self) -> None:
        cfg = self._make_cfg(
            scripts=[ScriptDefinition(name="CON", target="demo.main:main")]
        )
        with pytest.raises(ConfigError, match="reserved Windows device names"):
            validate_project_config(cfg)

    def test_control_character_script_name_raises(self) -> None:
        cfg = self._make_cfg(
            scripts=[ScriptDefinition(name="demo\x00app", target="demo.main:main")]
        )
        with pytest.raises(ConfigError, match="control characters"):
            validate_project_config(cfg)

    def test_reserved_windows_script_name_with_extension_raises(self) -> None:
        cfg = self._make_cfg(
            scripts=[ScriptDefinition(name="CON.txt", target="demo.main:main")]
        )
        with pytest.raises(ConfigError, match="reserved Windows device names"):
            validate_project_config(cfg)

    def test_invalid_project_name_for_default_output_raises(self) -> None:
        cfg = self._make_cfg(name="../../escape")
        with pytest.raises(ConfigError, match="default output directory name"):
            validate_project_config(cfg)


class TestValidateEmbeddableFile:
    def test_pyd_raises(self) -> None:
        with pytest.raises(BuildError, match="cannot be embedded"):
            validate_embeddable_file("demo", pathlib.Path("demo/fast.pyd"))

    def test_dll_raises(self) -> None:
        with pytest.raises(BuildError, match="cannot be embedded"):
            validate_embeddable_file("demo", pathlib.Path("demo/native.dll"))

    def test_so_raises(self) -> None:
        with pytest.raises(BuildError, match="cannot be embedded"):
            validate_embeddable_file("demo", pathlib.Path("demo/impl.so"))

    def test_dylib_raises(self) -> None:
        with pytest.raises(BuildError, match="cannot be embedded"):
            validate_embeddable_file("demo", pathlib.Path("demo/core.dylib"))

    def test_pyc_is_allowed(self) -> None:
        validate_embeddable_file("demo", pathlib.Path("demo/__init__.pyc"))

    def test_py_is_allowed(self) -> None:
        validate_embeddable_file("demo", pathlib.Path("demo/main.py"))

    def test_txt_is_allowed(self) -> None:
        validate_embeddable_file("demo", pathlib.Path("demo/data.txt"))
