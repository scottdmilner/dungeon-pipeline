from typing import Optional, Sequence
from ..baseclass import DCC


class HoudiniDCC(DCC):
    """Houdini DCC class"""

    def __init__(self) -> None:
        COMMAND = "/usr/bin/echo"
        ARGS = ["'hi'"]
        super().__init__(COMMAND, ARGS)
