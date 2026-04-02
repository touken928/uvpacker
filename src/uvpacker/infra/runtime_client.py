from __future__ import annotations

import pathlib
import re
import shutil
import urllib.request
import zipfile

from ..domain.errors import ConfigError, RuntimeResolveError
from ..domain.sources import DEFAULT_DOWNLOAD_CONFIG, PackDownloadConfig
from ..view.ui import info
from .cache_store import get_embed_cache_dir

EMBED_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)/")


def require_exact_minor_from_requires(requires_python: str | None) -> str:
    """Extract the X.Y minor version from a '==X.Y.*' requires-python spec."""
    if requires_python is None:
        raise ConfigError(
            "`project.requires-python` must be set and use the '==X.Y.*' format.",
        )

    m = re.fullmatch(r"==(\d+\.\d+)\.\*", requires_python.strip())
    if not m:
        raise ConfigError(
            "uvpack requires `project.requires-python` to be an exact minor "
            "constraint of the form '==X.Y.*', for example '==3.11.*'.",
        )
    return m.group(1)


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

    for major, minor_part, patch in sorted(candidates, key=lambda t: t[2], reverse=True):
        version = f"{major}.{minor_part}.{patch}"
        url = download.embed_zip_url(version)
        if _head_exists(url):
            return version

    raise RuntimeResolveError(
        f"Could not find a Windows 64-bit embedded runtime for minor {minor!r} "
        f"(checked under {index_url!r}).",
    )


def download_and_extract_embedded_runtime(
    python_version: str,
    dest_dir: pathlib.Path,
    *,
    download: PackDownloadConfig = DEFAULT_DOWNLOAD_CONFIG,
) -> None:
    """
    Download and unpack the official CPython embedded runtime for Windows.

    The ``embed-amd64`` zip is stored under ``~/.cache/uvpacker/embed`` (or
    ``$XDG_CACHE_HOME/uvpacker/embed``) so repeated packs skip re-downloading.
    """
    url = download.embed_zip_url(python_version)
    cache_name = f"python-{python_version}-embed-amd64.zip"
    cache_dir = get_embed_cache_dir()
    cache_zip = cache_dir / cache_name
    cache_dir.mkdir(parents=True, exist_ok=True)

    if _is_valid_cached_zip(cache_zip):
        info(f"Embedded runtime {python_version} from cache ({cache_dir}).")
        shutil.unpack_archive(str(cache_zip), str(dest_dir))
        return

    if cache_zip.is_file():
        try:
            cache_zip.unlink()
        except OSError:
            pass

    part_path = cache_dir / (cache_name + ".part")
    info(
        f"Downloading embedded runtime {python_version} from {url!r} into {cache_dir} ...",
    )
    try:
        try:
            with urllib.request.urlopen(url) as resp, part_path.open("wb") as f:
                shutil.copyfileobj(resp, f)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeResolveError(
                f"Failed to download embedded runtime from {url!r}: {exc}",
            ) from exc
        part_path.replace(cache_zip)
    finally:
        if part_path.is_file():
            try:
                part_path.unlink()
            except OSError:
                pass

    shutil.unpack_archive(str(cache_zip), str(dest_dir))


def _fetch_text(url: str, action: str) -> str:
    try:
        with urllib.request.urlopen(url) as resp:
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
        with urllib.request.urlopen(req):  # noqa: S310
            return True
    except Exception:
        return False


def _is_valid_cached_zip(path: pathlib.Path) -> bool:
    return path.is_file() and path.stat().st_size > 0 and zipfile.is_zipfile(path)
