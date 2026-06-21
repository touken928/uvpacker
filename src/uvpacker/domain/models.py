from __future__ import annotations

import dataclasses
import pathlib
from typing import Any, Mapping


@dataclasses.dataclass(frozen=True)
class ScriptDefinition:
    name: str
    target: str
    # True when from [project.gui-scripts] (Windows subsystem, no console).
    gui: bool = False


@dataclasses.dataclass(frozen=True)
class ProjectConfig:
    root: pathlib.Path
    name: str
    requires_python: str | None
    scripts: list[ScriptDefinition]
    build_system: Mapping[str, Any]


@dataclasses.dataclass(frozen=True)
class PackLayout:
    root: pathlib.Path
    runtime: pathlib.Path
    packages: pathlib.Path
