import logging
import os
import platform

from pathlib import Path
from typing import Mapping, Optional, Sequence, Union

from ..baseclass import DCC

log = logging.getLogger(__name__)


class MayaDCC(DCC):
    """Maya DCC class"""

    this_path = Path(__file__).resolve()
    pipe_path = this_path.parents[2]

    system = platform.system()

    maya_env_vars = {
        "MAYAUSD_EXPORT_MAP1_AS_PRIMARY_UV_SET": 1,
        "MAYAUSD_IMPORT_PRIMARY_UV_SET_AS_MAP1": 1,
        "PYTHONPATH": "",
        "OCIO": str(pipe_path / "lib/ocio/HEAD/config.ocio"),
        "QT_FONT_DPI": os.getenv("MAYA_FONT_DPI") if system == "Linux" else None,
        "QT_PLUGIN_PATH": None,
    }

    maya_launch_command = ""
    if system == "Linux":
        maya_launch_command = "/usr/local/bin/maya"
    elif system == "Windows":
        maya_launch_command = "C:\\Program Files\\Autodesk\\Maya2024\\bin\\maya.exe"
    else:
        raise NotImplementedError(
            f"The operating system {system} is not a supported OS for this DCC software"
        )

    maya_launch_args = []

    def __init__(
        self,
        command: str = maya_launch_command,
        args: Optional[Sequence[str]] = maya_launch_args,
        env_vars: Mapping[str, Optional[Union[int, str]]] = maya_env_vars,
    ) -> None:
        super().__init__(command, args, env_vars)
