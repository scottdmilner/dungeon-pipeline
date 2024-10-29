from __future__ import annotations

import logging
import maya.cmds as mc

from datetime import datetime
from typing import TYPE_CHECKING
from Qt.QtWidgets import QComboBox, QGridLayout, QLabel, QSpinBox, QWidget
from Qt.QtCore import QRegExp
from Qt.QtGui import QRegExpValidator

from pipe.db import DB
from pipe.util import checkbox_callback_helper, Playblaster
from shared.util import get_edit_path
from env_sg import DB_Config

from .struct import (
    HudDefinition,
    MPlayblastConfig,
    MShotDialogConfig,
    MShotPlayblastConfig,
    SaveLocation,
    dummy_shot,
)
from .ui import PlayblastDialog

if TYPE_CHECKING:
    from pipe.struct.db import Shot

log = logging.getLogger(__name__)


class AnimPlayblastDialog(PlayblastDialog):
    _conn: DB
    _shot: Shot | None

    class SAVE_LOCS(PlayblastDialog.SAVE_LOCS):
        EDIT = SaveLocation(
            "Send to Edit",
            get_edit_path() / "anim" / datetime.now().strftime("%m-%d-%y"),
            Playblaster.PRESET.EDIT_SQ,
        )

    SG_ID = "sg"
    CUSTOM_ID = "custom"

    def __init__(self, parent):
        self._conn = DB.Get(DB_Config)
        try:
            code = str(mc.fileInfo("code", query=True)[0])
            self._shot = self._conn.get_shot_by_code(code)
        except Exception:
            self._shot = None

        self._shot_dialog_configs = [
            MShotDialogConfig(
                id=self.SG_ID,
                name="Shot (from SG)",
                save_locs=[
                    (self.SAVE_LOCS.EDIT, False),
                    (self.SAVE_LOCS.CURRENT, True),
                    (self.SAVE_LOCS.CUSTOM, False),
                ],
            ),
            MShotDialogConfig(
                id=self.CUSTOM_ID,
                name="Custom",
                save_locs=[
                    (self.SAVE_LOCS.EDIT, False),
                    (self.SAVE_LOCS.CURRENT, True),
                    (self.SAVE_LOCS.CUSTOM, False),
                ],
            ),
        ]
        super().__init__(parent, self._shot_dialog_configs, "LnD Anim Playblast")

    def _setup_ui(self):
        super()._setup_ui()

        # disable the SG option if we can't find this shot in SG
        if not self._shot:
            self._enabled_shot_cbs[self.SG_ID].toggle()
            self._enabled_shot_cbs[self.SG_ID].setEnabled(False)

        anim_settings_widget = QWidget(self)
        anim_settings_layout = QGridLayout(anim_settings_widget)
        self._shot_pass = QComboBox(self)
        self._shot_pass.addItems(["Blocking #", "Polish #"])
        self._shot_pass.setEditable(True)
        self._shot_pass.setValidator(
            QRegExpValidator(QRegExp("(?:Blocking|Polish) #\d+"))
        )
        anim_settings_layout.addWidget(QLabel("Pass"), 0, 0)
        anim_settings_layout.addWidget(self._shot_pass, 0, 1, 1, 2)

        self._main_layout.insertWidget(2, anim_settings_widget)

        # Create UI for custom shot
        custom_shot_widget = QWidget(self)
        custom_shot_layout = QGridLayout(custom_shot_widget)

        self._custom_in = QSpinBox(self, maximum=10000, minimum=0, value=1001)
        self._custom_out = QSpinBox(self, maximum=10000, minimum=0, value=1100)
        custom_shot_layout.addWidget(QLabel("Custom In"), 1, 1)
        custom_shot_layout.addWidget(self._custom_in, 1, 2)
        custom_shot_layout.addWidget(QLabel("Custom Out"), 1, 3)
        custom_shot_layout.addWidget(self._custom_out, 1, 4)

        self._custom_camera = QComboBox(self)
        self._custom_camera.addItems(cameras := mc.ls(cameras=True, visible=True))
        self._custom_camera.setCurrentIndex(0)
        self._custom_camera.setValidator(QRegExpValidator(QRegExp("|".join(cameras))))
        custom_shot_layout.addWidget(QLabel("Custom Camera"), 2, 1)
        custom_shot_layout.addWidget(self._custom_camera, 2, 2, 1, 2)

        # disable UI if custom shot not enabled
        (escb := self._enabled_shot_cbs[self.CUSTOM_ID]).toggled.connect(
            checkbox_callback_helper(escb, custom_shot_widget)
        )

        self._main_layout.insertWidget(3, custom_shot_widget)

    def _generate_config(self) -> MPlayblastConfig:
        date = datetime.now().strftime("%m-%d-%y")
        shots: list[MShotPlayblastConfig] = []

        if self.is_shot_enabled(self.SG_ID):
            assert self._shot is not None
            sg_config = next(c for c in self._shot_dialog_configs if c.id == self.SG_ID)
            shots.append(
                MShotPlayblastConfig(
                    camera="|__mayaUsd__|shotCamParent|shotCam",
                    shot=self._shot,
                    paths=self.save_locations_to_paths(
                        self.SG_ID,
                        (sl[0] for sl in sg_config.save_locs),
                        f"{self._shot.code}_{date}",
                    ),
                    tails=(5, 5),
                )
            )

        if self.is_shot_enabled(self.CUSTOM_ID):
            custom_config = next(
                c for c in self._shot_dialog_configs if c.id == self.CUSTOM_ID
            )
            shots.append(
                MShotPlayblastConfig(
                    camera=self._custom_camera.currentText(),
                    shot=dummy_shot(
                        "custom",
                        inv := self._custom_in.value(),
                        outv := self._custom_out.value(),
                        cut_duration=outv - inv,
                    ),
                    paths=self.save_locations_to_paths(
                        self.CUSTOM_ID,
                        (sl[0] for sl in custom_config.save_locs),
                        f"customPB_{date}",
                    ),
                )
            )

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
                    command=lambda: self._shot.code
                    if self._shot
                    else "No shot code found",
                    section=7,
                    event="SceneSaved",
                ),
                HudDefinition(
                    "LnDpass",
                    command=lambda: self._shot_pass.currentText(),
                    label="Pass:",
                    section=5,
                    event="SceneSaved",
                ),
            ],
            hardware_fog=self.use_hardware_fog,
            lighting=self.use_lighting,
            shadows=self.use_shadows,
            shots=shots,
            ssao=self.use_ssao,
        )
