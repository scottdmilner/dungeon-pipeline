import logging
import os
import platform

from pathlib import Path

from ..baseclass import DCC

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
            "PYTHONPATH": "",
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "QT_PLUGIN_PATH": None,
        }

        if is_python_shell:
            raise NotImplementedError("Python shell is not supported for this DCC")

        launch_command = ""
        if system == "Windows":
            launch_command = "C:\\Program Files\\Adobe\\Adobe Substance 3D Designer\\Adobe Substance 3D Designer.exe"
        else:
            raise NotImplementedError(
                f"The operating system {system} is not a supported OS for this DCC software"
            )

        launch_args = [
            "--config-file",
            str(this_path.parent / "lnd_configuration.sbscfg"),
        ]

        super().__init__(launch_command, launch_args, env_vars)
