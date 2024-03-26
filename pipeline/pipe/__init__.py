import logging as _l
from os import environ as _e

from . import db
from . import glui
from . import struct
from . import texconverter
from . import util

__all__ = [
    "db",
    "glui",
    "struct",
    "texconverter",
    "util",
]

# import DCC-specific modules
from os import getenv as _getenv

_dcc = _getenv("DCC", "")

if _dcc == "houdini":
    from . import h

    __all__ += ["h"]

elif _dcc == "maya":
    from . import m

    __all__ += ["m"]

elif _dcc == "substance_painter":
    from . import sp

    __all__ += ["sp"]

# configure logging
_log = _l.getLogger(__name__)
_l.basicConfig(
    level=int(_e.get("PIPE_LOG_LEVEL") or 0),
    format="%(asctime)s %(processName)s(%(process)s) %(threadName)s [%(name)s(%(lineno)s)] [%(levelname)s] %(message)s",
)
