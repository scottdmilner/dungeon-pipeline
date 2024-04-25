import logging
import os
import platform

from pathlib import Path
from typing import List, Mapping, Optional, Union

from pipe.util import get_production_path, resolve_mapped_path

from ..baseclass import DCC
from env import Executables

log = logging.getLogger(__name__)


class HoudiniDCC(DCC):
    """Houdini DCC class"""

    def __init__(
        self,
        is_python_shell: bool = False,
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        env_vars: Optional[Mapping[str, Union[int, str, None]]]
        env_vars = {
            "DCC": str(this_path.parent.name),
            # Backup directory
            "HOUDINI_BACKUP_DIR": "./.backup",
            # Splash file
            "HOUDINI_SPLASH_FILE": str(pipe_path / "software/houdini/dunginisplash19.5.png"),
            # Dump the core on crash to help debugging
            "HOUDINI_COREDUMP": 1,
            # Compiled Houdini files debug
            "HOUDINI_DSO_ERROR": 2 if log.isEnabledFor(logging.DEBUG) else None,
            # Max backup files
            "HOUDINI_MAX_BACKUP_FILES": 20,
            # Prevent user envs from overriding existing values
            "HOUDINI_NO_ENV_FILE_OVERRIDES": 1,
            # Package loading debug logging
            "HOUDINI_PACKAGE_VERBOSE": 1 if log.isEnabledFor(logging.DEBUG) else None,
            # Project-specific preference overrides
            "HSITE": str(resolve_mapped_path(this_path.parent / "hsite")),
            # Job directory
            "JOB": str(resolve_mapped_path(get_production_path())),
            # Manually set LD_LIBRARY_PATH to integrated Houdini libraries (for Axiom)
            "LD_LIBRARY_PATH": str(Executables.hfs / "dsolib")
            if platform.system() == "Linux"
            else None,
            # Set project OCIO config
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            # Pass log level defined on commandline
            "PIPE_LOG_LEVEL": log.getEffectiveLevel(),
            "PIPE_PATH": str(pipe_path),
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                ]
            ),
            # "RMAN_COLOR_CONFIG_DIR": str(pipe_path / "lib/ocio/love-v01"),
        }

        launch_command = ""
        if is_python_shell:
            launch_command = str(Executables.hython)
        else:
            launch_command = str(Executables.houdini)

        launch_args: List[str] = [] if is_python_shell else ["-foreground"]

        super().__init__(launch_command, launch_args, env_vars)
