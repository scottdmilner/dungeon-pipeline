import logging
import os
import platform

from pathlib import Path

from ..baseclass import DCC

log = logging.getLogger(__name__)


class MayaDCC(DCC):
    """Maya DCC class"""

    def __init__(self, is_python_shell: bool = False) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        env_vars = {
            "MAYA_SHELF_PATH": str(this_path.parent / "shelves"),
            "MAYAUSD_EXPORT_MAP1_AS_PRIMARY_UV_SET": 1,
            "MAYAUSD_IMPORT_PRIMARY_UV_SET_AS_MAP1": 1,
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                    str(this_path.parent),
                    str(this_path.parent / "scripts"),
                ]
            ),
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "QT_FONT_DPI": os.getenv("MAYA_FONT_DPI") if system == "Linux" else None,
            "QT_PLUGIN_PATH": None,
        }

        launch_command = ""
        if system == "Linux":
            if is_python_shell:
                launch_command = "/usr/autodesk/maya2024/bin/mayapy"
            else:
                launch_command = "/usr/local/bin/maya"
        elif system == "Windows":
            if is_python_shell:
                launch_command = (
                    "C:\\Program Files\\Autodesk\\Maya2024\\bin\\mayapy.exe"
                )
            else:
                launch_command = "C:\\Program Files\\Autodesk\\Maya2024\\bin\\maya.exe"
        else:
            raise NotImplementedError(
                f"The operating system {system} is not a supported OS for this DCC software"
            )

        launch_args = []

        super().__init__(launch_command, launch_args, env_vars)
