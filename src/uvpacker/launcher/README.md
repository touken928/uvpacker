## uvpacker launcher

This directory contains the native Windows launcher used by `uvpacker` to start
packed applications via small `console.exe` / `gui.exe` template shims instead of a `.cmd` script.

### How it works

- `launcher.c` is a tiny Windows program that:
  - Locates its own executable path.
  - Reads an embedded **zip** project archive and a **JSON** metadata block, followed by a 12-byte trailer:
    JSON UTF-8 length (`uint32` LE) + 8-byte magic `"UVPKLAUN"`. Semantic fields (`uvpacker`, `archive_size`, `module`, `func`, …) live only in the JSON.
  - Locates the embedded runtime under `runtime\` next to the launcher
    (`python3.dll`, etc.).
  - Loads `python3.dll`, resolves `Py_Main`, installs a small in-memory importer, and runs the configured entrypoint from the appended project archive.
- Two PE templates are built from the same source:
  - **`console.exe`** — console subsystem (for `[project.scripts]`).
  - **`gui.exe`** — Windows subsystem, no console window (for
    `[project.gui-scripts]`).
- The Python package (`uvpacker.launcher`) locates the bundled templates and
  appends per-script `zip | json | trailer` to produce `<script>.exe` in the packed
  output directory.

### Embedded payload: binary layout

After the PE template, bytes are appended in this order:

1. **Zip archive** — deflate zip of the target project’s importable tree (see `uvpacker.services.packer`).
2. **JSON metadata** — UTF-8, compact encoding (no extra whitespace). Length is not stored inside JSON; the trailer gives its byte length.
3. **Trailer (12 bytes)** — `struct.pack('<I8s', len(json_bytes), b'UVPKLAUN')`: little-endian `uint32` JSON length, then the 8-byte magic `UVPKLAUN`.

The launcher reads from EOF: magic → JSON length → JSON text → uses `archive_size` from JSON to read the zip bytes that precede the JSON.

### JSON metadata contents

The metadata is a single JSON object. `uvpacker.launcher` builds it in `_make_payload()`; fields below are what the runtime expects today.

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `uvpacker` | string | yes | **uvpacker** release version that produced this payload (from `uvpacker.__version__`, e.g. `0.5.1`). |
| `archive_size` | integer | yes | Byte length of the **zip** segment immediately **before** this JSON. Used to locate and read the embedded archive from the executable. Must match the actual zip size. |
| `module` | string | yes | Dotted import path of the entry module (e.g. `web_demo.main`). |
| `func` | string | yes | Callable name on that module (e.g. `main`). Default at build time is `main` if omitted in `pyproject.toml` script syntax. |

Example (pretty-printed for readability; on disk it is minified):

```json
{
  "uvpacker": "0.5.1",
  "archive_size": 12345,
  "module": "web_demo.main",
  "func": "main"
}
```

The bootstrap in `launcher.c` loads this object as `_meta`, then sets `_ENTRY_MODULE = _meta['module']`, `_ENTRY_FUNC = _meta.get('func', 'main')`, and reads `_archive_size = int(_meta['archive_size'])` bytes for the in-memory zip.

### Runtime model

- The target project's own pure-Python package is embedded into each launcher `.exe`.
- Third-party dependencies stay in `packages/` and are exposed through the embedded runtime's `._pth` / `.pth`.
- `importlib.resources` access for embedded project files is supported by the launcher's in-memory loader.
- Native binaries inside the project package itself (for example `.pyd`) are not supported by this in-memory embedding model.

### Building with mingw-w64 (Windows or cross-compile)

From `src/uvpacker/launcher`, reuse one flag set for both targets:

```bash
CC=x86_64-w64-mingw32-gcc
FLAGS="-municode -O2 -static -s"
$CC $FLAGS -o console.exe launcher.c
$CC $FLAGS -mwindows -DUVPK_GUI -o gui.exe launcher.c
```

**What you should not drop**

- `-municode` — wide entry (`wmain` / `wWinMain`).
- `-mwindows` and `-DUVPK_GUI` together for `gui.exe` only — selects Windows subsystem and the `wWinMain` path in `launcher.c`.
- `-static` — avoids shipping MinGW runtime DLLs next to the template (recommended for checked-in `console.exe` / `gui.exe`).

**What you can omit if you want a shorter command**

- `-O2` — default is `-O0` (faster compile; exe may be larger). Use `-Os` if you care about size instead of speed.
- `-s` — keep for release; drop if you need symbols in a debugger.

### Building on macOS (cross-compiling for Windows)

```bash
brew install mingw-w64
cd src/uvpacker/launcher
x86_64-w64-mingw32-gcc -municode -O2 -static -s -o console.exe launcher.c
x86_64-w64-mingw32-gcc -municode -O2 -static -s -mwindows -DUVPK_GUI -o gui.exe launcher.c
```

Check in both `console.exe` and `gui.exe` so they ship inside
the `uvpacker` wheel.
