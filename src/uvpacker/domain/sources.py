from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class PackDownloadConfig:
    """
    Where to list/download the Windows ``embed-amd64`` zip.

    ``embed_index_base`` must follow the same layout as python.org: each release
    is a subdirectory ``{major}.{minor}.{patch}/`` containing
    ``python-{version}-embed-amd64.zip``.
    """

    embed_index_base: str

    def embed_listing_url(self) -> str:
        return self.embed_index_base.rstrip("/") + "/"

    def embed_zip_url(self, version: str) -> str:
        return f"{self.embed_listing_url()}{version}/python-{version}-embed-amd64.zip"


DEFAULT_DOWNLOAD_CONFIG = PackDownloadConfig(
    embed_index_base="https://www.python.org/ftp/python/",
)
