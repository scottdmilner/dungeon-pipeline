import logging
import os
import platform

from pathlib import Path
from typing import List, Mapping, Optional, Union

from ..baseclass import DCC
from shared.util import get_rigging_path
from env import Executables

log = logging.getLogger(__name__)


class MayaDCC(DCC):
    """Maya DCC class"""

    def __init__(self, is_python_shell: bool = False) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        env_vars: Optional[Mapping[str, Union[int, str, None]]]
        env_vars = {
            "DWPICKER_PROJECT_DIRECTORY": str(get_rigging_path() / "Pickers"),
            "MAYA_SHELF_PATH": str(this_path.parent / "shelves"),
            "MAYAUSD_EXPORT_MAP1_AS_PRIMARY_UV_SET": 1,
            "MAYAUSD_IMPORT_PRIMARY_UV_SET_AS_MAP1": 1,
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                    str(this_path.parent),
                    str(this_path.parent / "scripts"),
                ]
            ),
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "QT_FONT_DPI": os.getenv("MAYA_FONT_DPI") if system == "Linux" else None,
            "QT_PLUGIN_PATH": None,
        }

        launch_command = ""
        if is_python_shell:
            launch_command = str(Executables.mayapy)
        else:
            launch_command = str(Executables.maya)

        launch_args: List[str] = []

        super().__init__(launch_command, launch_args, env_vars)
