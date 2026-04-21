<h1 align="center">uvpacker</h1>

<p align="center">
  <strong>面向 Windows 的 Python 项目命令行打包工具，基于 <code>uv</code> 与 CPython 嵌入式运行时；可在 Linux、macOS 或 Windows 上运行，产出自包含的 <code>win_amd64</code> 应用目录（非单文件 exe 形态）。</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg?style=for-the-badge&logo=python" alt="Python 3.12+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL%20v3-blue.svg?style=for-the-badge" alt="License: GPL v3"></a>
  <a href="https://pypi.org/project/uvpacker/"><img src="https://img.shields.io/pypi/v/uvpacker.svg?style=for-the-badge&logo=pypi&logoColor=white&label=pypi" alt="PyPI version"></a>
  <a href="https://github.com/touken928/uvpacker/stargazers"><img src="https://img.shields.io/github/stars/touken928/uvpacker?style=for-the-badge&color=yellow&logo=github" alt="GitHub stars"></a>
</p>

<p align="center"><a href="README.md">English</a></p>

---

## 概述

`uvpacker` 会生成一个可直接压缩或拷贝分发的目录，其中包含：

- 官方 **Windows 64 位 CPython 嵌入式运行时**
- 已为 **`win_amd64`** 安装的**第三方依赖**
- 直接嵌入到每个启动器 `.exe` 中的**项目自身包**
- 由 **`[project.scripts]`**（控制台）与 **`[project.gui-scripts]`**（无控制台窗口）生成的启动器，在提供模板时为 `.exe`

目标是在**未安装系统 Python** 的机器上运行，同时保持构建 **声明式**（标准 `pyproject.toml`）且 **可预期**。

**仓库：** [touken928/uvpacker](https://github.com/touken928/uvpacker)

## 对目标项目的要求

被打包项目需具备：

| 要求 | 说明 |
|------|------|
| `pyproject.toml` | 常规布局 |
| `[project.scripts]` 和/或 `[project.gui-scripts]` | 至少一条入口；两个表中的名称不得重复 |
| `[build-system]` | 用于复现构建环境 |
| `project.requires-python` | 必须为 `==X.Y.*`（例如 `==3.11.*`、`==3.12.*`） |

`uvpacker` 会从 [python.org](https://www.python.org/downloads/) 选取该次版本提供 **`embed-amd64`** 的**最新补丁版**。

## 输出目录结构

默认路径：`dist/<项目名>/`

```text
dist/<项目名>/
  runtime/          # Windows 嵌入式 CPython
  packages/         # 仅第三方依赖（win_amd64）
  <脚本名>.exe      # 来自 scripts / gui-scripts 的控制台或 GUI 模板
```

启动器会加载 `runtime\python3.dll`，修改嵌入式运行时中的 `._pth` / `.pth` 使 **`..\packages`** 在 `sys.path` 中，并从 `.exe` 尾部附加的归档中导入你的项目包，不依赖全局 Python。

## 安装与用法

推荐使用 `uvx` 运行。

```bash
# 构建打包（默认输出：./dist/<项目名>）
uvx uvpacker build path/to/project

# 指定输出目录
uvx uvpacker build path/to/project -o path/to/output

# 缓存管理
uvx uvpacker cache clear
```

`uvpacker cache clear` 仅清理嵌入式 Python runtime 缓存（`~/.cache/uvpacker/embed` 或 `$XDG_CACHE_HOME/uvpacker/embed`）；依赖包相关缓存由 `uv` 管理。

> **说明：** 已在 **`uv` 0.11.x** 下测试；新版本 `uv` 若变更 CLI，请反馈或固定版本。

## 示例

| 路径 | 说明 |
|------|------|
| `example/web-demo` | FastAPI + `importlib.resources` 静态资源 |
| `example/qt-demo` | PySide6 桌面 GUI，经 GUI 启动器运行 |
| `example/cli-demo` | 基于 `argparse` 的简单命令行示例，目标 **Python 3.14**（`hello` / `version` / `cwd` 子命令） |

## 跨平台打包

依赖解析目标为 **`win_amd64`**，因此在非 Windows 上打包时：

- 项目为 **纯 Python**，或
- 原生扩展已能产出 **Windows** 可用的 wheel

`uvpacker` **不会**为你交叉编译自带 C 扩展；此类项目请在 Windows 上打包。

如果**项目自身包**包含 `.pyd` / `.dll` 这类原生二进制，当前的纯内存嵌入模式不支持，构建会直接失败。第三方原生依赖仍可保留在 `packages/` 中。

## 打包流程

1. 读取并校验 `pyproject.toml`（`scripts`、`gui-scripts`、`build-system`、`requires-python`）
2. 解析 Python 版本并获取 `python-<版本>-embed-amd64.zip`（首次下载后缓存于 `~/.cache/uvpacker/embed`，若设置了 `XDG_CACHE_HOME` 则为 `$XDG_CACHE_HOME/uvpacker/embed`）
3. 为目标项目构建 wheel
4. 使用 **`--python-platform x86_64-pc-windows-msvc`** 执行 `uv pip install` 到 `packages/`
5. 删除 `packages/bin` / `packages/Scripts` 中宿主平台风格的脚本 shim
6. 修改嵌入式运行时 `_pth`，加入 `..\packages`
7. 对**你的**项目包：用目标次版本号通过 `uv run` 将 `.py` 编译为 `.pyc`，再删除 `.py`（轻度混淆，非加密）
8. 将项目包打成内存 zip 归档并附加到每个启动器 `.exe` 尾部，同时从 `packages/` 中移除重复的项目包与项目自身 `.dist-info`
9. 生成 **`.exe`** 启动器（`console.exe` / `gui.exe` 模板；若缺失则跳过）

## 资源嵌入

运行时遵循 **wheel 的安装布局**：第三方依赖在 `packages/`，**你的**项目从 `.exe` 内嵌归档导入，通常**没有**开发时的 `src/...` 目录树。

凡是用 [`importlib.resources.files`](https://docs.python.org/3/library/importlib.resources.html#importlib.resources.files) 读的资源都要打进 wheel，并放在**可导入的子包路径**下（例如 `files("myproject.static")` 对应 wheel 里的 `myproject/static/`）。第一个参数用**带点号的真实包名**；不要用相对 exe 的路径、裸名猜磁盘位置，或 `Path(__file__).parent / ...`。

`files()` 常返回 **`Traversable`** 而非完整 `pathlib.Path`（嵌入场景尤甚）：不要用 `path / "x"`、不要用多参数 `joinpath`，应写成 `root.joinpath("a").joinpath("b")` 这类单参数链式。

## 说明

- 项目自身包从每个启动器 `.exe` 内部导入，不再从 `packages/` 读取。
- `packages/` 仅保留运行时所需的第三方依赖。
- 项目自身 `.dist-info` 元数据会在嵌入后从 `packages/` 清除。
- 项目内资源请用 `importlib.resources`，写法见上文 **资源嵌入**。

## 许可

GNU General Public License v3.0 — 见 [`LICENSE`](LICENSE)。
