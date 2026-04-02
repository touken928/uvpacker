from __future__ import annotations

import os
import pathlib
import re
import shutil
import urllib.request
import zipfile

from .errors import UvPackError
from .sources import DEFAULT_DOWNLOAD_CONFIG, PackDownloadConfig
from .ui import info


def _embed_cache_dir() -> pathlib.Path:
    """
    Default: ``~/.cache/uvpacker/embed``; respect ``XDG_CACHE_HOME`` when set.
    """
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        base = pathlib.Path(xdg)
    else:
        base = pathlib.Path.home() / ".cache"
    return base / "uvpacker" / "embed"


def require_exact_minor_from_requires(requires_python: str | None) -> str:
    """Extract the X.Y minor version from a '==X.Y.*' requires-python spec."""
    if requires_python is None:
        raise UvPackError(
            "`project.requires-python` must be set and use the '==X.Y.*' format.",
        )

    m = re.fullmatch(r"==(\d+\.\d+)\.\*", requires_python.strip())
    if not m:
        raise UvPackError(
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
    try:
        with urllib.request.urlopen(index_url) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise UvPackError(
            f"Failed to query embed index for available versions ({index_url!r}): {exc}",
        ) from exc

    candidates: list[tuple[int, int, int]] = []
    for match in re.finditer(r"(\d+)\.(\d+)\.(\d+)/", html):
        major, minor_part, patch = (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
        if f"{major}.{minor_part}" == minor:
            candidates.append((major, minor_part, patch))

    if not candidates:
        raise UvPackError(
            f"No patch releases found at embed index {index_url!r} for minor {minor!r}.",
        )

    for major, minor_part, patch in sorted(
        candidates,
        key=lambda t: t[2],
        reverse=True,
    ):
        version = f"{major}.{minor_part}.{patch}"
        url = download.embed_zip_url(version)
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req):  # noqa: S310
                return version
        except Exception:
            continue

    raise UvPackError(
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
    cache_dir = _embed_cache_dir()
    cache_zip = cache_dir / cache_name
    cache_dir.mkdir(parents=True, exist_ok=True)

    if cache_zip.is_file() and cache_zip.stat().st_size > 0 and zipfile.is_zipfile(cache_zip):
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
            raise UvPackError(
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
