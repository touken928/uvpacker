from __future__ import annotations

import pathlib
from pathlib import Path

import pytest

from uvpacker.domain.errors import BuildError, ConfigError
from uvpacker.services import packer


class TestRequireProjectDir:
    def test_existing_project_dir(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[project]\nname='test'\n")
        result = packer._require_project_dir(proj)
        assert result == proj / "pyproject.toml"

    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="does not exist"):
            packer._require_project_dir(tmp_path / "no_such_dir")

    def test_missing_pyproject_toml_raises(self, tmp_path: Path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        with pytest.raises(ConfigError, match="No pyproject.toml found"):
            packer._require_project_dir(proj)

    def test_file_not_dir_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("hello")
        with pytest.raises(ConfigError, match="does not exist"):
            packer._require_project_dir(f)


class TestLoadProjectConfig:
    def test_basic_config(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "demo"\nrequires-python = "==3.12.*"\n'
            "[project.scripts]\ndemo = \"demo.main:main\"\n"
            "[build-system]\nrequires = [\"uv_build\"]\n"
            'build-backend = "uv_build"\n'
        )
        cfg = packer._load_project_config(pyproject)
        assert cfg.name == "demo"
        assert cfg.requires_python == "==3.12.*"
        assert len(cfg.scripts) == 1
        assert cfg.scripts[0].name == "demo"
        assert cfg.scripts[0].target == "demo.main:main"
        assert cfg.scripts[0].gui is False
        assert cfg.root == tmp_path
        assert "requires" in cfg.build_system

    def test_gui_scripts(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "app"\nrequires-python = "==3.12.*"\n'
            "[project.scripts]\ncli = \"app.cli:main\"\n"
            "[project.gui-scripts]\nviewer = \"app.viewer:main\"\n"
            "[build-system]\nrequires = [\"uv_build\"]\n"
            'build-backend = "uv_build"\n'
        )
        cfg = packer._load_project_config(pyproject)
        assert len(cfg.scripts) == 2
        assert cfg.scripts[0].name == "cli"
        assert cfg.scripts[0].gui is False
        assert cfg.scripts[1].name == "viewer"
        assert cfg.scripts[1].gui is True

    def test_missing_name_raises(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nrequires-python = "==3.12.*"\n'
            "[project.scripts]\ndemo=\"demo.main:main\"\n"
            "[build-system]\nrequires = [\"uv_build\"]\n"
            'build-backend = "uv_build"\n'
        )
        with pytest.raises(ConfigError, match="project.name"):
            packer._load_project_config(pyproject)

    def test_missing_requires_python_yields_none(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "demo"\n'
            "[project.scripts]\ndemo=\"demo.main:main\"\n"
            "[build-system]\nrequires = [\"uv_build\"]\n"
            'build-backend = "uv_build"\n'
        )
        cfg = packer._load_project_config(pyproject)
        assert cfg.requires_python is None

    def test_empty_scripts_returns_empty_list(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "demo"\nrequires-python = "==3.12.*"\n'
            "[build-system]\nrequires = [\"uv_build\"]\n"
            'build-backend = "uv_build"\n'
        )
        cfg = packer._load_project_config(pyproject)
        assert cfg.scripts == []

    def test_missing_build_system_returns_empty_dict(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "demo"\nrequires-python = "==3.12.*"\n'
            "[project.scripts]\ndemo = \"demo.main:main\"\n"
        )
        cfg = packer._load_project_config(pyproject)
        assert cfg.build_system == {}

    def test_script_without_module_returns_empty_function(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "demo"\nrequires-python = "==3.12.*"\n'
            "[project.scripts]\nentry = \"demo.entry\"\n"
            "[build-system]\nrequires = [\"uv_build\"]\n"
            'build-backend = "uv_build"\n'
        )
        cfg = packer._load_project_config(pyproject)
        # target string has no colon, so partition gives module="demo.entry", func=""
        assert cfg.scripts[0].target == "demo.entry"


class TestValidateProjectConfig:
    def _make_cfg(
        self,
        *,
        name: str = "demo",
        requires_python: str = "==3.12.*",
        scripts: list[packer.ScriptDefinition] | None = None,
        build_system: dict | None = None,
    ) -> packer.ProjectConfig:
        if scripts is None:
            scripts = [packer.ScriptDefinition(name="demo", target="demo.main:main")]
        if build_system is None:
            build_system = {"requires": ["uv_build"], "build-backend": "uv_build"}
        return packer.ProjectConfig(
            root=pathlib.Path("/fake"),
            name=name,
            requires_python=requires_python,
            scripts=scripts,
            build_system=build_system,
        )

    def test_valid_config(self) -> None:
        cfg = self._make_cfg()
        packer._validate_project_config(cfg)  # should not raise

    def test_no_scripts_raises(self) -> None:
        cfg = self._make_cfg(scripts=[])
        with pytest.raises(ConfigError, match="No .*scripts"):
            packer._validate_project_config(cfg)

    def test_duplicate_script_names_raises(self) -> None:
        cfg = self._make_cfg(
            scripts=[
                packer.ScriptDefinition(name="app", target="a:main", gui=False),
                packer.ScriptDefinition(name="app", target="b:main", gui=True),
            ]
        )
        with pytest.raises(ConfigError, match="Duplicate script names"):
            packer._validate_project_config(cfg)

    def test_no_build_system_raises(self) -> None:
        cfg = self._make_cfg(build_system={})
        with pytest.raises(ConfigError, match="No .*build-system"):
            packer._validate_project_config(cfg)

    def test_none_requires_python_raises(self) -> None:
        cfg = self._make_cfg(requires_python=None)
        with pytest.raises(ConfigError, match="must be set"):
            packer._validate_project_config(cfg)

    def test_invalid_requires_python_format_raises(self) -> None:
        cfg = self._make_cfg(requires_python=">=3.10")
        with pytest.raises(ConfigError, match="exact minor"):
            packer._validate_project_config(cfg)


class TestResolveOutputDir:
    def test_explicit_output(self, tmp_path: Path) -> None:
        cfg = packer.ProjectConfig(
            root=tmp_path / "proj",
            name="demo",
            requires_python="==3.12.*",
            scripts=[packer.ScriptDefinition(name="d", target="d:main")],
            build_system={"requires": ["uv_build"]},
        )
        result = packer._resolve_output_dir(cfg, tmp_path, tmp_path / "custom")
        assert result == tmp_path / "custom"

    def test_default_output(self, tmp_path: Path) -> None:
        cfg = packer.ProjectConfig(
            root=tmp_path / "proj",
            name="my-app",
            requires_python="==3.12.*",
            scripts=[packer.ScriptDefinition(name="a", target="a:main")],
            build_system={"requires": ["uv_build"]},
        )
        result = packer._resolve_output_dir(cfg, tmp_path, None)
        assert result == tmp_path / "dist" / "my-app"


class TestPrepareLayout:
    def test_creates_directories(self, tmp_path: Path) -> None:
        output = tmp_path / "out"
        layout = packer._prepare_layout(output)
        assert layout.root == output
        assert layout.runtime == output / "runtime"
        assert layout.packages == output / "packages"
        assert output.is_dir()
        assert layout.runtime.is_dir()
        assert layout.packages.is_dir()

    def test_cleans_existing_output(self, tmp_path: Path) -> None:
        output = tmp_path / "out"
        output.mkdir()
        (output / "old_file.txt").write_text("stale")
        packer._prepare_layout(output)
        assert not (output / "old_file.txt").exists()


class TestPatchEmbeddedRuntimeConfig:
    def test_appends_packages_path_to_pth(self, tmp_path: Path) -> None:
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        pth = runtime / "python312._pth"
        pth.write_text("Lib/site-packages\n", encoding="utf-8")

        packer._patch_embedded_runtime_config(runtime)
        content = pth.read_text(encoding="utf-8")
        assert "..\\packages" in content

    def test_adds_entry_when_not_present(self, tmp_path: Path) -> None:
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        pth = runtime / "python._pth"
        pth.write_text("Lib\n", encoding="utf-8")

        packer._patch_embedded_runtime_config(runtime)
        assert "..\\packages" in pth.read_text(encoding="utf-8")

    def test_no_duplicate_entry(self, tmp_path: Path) -> None:
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        pth = runtime / "python._pth"
        pth.write_text("Lib\n..\\packages\n", encoding="utf-8")

        packer._patch_embedded_runtime_config(runtime)
        # Should not add a second line
        assert pth.read_text(encoding="utf-8").count("..\\packages") == 1

    def test_no_pth_file_silently_ignored(self, tmp_path: Path) -> None:
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        # No .pth file
        packer._patch_embedded_runtime_config(runtime)  # should not raise


class TestResolveProjectRoots:
    def test_returns_normalized_discovered_roots(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "packages"
        app_dir.mkdir()
        # Don't need actual dirs; normalized is just deduplicated
        result = packer._resolve_project_roots(app_dir, ("demo", "util", "demo"), "proj")
        assert result == ("demo", "util")

    def test_fallback_with_package_dir(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "packages"
        app_dir.mkdir()
        (app_dir / "proj").mkdir()
        result = packer._resolve_project_roots(app_dir, (), "proj")
        assert result == ("proj",)

    def test_fallback_with_dash_to_underscore(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "packages"
        app_dir.mkdir()
        (app_dir / "my_app").mkdir()
        result = packer._resolve_project_roots(app_dir, (), "my-app")
        # my-app doesn't exist on disk, only my_app does, so only my_app returned
        assert result == ("my_app",)

    def test_fallback_with_py_module_file(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "packages"
        app_dir.mkdir()
        (app_dir / "app.py").write_text("pass")
        result = packer._resolve_project_roots(app_dir, (), "app")
        assert result == ("app",)

    def test_fallback_with_pyc_module_file(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "packages"
        app_dir.mkdir()
        (app_dir / "lib.pyc").write_bytes(b"")
        result = packer._resolve_project_roots(app_dir, (), "lib")
        assert result == ("lib",)

    def test_fallback_no_match_returns_empty(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "packages"
        app_dir.mkdir()
        result = packer._resolve_project_roots(app_dir, (), "unknown")
        assert result == ()


class TestNormalizeDistributionName:
    def test_lowercase(self) -> None:
        assert packer._normalize_distribution_name("MyProject") == "myproject"

    def test_replaces_dashes_and_underscores(self) -> None:
        assert packer._normalize_distribution_name("my-project_name") == "my-project-name"

    def test_replaces_dots(self) -> None:
        assert packer._normalize_distribution_name("my.project") == "my-project"

    def test_multiple_separators(self) -> None:
        assert packer._normalize_distribution_name("my__project..name") == "my-project-name"


class TestReadMetadataName:
    def test_extracts_name(self, tmp_path: Path) -> None:
        meta = tmp_path / "METADATA"
        meta.write_text(
            "Metadata-Version: 2.1\nName: my-package\nVersion: 0.1.0\n",
            encoding="utf-8",
        )
        assert packer._read_metadata_name(meta) == "my-package"

    def test_no_name_line_returns_none(self, tmp_path: Path) -> None:
        meta = tmp_path / "METADATA"
        meta.write_text(
            "Metadata-Version: 2.1\nVersion: 0.1.0\n",
            encoding="utf-8",
        )
        assert packer._read_metadata_name(meta) is None

    def test_empty_file_returns_none(self, tmp_path: Path) -> None:
        meta = tmp_path / "METADATA"
        meta.write_text("")
        assert packer._read_metadata_name(meta) is None

    def test_name_with_spaces(self, tmp_path: Path) -> None:
        meta = tmp_path / "METADATA"
        meta.write_text("Name:   spaced-name  \n")
        assert packer._read_metadata_name(meta) == "spaced-name"


class TestLogDownloadSources:
    def test_default_config_silent(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from uvpacker.domain.sources import DEFAULT_DOWNLOAD_CONFIG

        packer._log_download_sources(DEFAULT_DOWNLOAD_CONFIG)
        assert "[uvpacker]" not in capsys.readouterr().out

    def test_non_default_config_logs(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from uvpacker.domain.sources import PackDownloadConfig

        custom = PackDownloadConfig(embed_index_base="https://mirror.example.com/python/")
        packer._log_download_sources(custom)
        captured = capsys.readouterr().out
        assert "Non-default embed index" in captured
        assert "mirror.example.com" in captured


class TestRemoveNonRuntimeScriptShims:
    def test_removes_both_bin_and_scripts(self, tmp_path: Path) -> None:
        packages = tmp_path / "packages"
        (packages / "bin").mkdir(parents=True)
        (packages / "Scripts").mkdir(parents=True)
        (packages / "bin" / "uvicorn").write_text("shim")
        (packages / "Scripts" / "uvicorn.exe").write_bytes(b"exe")
        (packages / "requests").mkdir(parents=True)

        packer._remove_non_runtime_script_shims(packages)

        assert not (packages / "bin").exists()
        assert not (packages / "Scripts").exists()
        assert (packages / "requests").exists()

    def test_no_op_when_dirs_missing(self, tmp_path: Path) -> None:
        packages = tmp_path / "packages"
        packages.mkdir()
        packer._remove_non_runtime_script_shims(packages)  # should not raise


class TestRemoveProjectDistInfo:
    def test_removes_matching_dist_info(self, tmp_path: Path) -> None:
        packages = tmp_path / "packages"
        own = packages / "demo_app-0.1.0.dist-info"
        own.mkdir(parents=True)
        (own / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: demo-app\n", encoding="utf-8"
        )

        packer._remove_project_dist_info(packages, "demo_app")
        assert not own.exists()

    def test_keeps_non_matching(self, tmp_path: Path) -> None:
        packages = tmp_path / "packages"
        dep = packages / "requests-2.32.0.dist-info"
        dep.mkdir(parents=True)
        (dep / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: requests\n", encoding="utf-8"
        )

        packer._remove_project_dist_info(packages, "demo")
        assert dep.exists()

    def test_no_dist_info_dirs_present(self, tmp_path: Path) -> None:
        packages = tmp_path / "packages"
        packages.mkdir()
        packer._remove_project_dist_info(packages, "demo")  # should not raise


class TestValidateEmbeddableFile:
    def test_pyd_raises(self) -> None:
        with pytest.raises(BuildError, match="cannot be embedded"):
            packer._validate_embeddable_file("demo", pathlib.Path("demo/fast.pyd"))

    def test_dll_raises(self) -> None:
        with pytest.raises(BuildError, match="cannot be embedded"):
            packer._validate_embeddable_file("demo", pathlib.Path("demo/native.dll"))

    def test_so_raises(self) -> None:
        with pytest.raises(BuildError, match="cannot be embedded"):
            packer._validate_embeddable_file("demo", pathlib.Path("demo/impl.so"))

    def test_dylib_raises(self) -> None:
        with pytest.raises(BuildError, match="cannot be embedded"):
            packer._validate_embeddable_file("demo", pathlib.Path("demo/core.dylib"))

    def test_pyc_is_allowed(self) -> None:
        packer._validate_embeddable_file("demo", pathlib.Path("demo/__init__.pyc"))

    def test_py_is_allowed(self) -> None:
        packer._validate_embeddable_file("demo", pathlib.Path("demo/main.py"))

    def test_txt_is_allowed(self) -> None:
        packer._validate_embeddable_file("demo", pathlib.Path("demo/data.txt"))


class TestExistingProjectDirs:
    def test_existing_dirs(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "packages"
        (app_dir / "pkg_a").mkdir(parents=True)
        (app_dir / "pkg_b").mkdir(parents=True)
        result = packer._existing_project_dirs(app_dir, ("pkg_a", "pkg_b", "pkg_c"))
        assert len(result) == 2
        assert app_dir / "pkg_a" in result
        assert app_dir / "pkg_b" in result

    def test_no_matching_dirs(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "packages"
        app_dir.mkdir()
        result = packer._existing_project_dirs(app_dir, ("nonexistent",))
        assert result == []
