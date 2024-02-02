import logging
import platform

from pathlib import Path

from shared.util import resolve_mapped_path

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
        hfs = ""
        if system == "Linux":
            hfs = Path("/opt/hfs19.5.640").resolve()
        elif system == "Windows":
            hfs = Path(
                "C:\\Program Files\\Side Effects Software\\Houdini 19.5.640"
            ).resolve()
        else:
            raise NotImplementedError(
                f"The operating system {system} is not a supported OS for this DCC software"
            )

        env_vars = {
            # Backup directory
            "HOUDINI_BACKUP_DIR": "./.backup",
            # Dump the core on crash to help debugging
            "HOUDINI_COREDUMP": 1,
            # Max backup files
            "HOUDINI_MAX_BACKUP_FILES": 20,
            # Prevent user envs from overriding existing values
            "HOUDINI_NO_ENV_FILE_OVERRIDES": 1,
            # Package loading debug logging
            "HOUDINI_PACKAGE_VERBOSE": 1 if log.isEnabledFor(logging.DEBUG) else None,
            # Project-specific preference overrides
            "HSITE": str(resolve_mapped_path(this_path.parent / "hsite")),
            # TODO: revert to project OCIO with R26
            # "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "PIPE_PATH": str(pipe_path),
            "PYTHONPATH": "",
            # "RMAN_COLOR_CONFIG_DIR": str(pipe_path / "lib/ocio/love-v01"),
        }

        launch_command = ""
        if is_python_shell:
            launch_command = str(hfs / "bin/hython")
        else:
            launch_command = str(hfs / "bin/houdinifx")

        if system == "Windows":
            launch_command += ".exe"

        launch_args = [] if is_python_shell else ["-foreground"]

        super().__init__(launch_command, launch_args, env_vars)
