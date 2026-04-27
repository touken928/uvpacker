from __future__ import annotations

import io
import urllib.request
import zipfile
from pathlib import Path

import pytest

from uvpacker.domain.errors import ConfigError, RuntimeResolveError
from uvpacker.domain.sources import PackDownloadConfig
from uvpacker.infra import runtime_client


class TestRequireExactMinorFromRequires:
    def test_valid_exact_minor(self) -> None:
        assert runtime_client.require_exact_minor_from_requires("==3.12.*") == "3.12"

    def test_valid_with_spaces(self) -> None:
        assert runtime_client.require_exact_minor_from_requires(" ==3.11.* ") == "3.11"

    def test_none_raises(self) -> None:
        with pytest.raises(ConfigError, match="must be set"):
            runtime_client.require_exact_minor_from_requires(None)

    def test_non_exact_spec_raises(self) -> None:
        with pytest.raises(ConfigError, match="exact minor"):
            runtime_client.require_exact_minor_from_requires(">=3.12")

    def test_caret_spec_raises(self) -> None:
        with pytest.raises(ConfigError, match="exact minor"):
            runtime_client.require_exact_minor_from_requires("^3.12")

    def test_wildcard_missing_raises(self) -> None:
        with pytest.raises(ConfigError, match="exact minor"):
            runtime_client.require_exact_minor_from_requires("==3.12")


class TestCollectCandidatesForMinor:
    def test_single_candidate(self) -> None:
        html = "3.12.1/"
        result = runtime_client._collect_candidates_for_minor(html, "3.12")
        assert result == [(3, 12, 1)]

    def test_multiple_patches_sorted_by_position(self) -> None:
        html = "3.12.1/\n3.12.3/\n3.12.0/"
        result = runtime_client._collect_candidates_for_minor(html, "3.12")
        assert result == [(3, 12, 1), (3, 12, 3), (3, 12, 0)]

    def test_filters_other_minors(self) -> None:
        html = "3.11.5/\n3.12.1/\n3.13.0/"
        result = runtime_client._collect_candidates_for_minor(html, "3.12")
        assert result == [(3, 12, 1)]

    def test_filters_other_majors(self) -> None:
        html = "2.7.18/\n3.12.1/"
        result = runtime_client._collect_candidates_for_minor(html, "3.12")
        assert result == [(3, 12, 1)]

    def test_no_match_returns_empty(self) -> None:
        html = "3.11.0/"
        result = runtime_client._collect_candidates_for_minor(html, "3.12")
        assert result == []

    def test_two_digit_minor(self) -> None:
        html = "3.10.12/"
        result = runtime_client._collect_candidates_for_minor(html, "3.10")
        assert result == [(3, 10, 12)]


class TestIsValidCachedZip:
    def test_valid_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "test.zip"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("dummy", b"hello")
        assert runtime_client._is_valid_cached_zip(p)

    def test_non_existent_file(self, tmp_path: Path) -> None:
        assert not runtime_client._is_valid_cached_zip(tmp_path / "missing.zip")

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.zip"
        p.write_bytes(b"")
        assert not runtime_client._is_valid_cached_zip(p)

    def test_not_a_zip(self, tmp_path: Path) -> None:
        p = tmp_path / "not_zip.zip"
        p.write_text("plain text", encoding="utf-8")
        assert not runtime_client._is_valid_cached_zip(p)

    def test_directory(self, tmp_path: Path) -> None:
        d = tmp_path / "dir"
        d.mkdir()
        assert not runtime_client._is_valid_cached_zip(d)


class TestHeadExists:
    def test_url_returns_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_urlopen(req: urllib.request.Request) -> io.BytesIO:
            assert req.method == "HEAD"
            return io.BytesIO(b"")
        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert runtime_client._head_exists("https://example.com/test.zip")

    def test_url_404_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_urlopen(req: urllib.request.Request) -> None:
            raise urllib.error.HTTPError("url", 404, "Not Found", {}, io.BytesIO(b""))
        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert not runtime_client._head_exists("https://example.com/missing.zip")

    def test_url_error_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_urlopen(req: urllib.request.Request) -> None:
            raise OSError("connection refused")
        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        assert not runtime_client._head_exists("https://invalid.example.com")


class TestFetchText:
    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_urlopen(url: str) -> io.BytesIO:
            return io.BytesIO(b"<html>index</html>")
        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        result = runtime_client._fetch_text("https://example.com", "test action")
        assert result == "<html>index</html>"

    def test_network_error_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_urlopen(url: str) -> None:
            raise OSError("timeout")
        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(RuntimeResolveError, match="Failed to test action"):
            runtime_client._fetch_text("https://example.com", "test action")


class TestResolveLatestEmbedForMinor:
    def test_resolves_highest_patch_with_available_zip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        html = '<a href="3.12.1/">3.12.1/</a>\n<a href="3.12.3/">3.12.3/</a>\n<a href="3.12.0/">3.12.0/</a>'
        monkeypatch.setattr(runtime_client, "_fetch_text", lambda url, action: html)

        head_results: dict[str, bool] = {
            "https://www.python.org/ftp/python/3.12.3/python-3.12.3-embed-amd64.zip": True,
            "https://www.python.org/ftp/python/3.12.1/python-3.12.1-embed-amd64.zip": True,
            "https://www.python.org/ftp/python/3.12.0/python-3.12.0-embed-amd64.zip": False,
        }

        def fake_head(url: str) -> bool:
            return head_results[url]

        monkeypatch.setattr(runtime_client, "_head_exists", fake_head)
        result = runtime_client.resolve_latest_embed_for_minor("3.12")
        assert result == "3.12.3"

    def test_no_candidates_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(runtime_client, "_fetch_text", lambda url, action: "")
        with pytest.raises(RuntimeResolveError, match="No patch releases found"):
            runtime_client.resolve_latest_embed_for_minor("3.99")

    def test_no_head_succeeds_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        html = '<a href="3.12.0/">3.12.0/</a>'
        monkeypatch.setattr(runtime_client, "_fetch_text", lambda url, action: html)
        monkeypatch.setattr(runtime_client, "_head_exists", lambda url: False)
        with pytest.raises(RuntimeResolveError, match="Could not find a Windows 64-bit"):
            runtime_client.resolve_latest_embed_for_minor("3.12")

    def test_custom_download_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        custom = PackDownloadConfig(embed_index_base="https://mirror.example.com/python/")
        html = '<a href="3.12.1/">3.12.1/</a>'
        called_url: list[str] = []

        def fake_fetch(url: str, action: str) -> str:
            called_url.append(url)
            return html

        def fake_head(url: str) -> bool:
            called_url.append(url)
            return True

        monkeypatch.setattr(runtime_client, "_fetch_text", fake_fetch)
        monkeypatch.setattr(runtime_client, "_head_exists", fake_head)
        result = runtime_client.resolve_latest_embed_for_minor("3.12", download=custom)
        assert result == "3.12.1"
        assert called_url[0] == "https://mirror.example.com/python/"
        assert (
            called_url[1]
            == "https://mirror.example.com/python/3.12.1/python-3.12.1-embed-amd64.zip"
        )


class TestDownloadAndExtractEmbeddedRuntime:
    def test_uses_cached_zip_when_valid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_dir = tmp_path / "uvpacker" / "embed"
        monkeypatch.setattr(
            runtime_client, "get_embed_cache_dir", lambda: cache_dir
        )
        cache_dir.mkdir(parents=True)
        cache_zip = cache_dir / "python-3.12.1-embed-amd64.zip"
        with zipfile.ZipFile(cache_zip, "w") as zf:
            zf.writestr("python.exe", b"fake")

        dest = tmp_path / "dest"
        dest.mkdir()

        runtime_client.download_and_extract_embedded_runtime("3.12.1", dest)
        assert (dest / "python.exe").is_file()

    def test_downloads_when_no_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_dir = tmp_path / "uvpacker" / "embed"
        monkeypatch.setattr(
            runtime_client, "get_embed_cache_dir", lambda: cache_dir
        )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("python312.dll", b"dll")

        def fake_urlopen(url: str) -> io.BytesIO:
            return io.BytesIO(zip_buffer.getvalue())

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        dest = tmp_path / "dest"
        dest.mkdir()

        runtime_client.download_and_extract_embedded_runtime("3.12.1", dest)
        assert (dest / "python312.dll").is_file()
        assert (cache_dir / "python-3.12.1-embed-amd64.zip").is_file()

    def test_replaces_corrupt_cached_zip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_dir = tmp_path / "uvpacker" / "embed"
        monkeypatch.setattr(
            runtime_client, "get_embed_cache_dir", lambda: cache_dir
        )
        cache_dir.mkdir(parents=True)
        cache_zip = cache_dir / "python-3.12.1-embed-amd64.zip"
        cache_zip.write_text("corrupt", encoding="utf-8")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("python.exe", b"new")

        def fake_urlopen(url: str) -> io.BytesIO:
            return io.BytesIO(zip_buffer.getvalue())

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        dest = tmp_path / "dest"
        dest.mkdir()

        runtime_client.download_and_extract_embedded_runtime("3.12.1", dest)
        assert (dest / "python.exe").is_file()

    def test_download_failure_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_dir = tmp_path / "uvpacker" / "embed"
        monkeypatch.setattr(
            runtime_client, "get_embed_cache_dir", lambda: cache_dir
        )

        def fake_urlopen(url: str) -> None:
            raise OSError("network error")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        dest = tmp_path / "dest"
        dest.mkdir()

        with pytest.raises(RuntimeResolveError, match="Failed to download"):
            runtime_client.download_and_extract_embedded_runtime("3.12.1", dest)
