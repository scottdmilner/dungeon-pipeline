import logging
import os
import platform

from pathlib import Path
from typing import Mapping, Optional, Sequence, Union

from ..baseclass import DCC

log = logging.getLogger(__name__)


class NukeDCC(DCC):
    """Nuke DCC class"""

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
        launch_command = "/opt/Nuke14.0v5/Nuke14.0"
    elif system == "Windows":
        launch_command = "C:\\Program Files\\Nuke14.0v5\\Nuke14.0.exe"
    else:
        raise NotImplementedError(
            f"The operating system {system} is not a supported OS for this DCC software"
        )

    launch_args = ["--nukex"]

    def __init__(
        self,
        command: str = launch_command,
        args: Optional[Sequence[str]] = launch_args,
        env_vars: Mapping[str, Optional[Union[int, str]]] = env_vars,
    ) -> None:
        super().__init__(command, args, env_vars)
