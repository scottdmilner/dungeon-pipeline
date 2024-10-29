from __future__ import annotations

import logging
import maya.cmds as mc
import os

from abc import abstractmethod
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING
from Qt import QtCore, QtWidgets
from Qt.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

from pipe.glui.dialogs import ButtonPair, MessageDialog
from pipe.util import checkbox_callback_helper, Playblaster

from .playblaster import MPlayblaster
from .struct import HudDefinition, SaveLocation

if TYPE_CHECKING:
    from .struct import MPlayblastConfig, MShotDialogConfig
    from typing import Callable, Iterable

log = logging.getLogger(__name__)


class ClickableQLabel(QLabel):
    clicked = QtCore.Signal()

    def mousePressEvent(self, ev):
        self.clicked.emit()


class PlayblastDialog(QtWidgets.QMainWindow, ButtonPair):
    """Dialog for a generic Maya playblaster. To subclass:
    - subclass SAVE_LOCS as necessary to add more locations
    - define a `_generate_config` function
    """

    _central_widget: QWidget
    _custom_folder_text: QLabel
    _enabled_loc_cbs: dict[str, dict[str, QCheckBox]]
    _enabled_shot_cbs: dict[str, QCheckBox]
    _main_layout: QtWidgets.QLayout
    _use_lighting: QCheckBox
    _use_shadows: QCheckBox

    playblaster = MPlayblaster()
    shot_configs: list[MShotDialogConfig]

    class SAVE_LOCS:
        CUSTOM = SaveLocation("Custom Folder", "", Playblaster.PRESET.WEB)
        CURRENT = SaveLocation(
            "Current Folder",
            Path(mc.file(query=True, sceneName=True)).parent,  # type: ignore[arg-type]
            Playblaster.PRESET.WEB,
        )

    class MAYA_HUDS:
        CAM_NAME = "HUDCameraNames"
        CUR_FRAME = "HUDCurrentFrame"
        FOCAL_LENGTH = "HUDFocalLength"

    class CUSTOM_HUDS:
        FILENAME = HudDefinition(
            "LnDfilename",
            command=lambda: str(mc.file(query=True, sceneName=True)),
            event="SceneSaved",
            label="File:",
            section=5,
        )
        ARTIST = HudDefinition(
            "LnDartist",
            command=lambda: os.getlogin(),
            event="SceneOpened",
            label="Artist:",
            section=5,
        )

    def __init__(
        self,
        parent: QWidget | None,
        shot_configs: list[MShotDialogConfig],
        windowTitle: str = "LnD Playblast",
    ) -> None:
        super().__init__(parent, windowTitle=windowTitle)
        # initialize SAVE_LOCS custom path
        self.SAVE_LOCS.CUSTOM._path = lambda: self._custom_folder_text.text()

        # initialize other values
        self.shot_configs = shot_configs
        self._enabled_shot_cbs = dict()
        self._enabled_loc_cbs = defaultdict(dict)
        self._setup_ui()

    def _setup_ui(self) -> None:
        # set up main layout
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._main_layout = QtWidgets.QVBoxLayout()
        self._central_widget.setLayout(self._main_layout)

        # title
        title = QLabel("Playblast")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: bold;")
        self._main_layout.addWidget(title, 0)

        # iterate over shot configs and add them to the table
        playblasts_layout = QtWidgets.QGridLayout()
        for idx, pb in enumerate(self.shot_configs):
            # create shot enable checkbox
            shot_enable_cb_widget = QWidget()
            shot_enable_cb_layout = QHBoxLayout(shot_enable_cb_widget)
            self._enabled_shot_cbs[pb.id] = QCheckBox()
            cb = self._enabled_shot_cbs[pb.id]
            cb.setChecked(True)
            shot_enable_cb_layout.addWidget(cb)

            shot_label = ClickableQLabel(f"<b>{pb.name}</b>", cb)
            shot_label.clicked.connect(self._click_checkbox(cb))
            shot_enable_cb_layout.addWidget(shot_label)
            playblasts_layout.addWidget(shot_enable_cb_widget, idx + 1, 0, 1, 1)

            # disable the output checkboxes when the shot is disabled
            outputs_container = QWidget()
            cb.toggled.connect(checkbox_callback_helper(cb, outputs_container))
            outputs_layout = QHBoxLayout(outputs_container)
            playblasts_layout.addWidget(outputs_container, idx + 1, 1, 1, 1)

            # create the location checkboxes
            for location, enabled_by_default in pb.save_locs:
                loc_cb = QCheckBox(location.name)
                loc_cb.setChecked(enabled_by_default)
                self._enabled_loc_cbs[pb.id][location.name] = loc_cb
                outputs_layout.addWidget(loc_cb)

            playblasts_layout.addWidget(outputs_container, idx + 1, 2, 1, 1)

        # Create check all/none buttons
        shots_toggle_container = QWidget()
        shots_toggle_container.setStyleSheet("margin: 0; padding: 0;")
        shots_toggle_layout = QHBoxLayout(shots_toggle_container)
        shots_all = QtWidgets.QPushButton("All", self)
        shots_all.clicked.connect(
            lambda: [
                cb.setChecked(True)  # type: ignore[func-returns-value]
                for cb in self._enabled_shot_cbs.values()
                if cb.isEnabled()
            ]
        )
        shots_toggle_layout.addWidget(shots_all)
        shots_none = QtWidgets.QPushButton("None", self)
        shots_none.clicked.connect(
            lambda: [
                cb.setChecked(False)  # type: ignore[func-returns-value]
                for cb in self._enabled_shot_cbs.values()
                if cb.isEnabled()
            ]
        )
        shots_toggle_layout.addWidget(shots_none)

        outputs_toggle_container = QWidget()
        outputs_toggle_layout = QHBoxLayout(outputs_toggle_container)
        for loc, _ in pb.save_locs:
            loc_toggle_container = QWidget()
            loc_toggle_container.setStyleSheet("margin: 0; padding: 0;")
            loc_toggle_layout = QHBoxLayout(loc_toggle_container)
            loc_all = QtWidgets.QPushButton("All", self)
            loc_all.clicked.connect(
                self._set_checkboxes(self._enabled_loc_cbs.values(), loc.name, True)
            )
            loc_toggle_layout.addWidget(loc_all)
            loc_none = QtWidgets.QPushButton("None", self)
            loc_none.clicked.connect(
                self._set_checkboxes(self._enabled_loc_cbs.values(), loc.name, False)
            )
            loc_toggle_layout.addWidget(loc_none)
            outputs_toggle_layout.addWidget(loc_toggle_container)

        playblasts_layout.addWidget(shots_toggle_container, 0, 0, 1, 1)
        playblasts_layout.addWidget(outputs_toggle_container, 0, 1)

        # configure playblast widget group
        playblasts_widget = QWidget()
        playblasts_widget.setLayout(playblasts_layout)
        playblasts_scroll_area = QtWidgets.QScrollArea()
        playblasts_scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff
        )
        playblasts_scroll_area.setWidget(playblasts_widget)
        playblasts_scroll_area.setWidgetResizable(True)
        self._main_layout.addWidget(playblasts_scroll_area)

        # create lighting, shadow, ssao toggles
        active_editor = str(mc.sequenceManager(query=True, modelPanel=True))
        toggles_layout = QHBoxLayout()
        toggles_widget = QWidget()
        toggles_widget.setLayout(toggles_layout)
        self._use_lighting = QCheckBox("Use Lighting")
        self._use_lighting.setChecked(
            mc.modelEditor(active_editor, query=True, displayLights=True) == "all"
        )
        toggles_layout.addWidget(self._use_lighting)
        self._use_shadows = QCheckBox("Use Shadows")
        self._use_shadows.setChecked(
            bool(mc.modelEditor(active_editor, query=True, shadows=True))
        )
        toggles_layout.addWidget(self._use_shadows)
        self._use_ssao = QCheckBox("Use Anti-aliasing")
        self._use_ssao.setChecked(
            bool(mc.getAttr("hardwareRenderingGlobals.ssaoEnable"))
        )
        toggles_layout.addWidget(self._use_ssao)
        self._use_hardware_fog = QCheckBox("Use Hardware Fog")
        self._use_hardware_fog.setChecked(
            bool(mc.modelEditor(active_editor, query=True, fogging=True))
        )
        toggles_layout.addWidget(self._use_hardware_fog)
        self._main_layout.addWidget(toggles_widget)

        # custom folder prompt
        custom_folder_layout = QHBoxLayout()
        self._custom_folder_text = QLabel(os.getenv("TMPDIR", os.getenv("TEMP", "tmp")))
        custom_folder_button = QtWidgets.QPushButton(text="Set Custom Folder")
        custom_folder_button.clicked.connect(self._set_custom_folder)
        custom_folder_layout.addWidget(self._custom_folder_text)
        custom_folder_layout.addWidget(custom_folder_button)
        self._main_layout.addLayout(custom_folder_layout)

        self._init_buttons(has_cancel_button=True, ok_name="Playblast")
        self.buttons.rejected.connect(self.close)
        self.buttons.accepted.connect(self.do_export)
        self._main_layout.addWidget(self.buttons)

    @staticmethod
    def _click_checkbox(checkbox: QCheckBox) -> Callable[[], None]:
        def inner() -> None:
            checkbox.click()

        return inner

    @staticmethod
    def _set_checkboxes(
        checkboxes_index: Iterable[dict[str, QCheckBox]], loc: str, val: bool
    ) -> Callable[[], None]:
        def inner() -> None:
            for cbi in checkboxes_index:
                cbi[loc].setChecked(val)

        return inner

    @property
    def use_lighting(self) -> bool:
        return self._use_lighting.isChecked()

    @property
    def use_shadows(self) -> bool:
        return self._use_shadows.isChecked()

    @property
    def use_ssao(self) -> bool:
        return self._use_ssao.isChecked()

    @property
    def use_hardware_fog(self) -> bool:
        return self._use_hardware_fog.isChecked()

    def save_locations_to_paths(
        self, dialog_id: str, locs: Iterable[SaveLocation], filename: str
    ) -> dict[Playblaster.PRESET, list[str | Path]]:
        paths: dict[Playblaster.PRESET, list[str | Path]] = defaultdict(list)
        for loc in locs:
            if self.is_location_enabled(dialog_id, loc.name):
                paths[loc.preset].append(str(loc.path) + "/" + filename)

        return paths

    def _set_custom_folder(self) -> None:
        """Prompt user to select a custom folder for saving"""
        path_list = mc.fileDialog2(
            caption="Select a custom playblast folder",
            fileMode=2,
            hideNameEdit=True,
            okCaption="Select",
            setProjectBtnEnabled=False,
        )
        if path_list:
            path = path_list[0]
            self._custom_folder_text.setText(path)

    @abstractmethod
    def _generate_config(self) -> MPlayblastConfig:
        pass

    def is_shot_enabled(self, dialog_id: str) -> bool:
        """Takes an MShotDialogConfig id and returns if it's enabled"""
        return self._enabled_shot_cbs[dialog_id].isChecked()

    def is_location_enabled(self, dialog_id: str, loc_name: str) -> bool:
        return self._enabled_loc_cbs[dialog_id][loc_name].isChecked()

    def do_export(self):
        self.playblaster.configure(self._generate_config()).playblast()

        MessageDialog(self.parent(), "Playblast(s) successful!").exec_()
        self.close()
