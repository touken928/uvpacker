<h1 align="center">uvpacker</h1>

<p align="center">
  <strong>Windows-oriented CLI packer for Python projects using <code>uv</code> and the CPython Embedded Runtime; run it on Linux, macOS, or Windows to produce a self-contained <code>win_amd64</code> app directory (not a single-file exe).</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge&logo=python" alt="Python 3.12+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL%20v3-blue.svg?style=for-the-badge" alt="License: GPL v3"></a>
  <a href="https://pypi.org/project/uvpacker/"><img src="https://img.shields.io/pypi/v/uvpacker.svg?style=for-the-badge&logo=pypi&logoColor=white&label=pypi" alt="PyPI version"></a>
  <a href="https://github.com/touken928/uvpacker/stargazers"><img src="https://img.shields.io/github/stars/touken928/uvpacker?style=for-the-badge&color=yellow&logo=github" alt="GitHub stars"></a>
</p>

---

## Overview

`uvpacker` builds a directory you can zip or copy as-is. It contains:

- the official **CPython Embedded Runtime** for Windows (64-bit)
- your project and dependencies installed for **`win_amd64`**
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
  packages/         # Your wheel + dependencies (win_amd64)
  <script>.exe      # Console vs GUI template from scripts / gui-scripts
```

Launchers use `runtime\python.exe` and patch the embedded `._pth` / `.pth` file so **`..\packages`** is on `sys.path` — no dependency on a global Python install.

## Installation & usage

Recommended: **`uvx`** so `uv` is available automatically.

```bash
# Pack a project (default output: ./dist/<project-name>)
uvx uvpacker path/to/project

# Explicit output directory
uvx uvpacker path/to/project -o path/to/output

# Pin version
uvx uvpacker==0.2.1 path/to/project
```

> **Note:** Tested with **`uv` 0.11.x**. Newer `uv` releases may change CLI behavior; report or pin versions if something breaks.

## Packing pipeline

1. Read and validate `pyproject.toml` (`scripts`, `gui-scripts`, `build-system`, `requires-python`)
2. Resolve Python version and download `python-<version>-embed-amd64.zip`
3. Build a wheel for the target project
4. `uv pip install` into `packages/` with **`--python-platform x86_64-pc-windows-msvc`**
5. Patch embedded runtime `_pth` to include `..\packages`
6. For **your** package tree: compile `.py` → `.pyc` with the target minor via `uv run`, then remove `.py` (light obfuscation; not encryption)
7. Generate **`.exe`** launchers (`console.exe` / `gui.exe` templates, or skip if missing)

## Cross-platform builds

Dependency resolution targets **`win_amd64`**, so you can pack from a non-Windows host when:

- the project is **pure Python**, or
- any native extensions are already buildable as **Windows** wheels

`uvpacker` does **not** cross-compile your own C extensions; use Windows for those projects.

## Examples

| Path | What it shows |
|------|----------------|
| `example/web-demo` | FastAPI + `importlib.resources` for static assets |
| `example/qt-demo` | PySide6 GUI via generated launcher |

## Roadmap (ideas)

- Hide or trim `packages/bin` shims that should not be end-user facing
- Stronger wheel checks and download **caching**
- Clearer errors and **verbose** diagnostics

## License

GNU General Public License v3.0 — see [`LICENSE`](LICENSE).
