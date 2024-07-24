from __future__ import annotations

import logging
import os
import platform

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing

from shared.util import get_production_path, resolve_mapped_path

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

        env_vars: typing.Mapping[str, int | str | None] | None
        env_vars = {
            "DCC": str(this_path.parent.name),
            # Asset Gallery sqlite db
            "HOUDINI_ASSETGALLERY_DB_FILE": str(
                resolve_mapped_path(get_production_path() / "asset/assetGallery.db")
            ),
            # Backup directory
            "HOUDINI_BACKUP_DIR": "./.backup",
            # Dump the core on crash to help debugging
            "HOUDINI_COREDUMP": 1,
            # Compiled Houdini files debug
            "HOUDINI_DSO_ERROR": 2 if log.isEnabledFor(logging.DEBUG) else None,
            # Max backup files
            "HOUDINI_MAX_BACKUP_FILES": 20,
            # Prevent user envs from overriding existing values
            "HOUDINI_NO_ENV_FILE_OVERRIDES": 1,
            # Disable start page splash
            "HOUDINI_NO_START_PAGE_SPLASH": 1,
            # Configure additional HDA locations outside of the pipeline
            "HOUDINI_OTLSCAN_PATH": os.pathsep.join(
                [
                    str(p)
                    for p in resolve_mapped_path(
                        get_production_path() / "hda"
                    ).iterdir()
                ]
                + ["&"]
            ),
            # Package loading debug logging
            "HOUDINI_PACKAGE_VERBOSE": 1 if log.isEnabledFor(logging.DEBUG) else None,
            # Houdini Path
            "HOUDINI_PATH": os.pathsep.join(
                [
                    str(pipe_path / "lib/usd/kinds"),
                    "&",
                ]
            ),
            # Splash file
            "HOUDINI_SPLASH_FILE": str(pipe_path / "lib/splash/dunginisplash19.5.png"),
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
            # USD Plugins
            "PXR_PLUGINPATH_NAME": os.pathsep.join(
                [
                    str(pipe_path / "lib/usd/kinds"),
                    os.environ.get("PXR_PLUGINPATH_NAME", ""),
                ]
            ),
            # Add pipe modules to Pyton path
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                    # Add $RMANTREE/bin to PYTHONPATH for the Tractor PDG scheduler
                    os.environ.get("RMANTREE", "") + "/bin",
                ]
            ),
            # RenderMan color config json file
            "RMAN_COLOR_CONFIG_DIR": str(pipe_path / "lib/ocio/love-v01"),
            # Explicitly set Tractor location
            "TRACTOR_ENGINE": "tractor-engine.cs.byu.edu:443",
        }

        launch_command = ""
        if is_python_shell:
            launch_command = str(Executables.hython)
        else:
            launch_command = str(Executables.houdini)

        launch_args: list[str] = [] if is_python_shell else ["-foreground"]

        super().__init__(launch_command, launch_args, env_vars)
