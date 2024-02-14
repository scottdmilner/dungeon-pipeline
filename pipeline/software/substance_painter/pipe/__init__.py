# import shared scripts
from pathlib import Path
import shared as _shared

__path__.append(str(Path(_shared.__file__).parent))

# import universal pipe functions that need localization
from .localizer import SubstancePainterLocalizer as _SPL

local = _SPL()

# import subtance painter-specific scripts
from . import asset
from . import channels
from . import metadata
