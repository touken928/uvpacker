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
    # cache_dir itself still exists (temp files may be present); only
    # cache-artefacts are removed.
    assert cache_dir.exists()
    assert not list(cache_dir.iterdir())


def test_clear_embed_cache_when_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    result = clear_embed_cache()
    assert result.existed is False
    assert result.files_removed == 0
    assert result.bytes_freed == 0


def test_clear_embed_cache_preserves_temp_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify that in-progress download temp files are not removed."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    cache_dir = get_embed_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    # A completed cache zip that should be removed.
    (cache_dir / "python-3.12.1-embed-amd64.zip").write_bytes(b"cache")
    # An in-progress temp file that must survive.
    tmp_file = cache_dir / "tmp_dl_abc123.zip"
    tmp_file.write_bytes(b"partial")

    result = clear_embed_cache()
    assert result.files_removed == 1  # only the finalised .zip
    assert result.bytes_freed == 5
    # The temp file is still there.
    assert tmp_file.is_file()
    assert tmp_file.read_bytes() == b"partial"
    assert not (cache_dir / "python-3.12.1-embed-amd64.zip").exists()


def test_clear_embed_cache_skips_hidden_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify that hidden/lock files are preserved during clearing."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    cache_dir = get_embed_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    (cache_dir / "python-3.12.1-embed-amd64.zip").write_bytes(b"data")
    lock_file = cache_dir / ".lock"
    lock_file.write_text("locked")

    result = clear_embed_cache()
    assert result.files_removed == 1
    assert lock_file.is_file()
    assert not (cache_dir / "python-3.12.1-embed-amd64.zip").exists()


def test_clear_embed_cache_leftover_part(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Legacy .part files should still be cleaned up."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    cache_dir = get_embed_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    (cache_dir / "python-3.12.1-embed-amd64.zip.part").write_bytes(b"partial")
    # A regular cached file too.
    (cache_dir / "python-3.10.0-embed-amd64.zip").write_bytes(b"older")

    result = clear_embed_cache()
    # both the .zip and the .part should be removed
    assert result.files_removed == 2


def test_clear_embed_cache_preserves_locked_cache_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    cache_dir = get_embed_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    payload = cache_dir / "python-3.12.1-embed-amd64.zip"
    payload.write_bytes(b"cache")
    (cache_dir / "python-3.12.1-embed-amd64.zip.lock").write_text("busy")

    result = clear_embed_cache()
    assert result.files_removed == 0
    assert payload.is_file()


def test_clear_embed_cache_respects_lock_created_mid_scan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    cache_dir = get_embed_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    payload = cache_dir / "python-3.12.1-embed-amd64.zip"
    payload.write_bytes(b"cache")
    original_is_file = Path.is_file
    seen_lock_check = False

    def patched_is_file(self: Path) -> bool:
        nonlocal seen_lock_check
        if self.name == "python-3.12.1-embed-amd64.zip.lock" and not seen_lock_check:
            seen_lock_check = True
            self.write_text("busy")
        return original_is_file(self)

    monkeypatch.setattr(Path, "is_file", patched_is_file)

    result = clear_embed_cache()
    assert result.files_removed == 0
    assert payload.is_file()
