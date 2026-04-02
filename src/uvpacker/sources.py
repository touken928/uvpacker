from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class PackDownloadConfig:
    """
    Where to list/download the Windows ``embed-amd64`` zip and, optionally,
    which default package index ``uv`` uses for ``uv build`` / ``uv pip install``.

    ``embed_index_base`` must follow the same layout as python.org: each release
    is a subdirectory ``{major}.{minor}.{patch}/`` containing
    ``python-{version}-embed-amd64.zip``.
    """

    embed_index_base: str
    pypi_default_index: str | None = None

    def embed_listing_url(self) -> str:
        return self.embed_index_base.rstrip("/") + "/"

    def embed_zip_url(self, version: str) -> str:
        return f"{self.embed_listing_url()}{version}/python-{version}-embed-amd64.zip"


DEFAULT_DOWNLOAD_CONFIG = PackDownloadConfig(
    embed_index_base="https://www.python.org/ftp/python/",
)

# Named bundles for CLI / API. Add new keys here without touching runtime/uvclient logic.
PACK_DOWNLOAD_PRESETS: dict[str, PackDownloadConfig] = {
    "tsinghua": PackDownloadConfig(
        embed_index_base="https://mirrors.tuna.tsinghua.edu.cn/python/",
        pypi_default_index="https://pypi.tuna.tsinghua.edu.cn/simple",
    ),
}


def pack_download_from_preset(name: str | None) -> PackDownloadConfig:
    """Resolve a preset label; ``None`` or ``\"default\"`` → official python.org / default PyPI."""
    if name is None:
        return DEFAULT_DOWNLOAD_CONFIG
    key = name.strip().lower()
    if key in ("", "default"):
        return DEFAULT_DOWNLOAD_CONFIG
    try:
        return PACK_DOWNLOAD_PRESETS[key]
    except KeyError as exc:
        known = ", ".join(sorted(PACK_DOWNLOAD_PRESETS))
        raise ValueError(
            f"Unknown download preset {name!r}; use 'default' or one of: {known}",
        ) from exc
