## uvpacker launcher

This directory contains the native Windows launcher used by `uvpacker` to start
packed applications via a small `launcher.exe` shim instead of a `.cmd` script.

### How it works

- `launcher.exe` is a very small Windows console application that:
  - Locates its own executable path.
  - Reads a JSON payload that has been appended to the end of the EXE, followed
    by a fixed 16‑byte footer (`"UVPKLAUN"`, payload size, reserved).
  - Extracts the target `module` and `func` from the JSON payload.
  - Locates the embedded runtime in `runtime\python.exe` / `python3.dll`
    relative to the launcher.
  - Loads `python3.dll`, resolves `Py_Main`, and executes:
    `from <module> import <func> as _f; raise SystemExit(_f())`.
- The Python package side (`uvpacker.launcher.__init__`) is responsible for:
  - Locating or building a generic `launcher.exe` template.
  - Appending the per‑script JSON payload and footer to produce `<script>.exe`
    launchers in the packed output directory.

### Building on Windows (MSVC or mingw-w64)

On a Windows machine, you can build `launcher.exe` directly from `launcher.c`.
For example, with mingw-w64:

```bash
cd src/uvpacker/launcher
x86_64-w64-mingw32-gcc -municode -O2 -static -s -o launcher.exe launcher.c
```

Notes:

- `-municode` tells the CRT to use `wmain` as the entry point.
- `-static -s` produces a small, mostly self‑contained EXE suitable for
  distribution as a generic template.

### Building on macOS (cross‑compiling for Windows)

On macOS you can cross‑compile the same Windows launcher using Homebrew's
mingw-w64 toolchain:

```bash
brew install mingw-w64

cd src/uvpacker/launcher
x86_64-w64-mingw32-gcc -municode -O2 -static -s -o launcher.exe launcher.c
```

This produces a `win_amd64` `launcher.exe` binary that can be checked into the
repository and bundled into the `uvpacker` wheel. At runtime, `uvpacker` copies
this template and appends per‑script configuration to create the final
launchers.

