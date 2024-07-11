from __future__ import annotations

import logging
import os
import subprocess

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable, Mapping, Optional, Sequence, Union

from shared.util import fix_launcher_metadata, get_production_path

from .interface import DCCInterface, DCCLocalizerInterface

"""Baseclasses for interacting with DCCs"""

log = logging.getLogger(__name__)


class DCC(DCCInterface):
    command: str
    args: Optional[list[str]]
    env_vars: Mapping[str, Optional[Union[int, str]]]
    pre_launch_tasks: Callable[[], None]

    def __init__(
        self,
        command: str,
        args: Optional[Sequence[str]] = None,
        env_vars: Optional[Mapping[str, Optional[Union[int, str]]]] = None,
        pre_launch_tasks: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize DCC object.

        Keyword arguments:
        - command -- the command to launch the software
        - args    -- the arguments to pass to the command
        """

        if args is None:
            args = []

        self.command = command
        self.args = list(args) if args else None
        self.env_vars = env_vars or {}
        self.pre_launch_tasks = pre_launch_tasks or (lambda: None)

    def _set_env_vars(
        self, env_vars: Optional[Mapping[str, Optional[Union[int, str]]]] = None
    ) -> None:
        """(Un)Set environment variables to their associated values.

        All values will be converted to strings. If a value is None,
        that environment variable will be unset.
        """
        if env_vars is None:
            env_vars = self.env_vars

        log.info("(Un)setting environment vars")

        for key, val in env_vars.items():
            if val is None:
                if key in os.environ:
                    del os.environ[key]
            else:
                os.environ[key] = str(val)

        if not os.environ["PYTHONPATH"]:
            os.environ["PYTHONPATH"] = ""
        os.environ["PYTHONPATH"] = os.pathsep.join(
            [
                os.environ["PYTHONPATH"],
                str(get_production_path() / "../pipeline/pipeline/lib/python"),
            ]
        )
        print(os.environ["PYTHONPATH"])

    def launch(
        self,
        command: Optional[str] = None,
        args: Optional[Sequence[str]] = None,
        pre_launch_tasks: Optional[Callable[[], None]] = None,
    ) -> None:
        """Launch the software with the specified arguments.

        Passing in optional parameters will override their default
        values.
        """

        if command is None:
            command = self.command
        if args is None:
            args = self.args
        if pre_launch_tasks is None:
            pre_launch_tasks = self.pre_launch_tasks

        fix_launcher_metadata()
        pre_launch_tasks()
        self._set_env_vars()

        log.info("Launching the software")
        log.debug(f"Command: {command}, Args: {args}")
        subprocess.call([command] + list(args or []))


class DCCLocalizer(DCCLocalizerInterface):
    id: str

    def __init__(self, id: str) -> None:
        self.id = id
