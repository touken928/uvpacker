from __future__ import annotations

from pathlib import Path

import pytest

from uvpacker.infra.cache_store import clear_embed_cache, get_embed_cache_dir


def test_clear_embed_cache_removes_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    cache_dir = get_embed_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = cache_dir / "python-3.12.1-embed-amd64.zip"
    payload.write_bytes(b"12345")

    result = clear_embed_cache()
    assert result.existed is True
    assert result.files_removed == 1
    assert result.bytes_freed == 5
    assert not cache_dir.exists()


def test_clear_embed_cache_when_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    result = clear_embed_cache()
    assert result.existed is False
    assert result.files_removed == 0
    assert result.bytes_freed == 0
