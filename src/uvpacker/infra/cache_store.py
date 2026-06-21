from __future__ import annotations

# Re-export public API for backward compatibility.
# Callers should migrate to infra.runtime_cache for direct access.
from .runtime_cache import CacheClearResult, clear_embed_cache, get_embed_cache_dir  # noqa: F401

__all__ = [
    "CacheClearResult",
    "clear_embed_cache",
    "get_embed_cache_dir",
]
