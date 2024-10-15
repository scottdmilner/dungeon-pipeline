from __future__ import annotations

import logging
# import maya.cmds as mc

from datetime import datetime
from typing import TYPE_CHECKING

from pipe.util import Playblaster
from shared.util import get_edit_path

from .struct import (
    HudDefinition,
    MPlayblastConfig,
    MShotPlayblastConfig,
    SaveLocation,
)
from .ui import PlayblastDialog

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class AnimPlayblastDialog(PlayblastDialog):
    class SAVE_LOCS(PlayblastDialog.SAVE_LOCS):
        EDIT = SaveLocation(
            "Send to Edit",
            get_edit_path() / "anim" / datetime.now().strftime("%m-%d-%y"),
            Playblaster.PRESET.EDIT_SQ,
        )

    def __init__(self, parent):
        HudDefinition
        MPlayblastConfig
        MShotPlayblastConfig
        # code = str(mc.fileInfo("code", query=True)[0])
        # shot = self.playblaster._conn.get_shot_by_code(code)
        # shot_config = MShotPlayblastConfig(
        #     name=code,
        #     # camera
        # )
        super().__init__(parent, [], "LnD Anim Playblast")


# class MAnimPlayblaster(MPlayblaster):
#     _code: str

#     def __init__(self) -> None:
#         self._code = mc.fileInfo("code", query=True)[0]
#         super().__init__()

#     def playblast(self) -> None:
#         with _applied_hud(*self.HUDS), _unselect_all(), self(
#             self._conn.get_shot_by_code(self._code),
#             "|__mayaUsd__|shotCamParent|shotCam",
#         ):
#             super()._do_playblast(
#                 [
#                     get_edit_path()
#                     / "testing"
#                     / self._shot.code
#                     / (self._shot.code + "_V002.mov")
#                 ],
#                 tail=5,
#             )
