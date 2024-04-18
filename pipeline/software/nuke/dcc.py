import logging
import os
import platform

from pathlib import Path

from pipe.util import resolve_mapped_path

from ..baseclass import DCC
from env import Executables

log = logging.getLogger(__name__)


class NukeDCC(DCC):
    """Nuke DCC class"""

    def __init__(
        self,
        is_python_shell: bool = False,
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        env_vars = {
            "NUKE_PATH": str(resolve_mapped_path(this_path.parent / "tools")),
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                ]
            ),
            "QT_SCALE_FACTOR": os.getenv("NUKE_SCALE_FACTOR")
            if system == "Linux"
            else None,
        }

        launch_command = ""
        if is_python_shell:
            launch_command = str(Executables.nuke_python)
        else:
            launch_command = str(Executables.nuke)

        if is_python_shell:
            launch_args = []
        else:
            launch_args = ["--nukex"]

        super().__init__(launch_command, launch_args, env_vars)
