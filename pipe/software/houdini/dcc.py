import logging
import platform

from pathlib import Path
from typing import Mapping, Optional, Sequence, Union

from ..baseclass import DCC

log = logging.getLogger(__name__)


class HoudiniDCC(DCC):
    """Houdini DCC class"""

    this_path = Path(__file__).resolve()
    pipe_path = this_path.parents[2]

    env_vars = {
        "HOUDINI_BACKUP_DIR": "./.backup",  # Backup directory
        "HOUDINI_COREDUMP": 1,  # Dump the core on crash to help debugging
        "HOUDINI_MAX_BACKUP_FILES": 20,  # Max backup files
        "HOUDINI_NO_ENV_FILE_OVERRIDES": 1,  # Prevent user envs from overriding existing values
        "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
        "PYTHONPATH": "",
        "RMAN_COLOR_CONFIG_DIR": str(pipe_path / "lib/ocio/love-v01"),
    }

    system = platform.system()

    launch_command = ""
    if system == "Linux":
        launch_command = "/opt/hfs19.5.640/bin/houdinifx"
    elif system == "Windows":
        launch_command = "C:\\Program Files\\Side Effects Software\\Houdini 19.5.640\\bin\\houdinifx.exe"
    else:
        raise NotImplementedError(
            f"The operating system {system} is not a supported OS for this DCC software"
        )

    launch_args = ["-foreground"]

    def __init__(
        self,
        command: str = launch_command,
        args: Optional[Sequence[str]] = launch_args,
        env_vars: Mapping[str, Optional[Union[int, str]]] = env_vars,
    ) -> None:
        super().__init__(command, args, env_vars)
