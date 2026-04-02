from __future__ import annotations

import sys
from collections.abc import Iterable


PREFIX = "[uvpacker]"


def _emit(message: str, *, level: str = "INFO", to_stderr: bool = False) -> None:
    stream = sys.stderr if to_stderr else sys.stdout
    stream.write(f"{PREFIX} {level}: {message}\n")
    stream.flush()


def info(message: str) -> None:
    _emit(message, level="INFO")


def warn(message: str) -> None:
    _emit(message, level="WARN")


def error(message: str) -> None:
    _emit(message, level="ERROR", to_stderr=True)


def success(message: str) -> None:
    _emit(message, level="OK")


def step(index: int, total: int, title: str) -> None:
    _emit(f"Step {index}/{total}: {title}", level="STEP")


def kv(key: str, value: object, *, level: str = "INFO") -> None:
    _emit(f"{key}: {value}", level=level)


def bullets(lines: Iterable[str], *, level: str = "INFO") -> None:
    for line in lines:
        _emit(f"- {line}", level=level)


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    units = ["KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        value /= 1024.0
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
    return f"{size} B"
