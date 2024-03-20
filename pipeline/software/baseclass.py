"""Baseclasses for interacting with DCCs"""

import logging
import os
import subprocess

from typing import Callable, List, Mapping, Optional, Sequence, Union

from .interface import DCCInterface, DCCLocalizerInterface
from shared.util import fix_launcher_metadata

log = logging.getLogger(__name__)


class DCC(DCCInterface):
    command: str
    args: Optional[List[str]]
    env_vars: Mapping[str, Optional[Union[int, str]]]
    pre_launch_tasks: Callable[[], None]

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = [],
        env_vars: Optional[Mapping[str, Optional[Union[int, str]]]] = None,
        pre_launch_tasks: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize DCC object.

        Keyword arguments:
        - command -- the command to launch the software
        - args    -- the arguments to pass to the command
        """

        self.command = command
        self.args = args
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

    def pre_launch_tasks(self, *args, **kwargs) -> None:
        pass

    def launch(
        self,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
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
        subprocess.call([command] + (args or []))


class DCCLocalizer(DCCLocalizerInterface):
    id: str

    def __init__(self, id: str) -> None:
        self.id = id
