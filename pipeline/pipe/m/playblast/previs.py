from __future__ import annotations

import logging
import maya.cmds as mc
import os

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pipe.util import Playblaster
from shared.util import get_edit_path

from .struct import (
    HudDefinition,
    MPlayblastConfig,
    MShotPlayblastConfig,
    SaveLocation,
    dummy_shot,
)
from .ui import PlayblastDialog

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class PrevisPlayblastDialog(PlayblastDialog):
    _camera_shot_lookup: dict[str, str]

    class SAVE_LOCS(PlayblastDialog.SAVE_LOCS):
        EDIT = SaveLocation(
            "Send to Edit",
            get_edit_path() / "previs" / datetime.now().strftime("%m-%d-%y"),
            Playblaster.PRESET.EDIT_SQ,
        )

    def __init__(self, parent) -> None:
        shot_node_list: list[str] = mc.sequenceManager(listShots=True) or []  # type: ignore[assignment]

        # generate lookup table for matching cameras to shots
        self._camera_shot_lookup = {
            str(mc.shot(node, query=True, currentCamera=True)): str(
                mc.shot(node, query=True, shotName=True)
            )
            for node in shot_node_list
        }

        # generate playblast configs
        shots = [
            MShotPlayblastConfig(
                camera=mc.shot(shot_node, query=True, currentCamera=True),  # type: ignore[arg-type]
                shot=dummy_shot(
                    str(mc.shot(shot_node, query=True, shotName=True)),
                    int(mc.shot(shot_node, query=True, startTime=True)),
                    int(mc.shot(shot_node, query=True, endTime=True)),
                    int(mc.shot(shot_node, query=True, clipDuration=True)),
                ),
                save_locs=[
                    (self.SAVE_LOCS.EDIT, True),
                    (self.SAVE_LOCS.CURRENT, False),
                    (self.SAVE_LOCS.CUSTOM, False),
                ],
            )
            for shot_node in shot_node_list
        ]
        seq_node = str(mc.sequenceManager(query=True, writableSequencer=True))
        sequence = MShotPlayblastConfig(
            camera=None,
            shot=dummy_shot(
                code=Path(mc.file(query=True, sceneName=True)).stem,  # type: ignore[arg-type]
                cut_in=(ci := mc.getAttr(f"{seq_node}.minFrame")),
                cut_out=(co := mc.getAttr(f"{seq_node}.maxFrame")),
                cut_duration=co - ci,
            ),
            save_locs=[
                (self.SAVE_LOCS.EDIT, True),
                (self.SAVE_LOCS.CURRENT, True),
                (self.SAVE_LOCS.CUSTOM, False),
            ],
            use_sequencer=True,
        )

        super().__init__(parent, shots + [sequence], "Lnd Previs Playblast")

    def _do_camera_shot_lookup(self) -> str:
        """Look up the current shot based off of the camera"""
        panel: str = mc.getPanel(withLabel="CapturePanel")  # type: ignore[assignment]
        if panel:
            camera = (
                str(mc.modelEditor(panel, query=True, camera=True)).split("|").pop()  # type: ignore[arg-type]
            )
            return self._camera_shot_lookup[camera]
        return "No shot data"

    def _generate_config(self) -> MPlayblastConfig:
        return MPlayblastConfig(
            builtin_huds=[
                "HUDCameraNames",
                "HUDCurrentFrame",
                "HUDFocalLength",
            ],
            custom_huds=[
                HudDefinition(
                    "LnDfilename",
                    command=lambda: str(mc.file(query=True, sceneName=True)),
                    event="SceneSaved",
                    label="File:",
                    section=5,
                ),
                HudDefinition(
                    "LnDartist",
                    command=lambda: os.getlogin(),
                    event="SceneOpened",
                    label="Artist:",
                    section=5,
                ),
                HudDefinition(
                    "LnDshot",
                    command=self._do_camera_shot_lookup,
                    section=7,
                    idle_refresh=True,
                ),
            ],
            lighting=self.use_lighting,
            shadows=self.use_shadows,
            shots=self.shot_configs,
        )
