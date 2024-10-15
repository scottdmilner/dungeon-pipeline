from __future__ import annotations

import copy
import logging
import os
import maya.cmds as mc

from abc import abstractmethod
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from Qt import QtCore, QtWidgets
from Qt.QtWidgets import QCheckBox, QWidget

from mayacapture.capture import capture  # type: ignore[import-not-found]
from pipe.db import DB
from pipe.glui.dialogs import ButtonPair, MessageDialog
from pipe.struct.db import Shot
from pipe.util import checkbox_callback_helper, Playblaster
from shared.util import get_edit_path

from env_sg import DB_Config

if TYPE_CHECKING:
    from typing import Any, Callable, Generator, Literal

log = logging.getLogger(__name__)


class _SaveLocation:
    """Information needed for a save location. If a lambda is provided to
    `path` it will call that and return the value"""

    name: str
    preset: Playblaster.PRESET
    _path: str | Path | Callable[[], str | Path]

    def __init__(
        self,
        name: str,
        path: str | Path | Callable[[], str | Path],
        preset: Playblaster.PRESET,
    ):
        self.name = name
        self._path = path
        self.preset = preset

    @property
    def path(self) -> str | Path:
        if callable(self._path):
            return self._path()
        else:
            return self._path


@dataclass
class MShotPlayblastConfig:
    camera: str | None
    name: str
    shot: Shot
    save_locs: list[tuple[_SaveLocation, bool]]
    enabled: bool = True
    paths: dict[Playblaster.PRESET, list[str | Path]] = field(default_factory=dict)
    tail: int = 0
    use_sequencer: bool = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_paths(self, paths: dict[Playblaster.PRESET, list[str | Path]]) -> None:
        self.paths = paths


@dataclass
class _HudDefinition:
    name: str
    command: Callable[[], str]
    section: int
    event: str = ""
    label: str = ""
    idle_refresh: bool = False
    blockSize: Literal["small", "large"] = "small"
    labelFontSize: Literal["small", "large"] = "small"


@dataclass
class MPlayblastConfig:
    builtin_huds: list[str]
    custom_huds: list[_HudDefinition]
    lighting: bool
    shadows: bool
    shots: list[MShotPlayblastConfig]


def dummy_shot(code: str, cut_in: int, cut_out: int, cut_duration: int) -> Shot:
    return Shot(
        code=code,
        id=0,
        assets=[],
        cut_in=cut_in,
        cut_out=cut_out,
        cut_duration=cut_duration,
        sequence=None,
        set=None,
    )


class MPlayblaster(Playblaster):
    _config: MPlayblastConfig
    _extra_kwargs: dict[str, Any]

    def __init__(self) -> None:
        super().__init__(DB.Get(DB_Config))

    def configure(self, config: MPlayblastConfig) -> MPlayblaster:
        self._config = config
        return self

    def _write_images(self, path: str) -> None:
        """Maya implementation of playblasting image frames"""
        self._extra_kwargs["viewport2_options"].update(
            {
                "maxHardwareLights": 16,
                "multiSampleEnable": True,
                "ssaoEnable": True,
            }
        )

        capture(
            width=1920,
            height=816,
            filename=path,
            start_frame=(self._shot.cut_in - 5),
            end_frame=(self._shot.cut_out + 5),
            format="image",
            compression="png",
            off_screen=True,
            show_ornaments=True,
            overwrite=True,
            maintain_aspect_ratio=False,
            viewer=0,
            **self._extra_kwargs,
        )

    def playblast(self) -> None:
        with _applied_hud(
            self._config.builtin_huds, self._config.custom_huds
        ), _unselect_all():
            # assemble kwargs from config options
            global_kwargs: dict[str, Any] = {
                "viewport_options": {},
                "viewport2_options": {},
            }
            if self._config.lighting:
                global_kwargs["viewport_options"].update({"displayLights": "all"})

            if self._config.shadows:
                global_kwargs["viewport_options"].update({"shadows": True})

            # iterate over shots and playblast
            for shot_config in self._config.shots:
                if not shot_config.enabled:
                    continue

                # assemble shot-specific kwargs
                self._extra_kwargs = copy.deepcopy(global_kwargs)
                if shot_config.use_sequencer:
                    self._extra_kwargs["use_camera_sequencer"] = True
                else:
                    self._extra_kwargs["camera"] = shot_config.camera

                with self(shot_config.shot):
                    super()._do_playblast(
                        shot_config.paths,
                        shot_config.tail,
                    )


class _ClickableQLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()

    def mousePressEvent(self, ev):
        self.clicked.emit()


class _PlayblastDialog(QtWidgets.QMainWindow, ButtonPair):
    _central_widget: QWidget
    _custom_folder_text: QtWidgets.QLabel
    _data: dict[str, dict[str, bool]]
    _enabled_checkboxes: dict[str, QCheckBox]
    _main_layout: QtWidgets.QLayout
    _shot_configs: list[MShotPlayblastConfig]
    _use_lighting: QCheckBox
    _use_shadows: QCheckBox

    playblaster = MPlayblaster()

    class SAVE_LOCS:
        CUSTOM = _SaveLocation("Custom Folder", "", Playblaster.PRESET.WEB)
        CURRENT = _SaveLocation(
            "Current Folder",
            Path(mc.file(query=True, sceneName=True)).parent,  # type: ignore[arg-type]
            Playblaster.PRESET.WEB,
        )

    def __init__(
        self,
        parent: QWidget | None,
        shot_configs: list[MShotPlayblastConfig],
        windowTitle: str = "LnD Playblast",
    ) -> None:
        super().__init__(parent, windowTitle=windowTitle)
        self.SAVE_LOCS.CUSTOM._path = lambda: self._custom_folder_text.text()
        self._shot_configs = shot_configs
        self._enabled_checkboxes = dict()
        self._data = defaultdict(dict)
        self._setup_ui()

    def _setup_ui(self) -> None:
        # set up main layout
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._main_layout = QtWidgets.QVBoxLayout()
        self._central_widget.setLayout(self._main_layout)

        # title
        title = QtWidgets.QLabel("Playblast")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: bold;")
        self._main_layout.addWidget(title, 0)

        # iterate over shot configs and add them to the table
        playblasts_layout = QtWidgets.QGridLayout()
        for idx, pb in enumerate(self._shot_configs):
            # create shot checkbox
            self._enabled_checkboxes[pb.name] = QCheckBox()
            cb = self._enabled_checkboxes[pb.name]
            cb.setChecked(True)
            playblasts_layout.addWidget(cb, idx, 0, 1, 1)
            shot_label = _ClickableQLabel(f"<b>{pb.name}</b>", cb)
            shot_label.clicked.connect(self._click_checkbox(cb))
            playblasts_layout.addWidget(shot_label, idx, 1, 1, 1)

            # disable the output checkboxes when the shot is disabled
            outputs_container = QWidget()
            cb.toggled.connect(checkbox_callback_helper(cb, outputs_container))
            outputs_layout = QtWidgets.QHBoxLayout(outputs_container)
            playblasts_layout.addWidget(outputs_container, idx, 2, 1, 1)

            # create the location checkboxes
            for location, enabled_by_default in pb.save_locs:
                loc_cb = QCheckBox(location.name)
                loc_cb.setChecked(enabled_by_default)
                self._data[pb.name][location.name] = enabled_by_default
                loc_cb.toggled.connect(
                    self._update_on_check(self._data[pb.name], location.name, loc_cb)
                )
                outputs_layout.addWidget(loc_cb)

            playblasts_layout.addWidget(outputs_container, idx, 3, 1, 1)

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

        # create lighting and shadow toggles
        toggles_layout = QtWidgets.QHBoxLayout()
        toggles_widget = QWidget()
        toggles_widget.setLayout(toggles_layout)
        self._use_lighting = QCheckBox("Use Lighting")
        self._use_lighting.setChecked(True)
        toggles_layout.addWidget(self._use_lighting)
        self._use_shadows = QCheckBox("Use Shadows")
        toggles_layout.addWidget(self._use_shadows)
        self._main_layout.addWidget(toggles_widget)

        # custom folder prompt
        custom_folder_layout = QtWidgets.QHBoxLayout()
        self._custom_folder_text = QtWidgets.QLabel(
            os.getenv("TMPDIR", os.getenv("TEMP", "tmp"))
        )
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
    def _update_on_check(
        data: dict, key: str, checkbox: QCheckBox
    ) -> Callable[[], None]:
        def inner() -> None:
            data[key] = checkbox.isChecked()

        return inner

    @staticmethod
    def _click_checkbox(checkbox: QCheckBox) -> Callable[[], None]:
        def inner() -> None:
            checkbox.click()

        return inner

    @property
    def use_lighting(self) -> bool:
        return self._use_lighting.isChecked()

    @property
    def use_shadows(self) -> bool:
        return self._use_shadows.isChecked()

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

    def do_export(self):
        date = datetime.now().strftime("%m-%d-%y")

        # iterate over shots and finalize configs
        for shot in self._shot_configs:
            # disable unenabled checkboxes
            if not self._enabled_checkboxes[shot.name].isChecked():
                shot.set_enabled(False)
                continue

            # sort paths by export preset
            paths = defaultdict(list)
            for loc, _ in shot.save_locs:
                if self._data[shot.name][loc.name]:
                    paths[loc.preset].append(str(loc.path) + f"/{shot.name}_{date}")

            shot.set_paths(paths)

        print(self._generate_config())

        self.playblaster.configure(self._generate_config()).playblast()

        MessageDialog(self.parent(), "Playblast(s) successful!").exec_()

        self.close()


class PrevisPlayblastDialog(_PlayblastDialog):
    _camera_shot_lookup: dict[str, str]

    class SAVE_LOCS(_PlayblastDialog.SAVE_LOCS):
        EDIT = _SaveLocation(
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
                name=(name := str(mc.shot(shot_node, query=True, shotName=True))),
                camera=mc.shot(shot_node, query=True, currentCamera=True),  # type: ignore[arg-type]
                shot=dummy_shot(
                    name,
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
        sequence = MShotPlayblastConfig(
            name=Path(mc.file(query=True, sceneName=True)).stem,  # type: ignore[arg-type]
            camera=None,
            shot=dummy_shot(
                code=(
                    seq := str(mc.sequenceManager(query=True, writableSequencer=True))
                ),
                cut_in=(ci := mc.getAttr(f"{seq}.minFrame")),
                cut_out=(co := mc.getAttr(f"{seq}.maxFrame")),
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

    def _camera_shot_lookup_factory(self) -> Callable[[], str]:
        """Return function that can be called to look up the current shot based
        off of the camera"""
        self._panel = ""

        def inner() -> str:
            if not self._panel:
                self._panel = mc.getPanel(withLabel="CapturePanel")  # type: ignore[assignment]
            if self._panel:
                camera = (
                    str(mc.modelEditor(self._panel, query=True, camera=True))
                    .split("|")
                    .pop()
                )
                return self._camera_shot_lookup[camera]
            return "No shot data"

        return inner

    def _generate_config(self) -> MPlayblastConfig:
        return MPlayblastConfig(
            builtin_huds=[
                "HUDCameraNames",
                "HUDCurrentFrame",
                "HUDFocalLength",
            ],
            custom_huds=[
                _HudDefinition(
                    "LnDfilename",
                    command=lambda: str(mc.file(query=True, sceneName=True)),
                    event="SceneSaved",
                    label="File:",
                    section=5,
                ),
                _HudDefinition(
                    "LnDartist",
                    command=lambda: os.getlogin(),
                    event="SceneOpened",
                    label="Artist:",
                    section=5,
                ),
                _HudDefinition(
                    "LnDshot",
                    command=self._camera_shot_lookup_factory(),
                    section=7,
                    idle_refresh=True,
                ),
            ],
            lighting=self.use_lighting,
            shadows=self.use_shadows,
            shots=self._shot_configs,
        )


class AnimPlayblastDialog(_PlayblastDialog):
    class SAVE_LOCS(_PlayblastDialog.SAVE_LOCS):
        CURRENT = _SaveLocation(
            "Current Folder",
            Path(mc.file(query=True, sceneName=True)).parent,  # type: ignore[arg-type]
            Playblaster.PRESET.EDIT_SQ,
        )

    def __init__(self, parent):
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


@contextmanager
def _applied_hud(
    builtin_huds: list[str], custom_huds: list[_HudDefinition]
) -> Generator[None, None, None]:
    # hide current huds and store current state
    orig_visibility: dict[str, bool] = {}
    orig_huds: list[str] = mc.headsUpDisplay(query=True, listHeadsUpDisplays=True)  # type: ignore[assignment]
    for hud in orig_huds:
        vis = bool(mc.headsUpDisplay(hud, query=True, visible=True))
        orig_visibility[hud] = vis
        if vis:
            mc.headsUpDisplay(hud, edit=True, visible=False)

    # display requested builtin huds
    for hud in builtin_huds:
        mc.headsUpDisplay(hud, edit=True, visible=True)

    # create requested custom huds
    for chud in custom_huds:
        if chud.name in orig_huds:
            mc.headsUpDisplay(chud.name, remove=True)

        kwargs: dict[str, Any] = dict()
        if chud.idle_refresh:
            kwargs.update({"attachToRefresh": True})
        else:
            kwargs.update({"event": chud.event})

        mc.headsUpDisplay(
            chud.name,
            block=mc.headsUpDisplay(nextFreeBlock=chud.section),  # type: ignore[arg-type]
            blockSize=chud.blockSize,
            command=chud.command,
            label=chud.label,
            labelFontSize=chud.labelFontSize,
            section=chud.section,
            **kwargs,
        )

    try:
        yield
    finally:
        # restore original visibility
        for hud, state in orig_visibility.items():
            mc.headsUpDisplay(hud, edit=True, visible=state)

        for chud in custom_huds:
            mc.headsUpDisplay(chud.name, remove=True)


@contextmanager
def _unselect_all() -> Generator[None, None, None]:
    selection = mc.ls(selection=True, long=True, ufeObjects=True, absoluteName=True)
    mc.select(clear=True)

    try:
        yield
    finally:
        mc.select(*selection, replace=True)
