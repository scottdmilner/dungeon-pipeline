# import shared scripts
from shared.util import get_pipe_path as _gpp

__path__.append(str(_gpp() / "shared"))

# import universal pipe functions that need localization
from .localizer import MayaLocalizer as _ML

local = _ML()

# import maya-specific scripts
from . import asset
