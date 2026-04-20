from __future__ import annotations

import argparse
import os

from cli_demo import __version__


def cmd_hello(ns: argparse.Namespace) -> int:
    name = ns.name if ns.name is not None else "world"
    print(f"Hello, {name}!")
    return 0


def cmd_version(_ns: argparse.Namespace) -> int:
    print(f"cli-demo {__version__}")
    return 0


def cmd_cwd(_ns: argparse.Namespace) -> int:
    print(os.getcwd())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="cli-demo",
        description="Minimal console example for uvpacker.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    hello = sub.add_parser("hello", help="Print a greeting.")
    hello.add_argument(
        "--name",
        default=None,
        metavar="TEXT",
        help="Name to greet (default: world).",
    )
    hello.set_defaults(func=cmd_hello)

    ver = sub.add_parser("version", help="Print the demo version string.")
    ver.set_defaults(func=cmd_version)

    cwd = sub.add_parser(
        "cwd",
        help="Print the current working directory (os.getcwd()).",
    )
    cwd.set_defaults(func=cmd_cwd)

    ns = parser.parse_args()
    return ns.func(ns)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
