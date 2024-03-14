# import shared scripts
from pathlib import Path
import shared as _shared

__path__.append(str(Path(_shared.__file__).parent))

# import universal pipe functions that need localization
from .localizer import MayaLocalizer as _ML

local = _ML()

# import maya-specific scripts
from . import asset, picker, rig_publish
