"""
Launcher-exe assembly — generating Windows ``.exe`` shims from C templates.

A consumer of the binary payload protocol (defined in ``uvpacker.launcher._payload``),
extracted from the archive module so that ``payload_archive`` stays focused on
zip building and package cleanup.
"""

from __future__ import annotations

import pathlib

from .. import launcher as exe_launcher
from ..domain.models import ScriptDefinition
from ..view.ui import info


def create_exe_launchers(
    scripts: list[ScriptDefinition],
    launchers_dir: pathlib.Path,
    archive: bytes,
) -> None:
    """
    Generate Windows ``.exe`` launchers backed by a small C shim.

    Console entries use a PE console template; ``[project.gui-scripts]`` entries
    use a Windows/GUI subsystem template (no console window).

    These launchers are optional: if the bundled ``console.exe`` / ``gui.exe``
    templates are missing from the package, the corresponding launchers are
    skipped.
    """
    for script in scripts:
        module, _, func = script.target.partition(":")
        if not module:
            continue
        created = exe_launcher.build_launcher_for_script(
            launchers_dir=launchers_dir,
            script_name=script.name,
            module=module,
            func=func or "main",
            gui=script.gui,
            archive=archive,
        )
        if created is None:
            kind = "GUI" if script.gui else "console"
            info(
                f"Failed to create executable launcher for script {script.name!r} "
                f"({kind} template missing).",
            )
