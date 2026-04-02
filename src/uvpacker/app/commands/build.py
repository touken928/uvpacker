from __future__ import annotations

import argparse
import pathlib

from ...services.packer import pack_project


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "build",
        help="Build a Windows app directory from a Python project.",
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
    parser.set_defaults(func=run_build_command)


def run_build_command(args: argparse.Namespace) -> int:
    project_dir = pathlib.Path(args.project_dir).resolve()
    output = pathlib.Path(args.output).resolve() if args.output else None
    pack_project(project_dir=project_dir, output_dir=output, download=None)
    return 0
