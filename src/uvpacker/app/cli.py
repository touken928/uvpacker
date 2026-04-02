from __future__ import annotations

import argparse
import sys

from .commands import build as build_command
from .commands import cache as cache_command


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uvpacker",
        description="Windows Python project packer based on uv and CPython Embedded Runtime.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_command.register(subparsers)
    cache_command.register(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        handler = getattr(args, "func", None)
        if handler is None:
            parser.error("No command selected.")
        return int(handler(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        parser.exit(1, f"uvpacker: error: {exc}\n")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
