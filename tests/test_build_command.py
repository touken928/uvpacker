from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from uvpacker.app.commands import build


def test_build_command_uses_default_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    out = tmp_path / "out"
    captured: dict[str, object] = {}

    def fake_pack_project(*, project_dir: Path, output_dir: Path | None, download: object) -> None:
        captured["project_dir"] = project_dir
        captured["output_dir"] = output_dir
        captured["download"] = download

    monkeypatch.setattr(build, "pack_project", fake_pack_project)

    rc = build.run_build_command(
        argparse.Namespace(project_dir=str(project), output=str(out)),
    )
    assert rc == 0
    assert captured["project_dir"] == project.resolve()
    assert captured["output_dir"] == out.resolve()
    assert captured["download"] is None
