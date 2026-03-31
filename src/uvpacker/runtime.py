from __future__ import annotations

import pathlib
import re
import tempfile
import urllib.request

from .errors import UvPackError


def require_exact_minor_from_requires(requires_python: str | None) -> str:
    """Extract the X.Y minor version from a '==X.Y.*' requires-python spec."""
    if requires_python is None:
        raise UvPackError(
            "`project.requires-python` must be set and use the '==X.Y.*' format.",
        )

    m = re.fullmatch(r"==(\d+\.\d+)\.\*", requires_python.strip())
    if not m:
        raise UvPackError(
            "uvpack requires `project.requires-python` to be an exact minor "
            "constraint of the form '==X.Y.*', for example '==3.11.*'.",
        )
    return m.group(1)


def resolve_latest_embed_for_minor(minor: str) -> str:
    """
    Resolve the latest CPython patch version that provides a Windows 64-bit
    embedded runtime for a given X.Y minor.
    """
    index_url = "https://www.python.org/ftp/python/"
    try:
        with urllib.request.urlopen(index_url) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise UvPackError(
            f"Failed to query python.org for available versions: {exc}",
        ) from exc

    candidates: list[tuple[int, int, int]] = []
    for match in re.finditer(r"(\d+)\.(\d+)\.(\d+)/", html):
        major, minor_part, patch = (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
        if f"{major}.{minor_part}" == minor:
            candidates.append((major, minor_part, patch))

    if not candidates:
        raise UvPackError(
            f"No patch releases found on python.org for minor version {minor!r}.",
        )

    for major, minor_part, patch in sorted(
        candidates,
        key=lambda t: t[2],
        reverse=True,
    ):
        version = f"{major}.{minor_part}.{patch}"
        url = (
            f"https://www.python.org/ftp/python/"
            f"{version}/python-{version}-embed-amd64.zip"
        )
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req):  # noqa: S310
                return version
        except Exception:
            continue

    raise UvPackError(
        f"Could not find a Windows 64-bit embedded runtime for minor {minor!r} "
        "on python.org.",
    )


def download_and_extract_embedded_runtime(
    python_version: str,
    dest_dir: pathlib.Path,
) -> None:
    """
    Download and unpack the official CPython embedded runtime for Windows.
    """
    major_minor_patch = python_version
    url = (
        f"https://www.python.org/ftp/python/"
        f"{major_minor_patch}/python-{major_minor_patch}-embed-amd64.zip"
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        zip_path = tmp_path / "python-embed.zip"

        try:
            with urllib.request.urlopen(url) as resp, zip_path.open("wb") as f:
                import shutil

                shutil.copyfileobj(resp, f)
        except Exception as exc:  # noqa: BLE001
            raise UvPackError(
                f"Failed to download embedded runtime from {url!r}: {exc}",
            ) from exc

        import shutil

        shutil.unpack_archive(str(zip_path), str(dest_dir))

