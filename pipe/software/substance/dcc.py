import logging
import os
import platform

from pathlib import Path
from typing import Mapping, Optional, Sequence, Union

from ..baseclass import DCC

log = logging.getLogger(__name__)


class SubstanceDCC(DCC):
    """Substance Painter DCC class"""

    this_path = Path(__file__).resolve()
    pipe_path = this_path.parents[2]

    system = platform.system()

    substance_env_vars = {
        "PYTHONPATH": "",
        "OCIO": str(pipe_path / "lib/ocio/HEAD/config.ocio"),
        "QT_PLUGIN_PATH": None,
        "SUBSTANCE_PAINTER_PLUGINS_PATH": str(this_path.parent / "plugins"),
    }

    substance_launch_command = ""
    if system == "Windows":
        substance_launch_command = "C:\\Program Files\\Adobe\\Adobe Substance 3D Painter\\Adobe Substance 3D Painter.exe"
    else:
        raise NotImplementedError(
            f"The operating system {system} is not a supported OS"
        )

    substance_launch_args = []

    def __init__(
        self,
        command: str = substance_launch_command,
        args: Optional[Sequence[str]] = substance_launch_args,
        env_vars: Mapping[str, Optional[Union[int, str]]] = substance_env_vars,
    ) -> None:
        super().__init__(command, args, env_vars)
