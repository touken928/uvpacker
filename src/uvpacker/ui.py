from __future__ import annotations

import sys


def info(message: str) -> None:
    sys.stdout.write(f"[uvpack] {message}\n")
    sys.stdout.flush()

