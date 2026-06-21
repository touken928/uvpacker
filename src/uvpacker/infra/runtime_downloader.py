from __future__ import annotations

import re
import urllib.request

from ..domain.errors import RuntimeResolveError
from ..domain.sources import DEFAULT_DOWNLOAD_CONFIG, PackDownloadConfig

# Timeout for HTTP requests used during version resolution (seconds).
_LIST_TIMEOUT: float = 15.0

EMBED_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)/")


def resolve_latest_embed_for_minor(
    minor: str,
    *,
    download: PackDownloadConfig = DEFAULT_DOWNLOAD_CONFIG,
) -> str:
    """
    Resolve the latest CPython patch version that provides a Windows 64-bit
    embedded runtime for a given X.Y minor.
    """
    index_url = download.embed_listing_url()
    html = _fetch_text(index_url, "query embed index for available versions")
    candidates = _collect_candidates_for_minor(html=html, minor=minor)

    if not candidates:
        raise RuntimeResolveError(
            f"No patch releases found at embed index {index_url!r} for minor {minor!r}.",
        )

    for major, minor_part, patch in sorted(
        candidates, key=lambda t: t[2], reverse=True
    ):
        version = f"{major}.{minor_part}.{patch}"
        url = download.embed_zip_url(version)
        if _head_exists(url):
            return version

    raise RuntimeResolveError(
        f"Could not find a Windows 64-bit embedded runtime for minor {minor!r} "
        f"(checked under {index_url!r}).",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_text(url: str, action: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=_LIST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeResolveError(f"Failed to {action} ({url!r}): {exc}") from exc


def _collect_candidates_for_minor(html: str, minor: str) -> list[tuple[int, int, int]]:
    candidates: list[tuple[int, int, int]] = []
    for match in EMBED_VERSION_PATTERN.finditer(html):
        major, minor_part, patch = (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
        if f"{major}.{minor_part}" == minor:
            candidates.append((major, minor_part, patch))
    return candidates


def _head_exists(url: str) -> bool:
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=_LIST_TIMEOUT):  # noqa: S310
            return True
    except Exception:
        return False
