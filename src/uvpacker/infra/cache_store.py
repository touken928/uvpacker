from __future__ import annotations

import dataclasses
import os
import shutil
from pathlib import Path

from ..domain.errors import CacheError


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
    for p in cache_dir.rglob("*"):
        if p.is_file():
            files_removed += 1
            try:
                bytes_freed += p.stat().st_size
            except OSError:
                pass

    try:
        shutil.rmtree(cache_dir)
    except OSError as exc:
        raise CacheError(f"Failed to clear cache directory {cache_dir}: {exc}") from exc
    return CacheClearResult(
        path=cache_dir,
        existed=True,
        files_removed=files_removed,
        bytes_freed=bytes_freed,
    )
