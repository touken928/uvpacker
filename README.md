## uvpacker

`uvpacker` is a Windows-oriented CLI packer for Python projects that you can run on Linux, macOS, or Windows hosts, while always producing Windows (`win_amd64`) application directories.  
Instead of producing a single-file executable, it builds a self-contained directory that can be copied, zipped, and distributed as-is. The directory contains:

- the official CPython Embedded Runtime for Windows
- all project dependencies installed for the `win_amd64` target
- launch scripts generated from your `[project.scripts]`

The goal is to make a fully declared Python project runnable on machines without a system Python installation, while keeping the build process simple and predictable.

### Requirements for target projects

The target project must provide at least:

- `pyproject.toml`
- a `[project.scripts]` table
- a `[build-system]` table
- `project.requires-python = "==X.Y.*"`

`requires-python` must pin a specific minor version, for example:

- `==3.11.*`
- `==3.12.*`

`uvpacker` will look up the latest patch release of that minor version that has an `embed-amd64` build on `python.org` and use it as the embedded runtime.

### Output layout

By default, `uvpacker` writes to `dist/<project-name>`, with a structure similar to:

```text
dist/<project-name>/
  runtime/
  packages/
  <script>.cmd
```

- `runtime/`: the official 64‑bit Windows Embedded Runtime
- `packages/`: the built wheel of your project and all dependencies
- `<script>.cmd`: launchers generated from `[project.scripts]`

The launchers invoke `runtime\python.exe` and adjust the embedded runtime’s `_pth` file to include `..\packages`, so the packed app does not depend on any system Python.

### Installation and usage (via `uvx`)

`uvpacker` is published on PyPI and is intended to be invoked through `uvx` so that users automatically get a working `uv` environment.

To run `uvpacker` without a global installation:

```bash
uvx uvpacker path/to/project
```

To specify an explicit output directory:

```bash
uvx uvpacker path/to/project -o path/to/output
```

You can also pin the `uvpacker` version:

```bash
uvx uvpacker==0.2.0 path/to/project
```

> **Note:** The current implementation has been tested with `uv` **0.11.x**.  
> Future `uv` releases may introduce breaking changes to the CLI or build behavior that could cause `uvpacker` to stop working until it is updated.

### Packing pipeline

The current build pipeline in `uvpacker` is:

1. Read the target project’s `pyproject.toml`
2. Validate `[project.scripts]`, `[build-system]`, and `requires-python`
3. Resolve the target Python version and download `python-<version>-embed-amd64.zip`
4. Build a wheel for the target project
5. Use `uv pip install` with the `win_amd64` target platform to install the wheel and its dependencies into `packages/`
6. Patch the embedded runtime’s `_pth` file to include `..\packages`
7. Generate `.cmd` launchers in the root of the output directory

### Cross-platform builds

Because dependency resolution is performed for the `win_amd64` target, you can build Windows distributions from non-Windows hosts, with one caveat:

- if the target project is **pure Python**, cross-platform packing is usually fine
- if the target project includes native extensions, the project’s own wheel must still be buildable for Windows; otherwise you should build on Windows

In other words, `uvpacker` fixes how third-party dependencies are resolved for Windows, but it does **not** try to solve cross-compiling your own native extensions.

### Example projects

This repository currently includes two example projects:

- `example/web-demo`: a minimal FastAPI web application
- `example/qt-demo`: a minimal PySide6 desktop application

The web demo uses `importlib.resources` to load HTML/CSS/JS from the package to verify that:

- packaged static assets are correctly included in the wheel
- resource loading is robust to directory layout changes
- the generated launcher can drive a complete application

The Qt demo verifies that:

- a GUI application can be packed and launched via a `.cmd` script
- GUI-related dependencies are correctly installed for `win_amd64`

### Current status and future work

The current implementation covers:

- automatic resolution and download of the Windows 64‑bit Embedded Runtime
- launcher generation in the root of the packed directory
- injecting `packages/` into the embedded runtime’s import path
- installing dependencies for the `win_amd64` target platform
- packing applications that use in-package resources

Planned and potential improvements include:

- generating real `.exe` launchers instead of `.cmd` files
- cleaning up helper entry points in `packages/bin` that should not be exposed
- stricter wheel compatibility checks and caching strategies
- more detailed error messages and build diagnostics

### License

This project is licensed under the GNU General Public License v3.0 (GPLv3).  
See the `LICENSE` file for details.