from __future__ import annotations

import logging

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from pipe.struct.db import Shot

import maya.cmds as mc

from pipe.glui.dialogs import MessageDialog
from pipe.struct.timeline import Timeline
from shared.util import get_production_path

from .publisher import Publisher
from .usdchaser import ChaserMode, ExportChaser

log = logging.getLogger(__name__)

CACHE_SET = "cache_SET"
PROP_SET = "prop_SET"


class AnimPublisher(Publisher):
    _shot: Shot
    _init_success: bool

    def __init__(self):
        super().__init__(use_sg_entity=False)
        try:
            shot_code = mc.fileInfo("code", query=True)[0]
            self._init_success = True
        except IndexError:
            mc.error("Could not find shot code in fileInfo! Cannot export shot.")
            error = MessageDialog(
                self._window,
                "Error: could not detect shot code. Please reach out to Scott",
            )
            error.exec_()
            self._init_success = False

        self._shot = self._conn.get_shot_by_code(shot_code)

    def _prepublish(self) -> bool:
        if not self._init_success:
            return False

        cache_sets = mc.ls("::" + CACHE_SET, sets=True)
        prop_sets = mc.ls("::" + PROP_SET, sets=True)

        mc.select(*cache_sets, *prop_sets, replace=True)

        return True

    def _get_save_path(self) -> Path | None:
        if not self._shot.path:
            return None
        return get_production_path() / self._shot.path / "anim/usd/main.usd"

    def _presave(self) -> bool:
        return True

    def _get_mayausd_kwargs(self) -> dict[str, Any]:
        timeline = Timeline.from_shot(self._shot, preroll_duration=55)
        return {
            "chaser": [ExportChaser.ID],
            "chaserArgs": [
                (ExportChaser.ID, "mode", ChaserMode.ANIM),
                (ExportChaser.ID, "timeline", timeline.to_json()),
            ],
            "exportColorSets": False,
            "exportComponentTags": False,
            "exportUVs": False,
            "frameRange": (
                timeline.preroll,
                timeline.end,
            ),
            "frameStride": 1.0,
            "shadingMode": "none",
            "stripNamespaces": False,
        }

    def _get_confirm_message(self):
        return f"Animation has been exported to {self._publish_path}"
