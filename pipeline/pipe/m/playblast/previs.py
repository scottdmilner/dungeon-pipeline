from __future__ import annotations

import logging
import maya.cmds as mc

from datetime import datetime
from pathlib import Path

from pipe.util import Playblaster
from shared.util import get_edit_path

from .struct import (
    HudDefinition,
    MPlayblastConfig,
    MShotDialogConfig,
    MShotPlayblastConfig,
    SaveLocation,
    dummy_shot,
)
from .ui import PlayblastDialog

log = logging.getLogger(__name__)


class PrevisPlayblastDialog(PlayblastDialog):
    _camera_shot_lookup: dict[str, str]
    _sequence_dialog_configs: list[MShotDialogConfig]
    _shot_dialog_configs: list[MShotDialogConfig]

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

        self._shot_dialog_configs = [
            MShotDialogConfig(
                id=shot_node,
                name=str(mc.shot(shot_node, query=True, shotName=True)),
                save_locs=[
                    (self.SAVE_LOCS.EDIT, True),
                    (self.SAVE_LOCS.CURRENT, False),
                    (self.SAVE_LOCS.CUSTOM, False),
                ],
            )
            for shot_node in shot_node_list
        ]
        self._sequence_dialog_configs = [
            MShotDialogConfig(
                id=str(mc.sequenceManager(query=True, writableSequencer=True)),
                name="Camera Sequencer",
                save_locs=[
                    (self.SAVE_LOCS.EDIT, True),
                    (self.SAVE_LOCS.CURRENT, True),
                    (self.SAVE_LOCS.CUSTOM, False),
                ],
            )
        ]

        super().__init__(
            parent,
            self._shot_dialog_configs + self._sequence_dialog_configs,
            "Lnd Previs Playblast",
        )

    def _do_camera_shot_lookup(self) -> str:
        """Look up the current shot based off of the camera"""
        panel: str = mc.getPanel(withLabel="CapturePanel")  # type: ignore[assignment]
        try:
            if panel:
                camera = (
                    str(mc.modelEditor(panel, query=True, camera=True)).split("|").pop()  # type: ignore[arg-type]
                )
                return self._camera_shot_lookup[camera]
        except KeyError:
            pass
        return "No shot data"

    def _generate_config(self) -> MPlayblastConfig:
        seq_node = str(mc.sequenceManager(query=True, writableSequencer=True))
        date = datetime.now().strftime("%m-%d-%y")
        return MPlayblastConfig(
            builtin_huds=[
                PlayblastDialog.MAYA_HUDS.CAM_NAME,
                PlayblastDialog.MAYA_HUDS.CUR_FRAME,
                PlayblastDialog.MAYA_HUDS.FOCAL_LENGTH,
            ],
            custom_huds=[
                PlayblastDialog.CUSTOM_HUDS.FILENAME,
                PlayblastDialog.CUSTOM_HUDS.ARTIST,
                HudDefinition(
                    "LnDshot",
                    command=self._do_camera_shot_lookup,
                    section=7,
                    idle_refresh=True,
                ),
            ],
            hardware_fog=self.use_hardware_fog,
            lighting=self.use_lighting,
            shadows=self.use_shadows,
            shots=[
                MShotPlayblastConfig(
                    camera=str(mc.shot(config.id, query=True, currentCamera=True)),
                    shot=dummy_shot(
                        shot_name := str(mc.shot(config.id, query=True, shotName=True)),
                        int(mc.shot(config.id, query=True, startTime=True)),
                        int(mc.shot(config.id, query=True, endTime=True)),
                        int(mc.shot(config.id, query=True, clipDuration=True)),
                    ),
                    paths=self.save_locations_to_paths(
                        config.id,
                        (sl[0] for sl in config.save_locs),
                        f"{shot_name}_{date}",
                    ),
                )
                for config in self._shot_dialog_configs
                if self.is_shot_enabled(config.id)
            ]
            + [
                MShotPlayblastConfig(
                    camera=None,
                    shot=dummy_shot(
                        code=(name := Path(mc.file(query=True, sceneName=True)).stem),  # type: ignore[arg-type]
                        cut_in=(ci := mc.getAttr(f"{seq_node}.minFrame")),
                        cut_out=(co := mc.getAttr(f"{seq_node}.maxFrame")),
                        cut_duration=co - ci,
                    ),
                    paths=self.save_locations_to_paths(
                        config.id, (sl[0] for sl in config.save_locs), f"{name}_{date}"
                    ),
                    use_sequencer=True,
                )
                for config in self._sequence_dialog_configs
                if self.is_shot_enabled(config.id)
            ],
            ssao=self.use_ssao,
        )
