import logging
import os
import platform

from pathlib import Path
from typing import List, Mapping, Optional, Union

from ..baseclass import DCC
from env import Executables

log = logging.getLogger(__name__)


class SubstancePainterDCC(DCC):
    """Substance Painter DCC class"""

    def __init__(
        self,
        is_python_shell: bool = False,
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        env_vars: Optional[Mapping[str, Union[int, str, None]]]
        env_vars = {
            "DCC": str(this_path.parent.name),
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "PIPE_LOG_LEVEL": log.getEffectiveLevel(),
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                ]
            ),
            "QT_PLUGIN_PATH": "",
            "SUBSTANCE_PAINTER_PLUGINS_PATH": str(this_path.parent / "plugins"),
        }

        if is_python_shell:
            raise NotImplementedError("Python shell is not supported for this DCC")

        launch_command = str(Executables.substance_painter)
        if not launch_command:
            raise NotImplementedError(
                f"The operating system {system} is not a supported OS for this DCC software"
            )

        launch_args: List[str] = []

        super().__init__(launch_command, launch_args, env_vars)
