"""
Binary payload protocol shared with the C launcher (``launcher.c``).

The C runtime discovers module metadata and an embedded zip by seeking backward
from end-of-file.  The on-disk layout for every launcher ``.exe`` is::

    [template PE] [zip_bytes] [utf8_json] [12-byte trailer]

The 12-byte trailer is ``struct.pack('<I8s', json_len, MAGIC)``:
4-byte little-endian JSON byte-length followed by the 8-byte magic
``UVPKLAUN``.  The JSON metadata is always the field named ``module``
(the entry point dotted name) and may include ``func`` (default ``"main"``),
``archive_size``, and ``uvpacker`` (build tool version).
"""

from __future__ import annotations

import json
import struct
from typing import Any, Mapping

MAGIC = b"UVPKLAUN"
"""
Eight-byte magic that terminates every launcher trailer.

The C side compares this after reading ``_TAIL.unpack()``.
"""

TRAILER_STRUCT = struct.Struct("<I8s")
"""
``<I8s`` — little-endian uint32 JSON length followed by 8-byte magic.
"""


def _make_payload(config: Mapping[str, Any], archive: bytes = b"") -> bytes:
    """Encode the binary payload that is appended to a template ``.exe``.

    Parameters
    ----------
    config:
        Must include ``module`` (dotted entry-point module name) and may
        include ``func`` (default ``"main"``).  All keys are forwarded into
        the embedded JSON so the C runtime can read them.
    archive:
        Raw bytes of a zip archive containing the project's compiled modules.
        Pass ``b""`` when no project data should be embedded (payload-only
        launcher).

    Returns
    -------
    ``archive + utf8_json + trailer`` — exactly what the C side expects.
    """
    from .. import __version__ as uvpacker_version

    meta: dict[str, Any] = dict(config)
    meta["uvpacker"] = uvpacker_version
    meta["archive_size"] = len(archive)
    data = json.dumps(meta, separators=(",", ":")).encode("utf-8")
    trailer = TRAILER_STRUCT.pack(len(data), MAGIC)
    return archive + data + trailer
