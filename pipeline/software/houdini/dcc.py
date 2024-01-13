import logging
import platform

from pathlib import Path

from ..baseclass import DCC

log = logging.getLogger(__name__)


class HoudiniDCC(DCC):
    """Houdini DCC class"""

    def __init__(
        self,
        is_python_shell: bool = False,
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        env_vars = {
            "HOUDINI_BACKUP_DIR": "./.backup",  # Backup directory
            "HOUDINI_COREDUMP": 1,  # Dump the core on crash to help debugging
            "HOUDINI_MAX_BACKUP_FILES": 20,  # Max backup files
            "HOUDINI_NO_ENV_FILE_OVERRIDES": 1,  # Prevent user envs from overriding existing values
            # TODO: revert to project OCIO with R26
            # "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "OCIO": str(Path("/opt/pixar" if system == "Linux" else "C:\\Program Files\\Pixar").resolve() / "RenderManProServer-25.2/lib/ocio/ACES-1.2/config.ocio"),
            "PYTHONPATH": "",
            # "RMAN_COLOR_CONFIG_DIR": str(pipe_path / "lib/ocio/love-v01"),
        }

        launch_command = ""
        if system == "Linux":
            if is_python_shell:
                launch_command = "/opt/hfs19.5.640/bin/hython"
            else:
                launch_command = "/opt/hfs19.5.640/bin/houdinifx"
        elif system == "Windows":
            if is_python_shell:
                launch_command = "C:\\Program Files\\Side Effects Software\\Houdini 19.5.640\\bin\\hython.exe"
            else:
                launch_command = "C:\\Program Files\\Side Effects Software\\Houdini 19.5.640\\bin\\houdinifx.exe"
        else:
            raise NotImplementedError(
                f"The operating system {system} is not a supported OS for this DCC software"
            )

        launch_args = [] if is_python_shell else ["-foreground"]

        super().__init__(launch_command, launch_args, env_vars)
