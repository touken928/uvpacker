from __future__ import annotations

import argparse
import pathlib
import sys

from .core import pack_project
from .sources import PACK_DOWNLOAD_PRESETS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uvpack",
        description=(
            "Windows Python project packer based on uv and the "
            "Python Embedded Runtime."
        ),
    )

    parser.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="Path to the Python project (directory containing pyproject.toml).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output directory for the packed application (defaults to ./dist/<project-name>).",
    )
    parser.add_argument(
        "--tsinghua",
        action="store_true",
        help=(
            "Use Tsinghua mirrors for the embed zip index and for uv's default PyPI index "
            "(build + pip install)."
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.tsinghua:
        if "tsinghua" not in PACK_DOWNLOAD_PRESETS:
            parser.error("This build does not include Tsinghua download sources.")
        download = PACK_DOWNLOAD_PRESETS["tsinghua"]
    else:
        download = None

    project_dir = pathlib.Path(args.project_dir).resolve()
    output = pathlib.Path(args.output).resolve() if args.output else None

    try:
        pack_project(
            project_dir=project_dir,
            output_dir=output,
            download=download,
        )
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        parser.exit(1, f"uvpack: error: {exc}\n")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
