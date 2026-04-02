## uvpacker launcher

This directory contains the native Windows launcher used by `uvpacker` to start
packed applications via small `launcher_*.exe` shims instead of a `.cmd` script.

### How it works

- `launcher.c` is a tiny Windows program that:
  - Locates its own executable path.
  - Reads a JSON payload appended to the end of the EXE, followed by a fixed
    16-byte footer (`"UVPKLAUN"`, payload size, reserved).
  - Extracts the target `module` and `func` from the JSON payload.
  - Locates the embedded runtime under `runtime\` next to the launcher
    (`python3.dll`, etc.).
  - Loads `python3.dll`, resolves `Py_Main`, and runs:
    `from <module> import <func> as _f; raise SystemExit(_f())`.
- Two PE templates are built from the same source:
  - **`launcher_console.exe`** — console subsystem (for `[project.scripts]`).
  - **`launcher_gui.exe`** — Windows subsystem, no console window (for
    `[project.gui-scripts]`).
- The Python package (`uvpacker.launcher`) locates or cross-compiles these
  templates and appends per-script JSON + footer to produce `<script>.exe` in
  the packed output directory.

### Building on Windows (MSVC or mingw-w64)

From `src/uvpacker/launcher`:

**Console template**

```bash
x86_64-w64-mingw32-gcc -municode -O2 -static -s -o launcher_console.exe launcher.c
```

**GUI template (no console window)**

```bash
x86_64-w64-mingw32-gcc -municode -O2 -static -s -mwindows -DUVPACKER_GUI_SUBSYSTEM -o launcher_gui.exe launcher.c
```

Notes:

- `-municode` selects the wide-character entry (`wmain` / `wWinMain`).
- `-mwindows` + `-DUVPACKER_GUI_SUBSYSTEM` builds the GUI subsystem binary.
- `-static -s` keeps the templates small and mostly self-contained.

### Building on macOS (cross-compiling for Windows)

```bash
brew install mingw-w64
cd src/uvpacker/launcher
x86_64-w64-mingw32-gcc -municode -O2 -static -s -o launcher_console.exe launcher.c
x86_64-w64-mingw32-gcc -municode -O2 -static -s -mwindows -DUVPACKER_GUI_SUBSYSTEM -o launcher_gui.exe launcher.c
```

Check in both `launcher_console.exe` and `launcher_gui.exe` so they ship inside
the `uvpacker` wheel.
