import logging as _l
from os import environ as _e

# import shared scripts
from pathlib import Path
import shared as _shared

__path__.append(str(Path(_shared.__file__).parent))

# import universal pipe functions that need localization
from .localizer import SubstancePainterLocalizer as _SPL

local = _SPL()

# import subtance painter-specific scripts
from . import channels
from . import export
from . import metadata

# configure logging
_log = _l.getLogger(__name__)
_l.basicConfig(
    level=int(_e.get("PIPE_LOG_LEVEL")),
    format="%(asctime)s %(processName)s(%(process)s) %(threadName)s [%(name)s(%(lineno)s)] [%(levelname)s] %(message)s",
)
