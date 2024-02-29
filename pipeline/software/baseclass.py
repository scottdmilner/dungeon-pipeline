"""Baseclasses for interacting with DCCs"""

import logging
import os
import subprocess

from typing import List, Mapping, Optional, Sequence, Union

from .interface import DCCInterface, DCCLocalizerInterface

log = logging.getLogger(__name__)


class DCC(DCCInterface):
    command: str
    args: Optional[List[str]]
    env_vars: Mapping[str, Optional[Union[int, str]]]

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = [],
        env_vars: Optional[Mapping[str, Optional[Union[int, str]]]] = None,
    ) -> None:
        """Initialize DCC object.

        Keyword arguments:
        - command -- the command to launch the software
        - args    -- the arguments to pass to the command
        """

        self.command = command
        self.args = args
        self.env_vars = env_vars or {}

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

    def launch(
        self,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
    ) -> None:
        """Launch the software with the specified arguments.

        Passing in optional parameters will override their default
        values.
        """

        if command is None:
            command = self.command
        if args is None:
            args = self.args

        self._set_env_vars()

        log.info("Launching the software")
        log.debug(f"Command: {command}, Args: {args}")
        subprocess.call([command] + (args or []))


class DCCLocalizer(DCCLocalizerInterface):
    id: str

    def __init__(self, id: str) -> None:
        self.id = id
