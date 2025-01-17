from __future__ import annotations

import logging
import os
import platform
import shutil

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing

from ..baseclass import DCC
from shared.util import get_production_path, get_rigging_path
from env import Executables

log = logging.getLogger(__name__)


class MayaDCC(DCC):
    """Maya DCC class"""

    shelf_path: str

    def __init__(
        self, is_python_shell: bool = False, extra_args: list[str] | None = None
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        self.shelf_path = str(
            Path(os.getenv("TMPDIR", os.getenv("TEMP", "tmp"))).resolve() / "shelves"
        )

        env_vars: typing.Mapping[str, int | str | None] | None
        env_vars = {
            "DCC": str(this_path.parent.name),
            "DWPICKER_PROJECT_DIRECTORY": str(get_rigging_path() / "Pickers"),
            "MAYA_SHELF_PATH": self.shelf_path,
            "MAYAUSD_EXPORT_MAP1_AS_PRIMARY_UV_SET": 1,
            "MAYAUSD_IMPORT_PRIMARY_UV_SET_AS_MAP1": 1,
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                    str(this_path.parent / "scripts"),
                    str(this_path.parent / "userSetup"),
                    str(this_path.parent / "scripts/studiolibrary/src"),
                ]
            ),
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "QT_FONT_DPI": os.getenv("MAYA_FONT_DPI") if system == "Linux" else None,
            "QT_PLUGIN_PATH": None,
            # Configure Asset Resolver
            "PXR_AR_DEFAULT_SEARCH_PATH": os.pathsep.join(
                [
                    str(get_production_path()),
                ]
            ),
            # USD Plugins
            "PXR_PLUGINPATH_NAME": os.pathsep.join(
                [
                    str(pipe_path / "lib/usd/kinds"),
                    os.environ.get("PXR_PLUGINPATH_NAME", ""),
                ]
            ),
            # Icons
            "XBMLANGPATH": os.pathsep.join(
                [
                    str(pth) + ("/%B" if system == "Linux" else "")
                    for pth in [
                        this_path.parent
                        / "scripts/studiolibrary/src/studiolibrary/resource/icons",
                        pipe_path / "lib/icon",
                        pipe_path / "lib/splash",
                    ]
                ]
            ),
        }

        launch_command = ""
        launch_args: list[str] = []
        if is_python_shell:
            launch_command = str(Executables.mayapy)
            cmd_str = ""
            extra_args_preamble = []

            print(extra_args)

            if extra_args:
                # extract the cmd arg so we can append it to everything else
                try:
                    cmd_flag_index = next(
                        (
                            i
                            for i, f in enumerate(extra_args)
                            if (f[0] == "-") and (f[-1] == "c")
                        )
                    )
                    cmd_str = extra_args[cmd_flag_index + 1]
                    if len(extra_args[cmd_flag_index]) > 2:
                        cmd_str_other_flags = ["-" + extra_args[cmd_flag_index][1:-1]]
                    else:
                        cmd_str_other_flags = []

                    extra_args_preamble = (
                        extra_args[:cmd_flag_index]
                        + extra_args[cmd_flag_index + 2 :]
                        + cmd_str_other_flags
                    )
                except StopIteration:
                    pass

            launch_args = extra_args_preamble + [
                "-ic",
                ";".join(
                    [
                        "import atexit",
                        "import maya.standalone",
                        "maya.standalone.initialize()",
                        "atexit.register(maya.standalone.uninitialize)",
                        cmd_str,
                    ]
                ),
            ]
        else:
            launch_command = str(Executables.maya)
            if extra_args:
                launch_args = extra_args

        super().__init__(
            launch_command, launch_args, env_vars, lambda: self.set_up_shelf_path()
        )

    def set_up_shelf_path(self) -> None:
        prod_dir = str(Path(__file__).parent / "shelves")
        local_dir = self.shelf_path

        shutil.copytree(prod_dir, local_dir, dirs_exist_ok=True)
