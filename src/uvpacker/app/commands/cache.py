from __future__ import annotations

import argparse

from ...infra.cache_store import clear_embed_cache
from ...view.ui import format_bytes, kv, success, warn


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("cache", help="Manage uvpacker cache.")
    cache_sub = parser.add_subparsers(dest="cache_command", required=True)

    clear = cache_sub.add_parser("clear", help="Clear embedded runtime cache.")
    clear.set_defaults(func=run_cache_clear_command)


def run_cache_clear_command(_: argparse.Namespace) -> int:
    result = clear_embed_cache()
    if not result.existed:
        warn(f"Cache directory does not exist: {result.path}")
        return 0

    success("Cache cleared.")
    kv("Files removed", result.files_removed)
    kv("Bytes freed", f"{result.bytes_freed} ({format_bytes(result.bytes_freed)})")
    kv("Cache path", result.path)
    return 0
