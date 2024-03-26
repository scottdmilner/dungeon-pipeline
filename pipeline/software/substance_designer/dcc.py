import logging
import os
import platform

from pathlib import Path

from ..baseclass import DCC
from env import Executables

log = logging.getLogger(__name__)


class SubstanceDesignerDCC(DCC):
    """Substance Designer DCC class"""

    def __init__(
        self,
        is_python_shell: bool = False,
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        env_vars = {
            "DCC": str(this_path.parent.name),
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                ]
            ),
            "QT_PLUGIN_PATH": "",
        }

        if is_python_shell:
            raise NotImplementedError("Python shell is not supported for this DCC")

        launch_command = str(Executables.substance_designer)
        if not launch_command:
            raise NotImplementedError(
                f"The operating system {system} is not a supported OS for this DCC software"
            )

        launch_args = [
            "--config-file",
            str(this_path.parent / "lnd_configuration.sbscfg"),
        ]

        super().__init__(launch_command, launch_args, env_vars)
