from __future__ import annotations

import pytest

from uvpacker.domain.sources import DEFAULT_DOWNLOAD_CONFIG, PackDownloadConfig


class TestPackDownloadConfig:
    def test_default_embed_listing_url(self) -> None:
        assert (
            DEFAULT_DOWNLOAD_CONFIG.embed_listing_url()
            == "https://www.python.org/ftp/python/"
        )

    def test_default_embed_zip_url(self) -> None:
        assert (
            DEFAULT_DOWNLOAD_CONFIG.embed_zip_url("3.12.1")
            == "https://www.python.org/ftp/python/3.12.1/python-3.12.1-embed-amd64.zip"
        )

    def test_custom_embed_listing_url(self) -> None:
        config = PackDownloadConfig(embed_index_base="https://mirror.example.com/python/")
        assert config.embed_listing_url() == "https://mirror.example.com/python/"

    def test_custom_embed_listing_url_no_trailing_slash(self) -> None:
        config = PackDownloadConfig(embed_index_base="https://mirror.example.com/python")
        assert config.embed_listing_url() == "https://mirror.example.com/python/"

    def test_custom_embed_zip_url(self) -> None:
        config = PackDownloadConfig(embed_index_base="https://mirror.example.com/python/")
        assert (
            config.embed_zip_url("3.11.9")
            == "https://mirror.example.com/python/3.11.9/python-3.11.9-embed-amd64.zip"
        )

    def test_config_is_frozen(self) -> None:
        config = PackDownloadConfig(embed_index_base="https://example.com/")
        with pytest.raises(Exception):
            config.embed_index_base = "changed"  # type: ignore[misc]

    def test_config_equality(self) -> None:
        a = PackDownloadConfig(embed_index_base="https://example.com/")
        b = PackDownloadConfig(embed_index_base="https://example.com/")
        c = PackDownloadConfig(embed_index_base="https://other.com/")
        assert a == b
        assert a != c
        assert a != DEFAULT_DOWNLOAD_CONFIG


class TestDefaultDownloadConfig:
    def test_constant_is_pack_download_config(self) -> None:
        assert isinstance(DEFAULT_DOWNLOAD_CONFIG, PackDownloadConfig)

    def test_default_base_is_python_org(self) -> None:
        assert "python.org" in DEFAULT_DOWNLOAD_CONFIG.embed_index_base

    def test_default_is_https(self) -> None:
        assert DEFAULT_DOWNLOAD_CONFIG.embed_index_base.startswith("https://")
