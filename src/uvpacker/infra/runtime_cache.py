from __future__ import annotations

import contextlib
import dataclasses
import os
import pathlib
import shutil
import tempfile
import time
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path

from ..domain.errors import CacheError, RuntimeResolveError
from ..domain.sources import DEFAULT_DOWNLOAD_CONFIG, PackDownloadConfig

# Timeout for the HTTP download of the embedded runtime zip (seconds).
_DOWNLOAD_TIMEOUT: float = 120.0

# A lock file older than this is considered stale and can be broken.
_LOCK_STALE_SECONDS: float = 15 * 60.0


# ---------------------------------------------------------------------------
# Cache path / metadata
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CacheClearResult:
    path: Path
    existed: bool
    files_removed: int
    bytes_freed: int


def get_embed_cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".cache"
    return base / "uvpacker" / "embed"


# ---------------------------------------------------------------------------
# Cache clearing (safe against active downloads)
# ---------------------------------------------------------------------------


def _is_temp_inprogress_name(name: str) -> bool:
    """Return True for file names that belong to an active download / lock."""
    return name.startswith("tmp_dl_") or name.startswith(".") or name.endswith(".lock")


def _is_active_cache_artifact(path: Path) -> bool:
    """Return True if *path* has a companion ``.lock`` file (active download)."""
    for suffix in (".zip", ".zip.part"):
        if not path.name.endswith(suffix):
            continue
        lock_path = path.with_name(path.name.removesuffix(suffix) + suffix + ".lock")
        if lock_path.is_file():
            return True
    return False


def clear_embed_cache() -> CacheClearResult:
    cache_dir = get_embed_cache_dir()
    if not cache_dir.exists():
        return CacheClearResult(
            path=cache_dir,
            existed=False,
            files_removed=0,
            bytes_freed=0,
        )

    files_removed = 0
    bytes_freed = 0
    errors: list[str] = []

    # Remove only finalized cache artefacts (*.zip, *.part leftovers);
    # skip temp / in-progress / lock files so concurrent downloads are not
    # disrupted.
    for p in cache_dir.rglob("*"):
        if not p.is_file() or _is_temp_inprogress_name(p.name):
            continue
        if _is_active_cache_artifact(p):
            continue
        try:
            bytes_freed += p.stat().st_size
            p.unlink()
            files_removed += 1
        except OSError as exc:
            errors.append(str(exc))

    # Remove empty sub-directories (but not the cache root itself).
    for p in reversed(list(cache_dir.rglob("*"))):
        if p.is_dir() and p != cache_dir:
            try:
                p.rmdir()
            except OSError:
                pass

    if errors:
        raise CacheError(
            f"Failed to clear some files in {cache_dir}: {'; '.join(errors)}",
        )

    return CacheClearResult(
        path=cache_dir,
        existed=True,
        files_removed=files_removed,
        bytes_freed=bytes_freed,
    )


# ---------------------------------------------------------------------------
# Locking (file-based, per-cache-zip)
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _cache_lock(lock_path: pathlib.Path) -> Iterator[None]:
    fd: int | None = None
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        _break_stale_lock(lock_path)
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise RuntimeResolveError(
                f"Embedded runtime cache is busy for {lock_path.stem!r}; try again shortly."
            )
    if fd is not None:
        os.write(fd, str(os.getpid()).encode("ascii", errors="ignore"))
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink()
        except OSError:
            pass


def _break_stale_lock(lock_path: pathlib.Path) -> None:
    try:
        age = time.time() - lock_path.stat().st_mtime
    except OSError:
        return
    if age <= _LOCK_STALE_SECONDS:
        return
    try:
        lock_path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Cache-zip validation
# ---------------------------------------------------------------------------


def _is_valid_cached_zip(path: pathlib.Path) -> bool:
    return path.is_file() and path.stat().st_size > 0 and zipfile.is_zipfile(path)


# ---------------------------------------------------------------------------
# Download + extract (coordinates network I/O with cache management)
# ---------------------------------------------------------------------------


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
    cache_lock = cache_dir / (cache_name + ".lock")
    cache_dir.mkdir(parents=True, exist_ok=True)

    with _cache_lock(cache_lock):
        if _is_valid_cached_zip(cache_zip):
            shutil.unpack_archive(str(cache_zip), str(dest_dir))
            return

        if cache_zip.is_file():
            try:
                cache_zip.unlink()
            except OSError:
                pass

        # Download to a unique temp file in the same directory so concurrent
        # processes do not share a single .part path. After a successful
        # download the file is atomically renamed into place.
        fd, tmp_path_str = tempfile.mkstemp(
            dir=str(cache_dir), prefix="tmp_dl_", suffix=".zip"
        )
        os.close(fd)
        tmp_path = pathlib.Path(tmp_path_str)

        try:
            try:
                with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT) as resp, tmp_path.open("wb") as f:
                    shutil.copyfileobj(resp, f)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeResolveError(
                    f"Failed to download embedded runtime from {url!r}: {exc}",
                ) from exc
            # Atomic publish (os.rename / Path.replace is atomic on POSIX;
            # on Windows it behaves as an atomic replacement for the same volume).
            tmp_path.replace(cache_zip)
        finally:
            if tmp_path.is_file():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        shutil.unpack_archive(str(cache_zip), str(dest_dir))
