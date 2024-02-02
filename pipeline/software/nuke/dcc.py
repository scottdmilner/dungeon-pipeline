import logging
import os
import platform

from pathlib import Path

from ..baseclass import DCC

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
            "PYTHONPATH": "",
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "QT_SCALE_FACTOR": os.getenv("NUKE_SCALE_FACTOR")
            if system == "Linux"
            else None,
        }

        launch_command = ""
        if system == "Linux":
            if is_python_shell:
                launch_command = "/opt/Nuke14.0v5/python3"
            else:
                launch_command = "/opt/Nuke14.0v5/Nuke14.0"
        elif system == "Windows":
            if is_python_shell:
                launch_command = "C:\\Program Files\\Nuke14.0v5\\python.exe"
            else:
                launch_command = "C:\\Program Files\\Nuke14.0v5\\Nuke14.0.exe"
        else:
            raise NotImplementedError(
                f"The operating system {system} is not a supported OS for this DCC software"
            )

        if is_python_shell:
            launch_args = []
        else:
            launch_args = ["--nukex"]

        super().__init__(launch_command, launch_args, env_vars)
