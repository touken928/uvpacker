<h1 align="center">uvpacker</h1>

<p align="center">
  <strong>Windows-oriented CLI packer for Python projects using <code>uv</code> and the CPython Embedded Runtime; run it on Linux, macOS, or Windows to produce a self-contained <code>win_amd64</code> app directory (not a single-file exe).</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge&logo=python" alt="Python 3.12+"></a>
  <a href="https://github.com/touken928/uvpacker/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/touken928/uvpacker/ci.yml?branch=main&amp;label=CI&amp;style=for-the-badge&amp;logo=github&amp;logoColor=white" alt="CI"></a>
  <a href="https://pypi.org/project/uvpacker/"><img src="https://img.shields.io/pypi/v/uvpacker.svg?style=for-the-badge&logo=pypi&logoColor=white&label=pypi" alt="PyPI version"></a>
  <a href="https://github.com/touken928/uvpacker/stargazers"><img src="https://img.shields.io/github/stars/touken928/uvpacker?style=for-the-badge&color=yellow&logo=github" alt="GitHub stars"></a>
</p>

<p align="center"><a href="README_zh.md">简体中文</a></p>

---

## Overview

`uvpacker` builds a directory you can zip or copy as-is. It contains:

- the official **CPython Embedded Runtime** for Windows (64-bit)
- your **third-party dependencies** installed for **`win_amd64`**
- your **project package embedded into each generated launcher `.exe`**
- launchers derived from **`[project.scripts]`** (console) and **`[project.gui-scripts]`** (no console window), as `.exe` when templates are available

The goal is to run on machines **without a system Python**, while keeping the build **declarative** (standard `pyproject.toml`) and **predictable**.

**Repository:** [touken928/uvpacker](https://github.com/touken928/uvpacker)

## Requirements (target projects)

The project you pack must have:

| Requirement | Notes |
|-------------|--------|
| `pyproject.toml` | Standard layout |
| `[project.scripts]` and/or `[project.gui-scripts]` | At least one entry; names must not overlap between the two tables |
| `[build-system]` | Used to reproduce the build environment |
| `project.requires-python` | Must be `==X.Y.*` (e.g. `==3.11.*`, `==3.12.*`) |

`uvpacker` picks the **latest patch** for that minor that has **`embed-amd64`** on [python.org](https://www.python.org/downloads/).

## Output layout

Default path: `dist/<project-name>/`

```text
dist/<project-name>/
  runtime/          # Windows embedded CPython
  packages/         # Third-party dependencies only (win_amd64)
  <script>.exe      # Console vs GUI template from scripts / gui-scripts
```

Launchers load `runtime\python3.dll`, patch the embedded `._pth` / `.pth` file so **`..\packages`** is on `sys.path`, and import your project package from an archive appended to the end of the `.exe` — no dependency on a global Python install.

## Installation & usage

Recommended: run with `uvx`.

```bash
# Build package output (default output: ./dist/<project-name>)
uvx uvpacker build path/to/project

# Explicit output directory
uvx uvpacker build path/to/project -o path/to/output

# Cache management
uvx uvpacker cache clear
```

`uvpacker cache clear` only removes embedded Python runtime cache (`~/.cache/uvpacker/embed` or `$XDG_CACHE_HOME/uvpacker/embed`); dependency-package cache is managed by `uv`.

> **Note:** Tested with **`uv` 0.11.x**. Newer `uv` releases may change CLI behavior; report or pin versions if something breaks.

## Packing pipeline

1. Read and validate `pyproject.toml` (`scripts`, `gui-scripts`, `build-system`, `requires-python`)
2. Resolve Python version and obtain `python-<version>-embed-amd64.zip` (downloaded once, then cached under `~/.cache/uvpacker/embed`, or `$XDG_CACHE_HOME/uvpacker/embed` if set)
3. Build a wheel for the target project
4. `uv pip install` into `packages/` with **`--python-platform x86_64-pc-windows-msvc`**
5. Remove host-style script shims from `packages/bin` / `packages/Scripts`
6. Patch embedded runtime `_pth` to include `..\packages`
7. For **your** package tree: compile `.py` → `.pyc` with the target minor via `uv run`, then remove `.py` (light obfuscation; not encryption)
8. Bundle your project package into an in-memory zip archive, append it to each generated launcher `.exe`, and remove the duplicated project package / project `.dist-info` from `packages/`
9. Generate **`.exe`** launchers (`console.exe` / `gui.exe` templates, or skip if missing)

## Cross-platform builds

Dependency resolution targets **`win_amd64`**, so you can pack from a non-Windows host when:

- the project is **pure Python**, or
- any native extensions are already buildable as **Windows** wheels

`uvpacker` does **not** cross-compile your own C extensions; use Windows for those projects.

If your **project package itself** contains native binaries such as `.pyd` / `.dll`, the current in-memory embedding mode is not supported and the build will fail. Third-party native dependencies can still remain in `packages/`.

## Examples

| Path | What it shows |
|------|----------------|
| `example/web-demo` | FastAPI + `importlib.resources` for static assets |
| `example/qt-demo` | PySide6 GUI via generated launcher |

## Notes

- Your project package is imported from inside each launcher `.exe`, not from `packages/`.
- `packages/` is reserved for third-party dependencies needed at runtime.
- The project's own `.dist-info` metadata is removed from `packages/` after embedding.
- Resource access via `importlib.resources` is supported for embedded project files.

## License

GNU General Public License v3.0 — see [`LICENSE`](LICENSE).
