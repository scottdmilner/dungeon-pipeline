"""Baseclasses for interacting with DCCs"""

import logging
import os
import subprocess

from typing import Optional, Sequence

from .interface import DCCInterface

log = logging.getLogger(__name__)


class DCC(DCCInterface):
    command: str = None
    args: Optional[Sequence[str]] = None
    processes = []

    def __init__(
        self,
        command: str,
        args: Optional[Sequence[str]] = [],
    ) -> None:
        """Initialize DCC object.

        Keyword arguments:
        - command -- the command to launch the software
        - args    -- the arguments to pass to the command
        """

        self.command = command
        self.args = args

    def launch(
        self,
        command: Optional[str] = None,
        args: Optional[Sequence[str]] = None,
    ) -> None:
        """Launch the software with the specified arguments.

        Passing in optional parameters will override their default
        values.
        """

        if command is None:
            command = self.command
        if args is None:
            args = self.args

        log.info("Launching the software")
        self.processes.append(subprocess.Popen([command] + args))
