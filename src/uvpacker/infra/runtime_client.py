from __future__ import annotations

# Re-export public API for backward compatibility.
# Callers should migrate to infra.runtime_downloader or infra.runtime_cache
# for direct access to internals.
from .runtime_cache import download_and_extract_embedded_runtime  # noqa: F401
from .runtime_downloader import resolve_latest_embed_for_minor  # noqa: F401

__all__ = [
    "download_and_extract_embedded_runtime",
    "resolve_latest_embed_for_minor",
]
