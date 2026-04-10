## uvpacker launcher

This directory contains the native Windows launcher used by `uvpacker` to start
packed applications via small `console.exe` / `gui.exe` template shims instead of a `.cmd` script.

### How it works

- `launcher.c` is a tiny Windows program that:
  - Locates its own executable path.
  - Reads an embedded project archive and JSON metadata appended to the end of the EXE, followed by a fixed
    20-byte footer (`"UVPKLAUN"`, metadata size, archive size, version).
  - Locates the embedded runtime under `runtime\` next to the launcher
    (`python3.dll`, etc.).
  - Loads `python3.dll`, resolves `Py_Main`, installs a small in-memory importer, and runs the configured entrypoint from the appended project archive.
- Two PE templates are built from the same source:
  - **`console.exe`** — console subsystem (for `[project.scripts]`).
  - **`gui.exe`** — Windows subsystem, no console window (for
    `[project.gui-scripts]`).
- The Python package (`uvpacker.launcher`) locates the bundled templates and
  appends per-script archive + JSON + footer to produce `<script>.exe` in the packed
  output directory.

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
