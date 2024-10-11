from __future__ import annotations

import os
import maya.cmds as mc

from abc import abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from Qt import QtCore, QtWidgets
from Qt.QtWidgets import QCheckBox

from mayacapture.capture import capture  # type: ignore[import-not-found]
from pipe.db import DB
from pipe.glui.dialogs import ButtonPair
from pipe.struct.db import Shot
from pipe.util import checkbox_callback_helper, Playblaster
from shared.util import get_edit_path

from env_sg import DB_Config

if TYPE_CHECKING:
    from typing import Any, Callable, Generator, Literal


class _ShotPlayblastWidget(QtWidgets.QWidget):
    _enabled_checkbox: QCheckBox
    _locations: list[tuple[_SaveLocation, bool]]
    _data: dict[str, bool]
    _name: str

    def __init__(
        self,
        parent: _PlayblastDialog,
        name: str,
        locations: list[tuple[_SaveLocation, bool]],
    ) -> None:
        super().__init__(parent)
        self.setParent(parent)
        self._locations = locations
        self._data = dict()
        self._name = name
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QtWidgets.QHBoxLayout()
        layout.setAlignment(QtCore.Qt.AlignTop)

        self._enabled_checkbox = QCheckBox()
        self._enabled_checkbox.setChecked(True)
        layout.addWidget(self._enabled_checkbox, 0, QtCore.Qt.AlignRight)
        shot_label = QtWidgets.QLabel(f"<b>{self._name}</b>", self._enabled_checkbox)
        shot_label.setFixedWidth(160)
        layout.addWidget(shot_label, 0, QtCore.Qt.AlignLeft)

        outputs_container = QtWidgets.QWidget()
        self._enabled_checkbox.toggled.connect(
            checkbox_callback_helper(self._enabled_checkbox, outputs_container)
        )
        outputs_layout = QtWidgets.QHBoxLayout(outputs_container)
        layout.addWidget(outputs_container, 90)

        for location, enabled_by_default in self._locations:
            cb = QCheckBox(location.name)
            cb.setChecked(enabled_by_default)
            self._data[location.name] = enabled_by_default
            cb.toggled.connect(self._update_on_check(self._data, location.name, cb))

            outputs_layout.addWidget(cb)

        self.setLayout(layout)

    @staticmethod
    def _update_on_check(
        data: dict, key: str, checkbox: QtWidgets.QCheckBox
    ) -> Callable[[], None]:
        def inner() -> None:
            data[key] = checkbox.isChecked()

        return inner

    def get_location(self, location: str) -> bool:
        return self._data[location]

    @property
    def enabled(self) -> bool:
        return self._enabled_checkbox.isChecked()


@dataclass
class MShotPlayblastConfig:
    camera: str | None
    name: str
    shot: Shot
    save_locs: list[tuple[_SaveLocation, bool]]
    enabled: bool = True
    paths: list[str | Path] = field(default_factory=list)
    tail: int = 0
    use_sequencer: bool = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_paths(self, paths: list[str | Path]) -> None:
        self.paths = paths


@dataclass
class _SaveLocation:
    name: str
    path: str | Path


class _PlayblastDialog(QtWidgets.QMainWindow, ButtonPair):
    _central_widget: QtWidgets.QWidget
    _custom_folder_text: QtWidgets.QLabel
    _main_layout: QtWidgets.QLayout
    _shot_widgets: dict[str, _ShotPlayblastWidget]
    _shot_configs: list[MShotPlayblastConfig]

    class SAVE_LOCS:
        CUSTOM = _SaveLocation("Custom Folder", "")

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        shot_configs: list[MShotPlayblastConfig],
        windowTitle: str = "LnD Playblast",
    ) -> None:
        super().__init__(parent, windowTitle=windowTitle)
        self._shot_configs = shot_configs
        self._shot_widgets = dict()
        self._setup_ui()

    def _setup_ui(self) -> None:
        # make sure window always stays on top
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        # set up main layout
        self._central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self._central_widget)
        self._main_layout = QtWidgets.QVBoxLayout()
        self._central_widget.setLayout(self._main_layout)

        # title
        title = QtWidgets.QLabel("Playblast")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: bold;")
        self._main_layout.addWidget(title, 0)

        # playblast widgets
        playblasts_layout = QtWidgets.QVBoxLayout()
        for pb in self._shot_configs:
            widget = _ShotPlayblastWidget(self, pb.name, pb.save_locs)
            self._shot_widgets[pb.name] = widget
            playblasts_layout.addWidget(widget)

        # configure playblast widget group
        playblasts_widget = QtWidgets.QWidget()
        playblasts_widget.setLayout(playblasts_layout)
        playblasts_scroll_area = QtWidgets.QScrollArea()
        playblasts_scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff
        )
        playblasts_scroll_area.setWidget(playblasts_widget)
        playblasts_scroll_area.setWidgetResizable(True)
        self._main_layout.addWidget(playblasts_scroll_area)

        # custom folder prompt
        custom_folder_layout = QtWidgets.QHBoxLayout()
        self._custom_folder_text = QtWidgets.QLabel("no custom folder set")
        custom_folder_button = QtWidgets.QPushButton(text="Set Custom Folder")
        custom_folder_button.clicked.connect(self._set_custom_folder)
        custom_folder_layout.addWidget(self._custom_folder_text)
        custom_folder_layout.addWidget(custom_folder_button)
        self._main_layout.addLayout(custom_folder_layout)

        self._init_buttons(has_cancel_button=True, ok_name="Playblast")
        self.buttons.rejected.connect(self.close)
        self.buttons.accepted.connect(self.do_export)
        self._main_layout.addWidget(self.buttons)

    def _set_custom_folder(self) -> None:
        """Prompt user to select a custom folder for saving"""
        paths = mc.fileDialog2(
            caption="Select a custom playblast folder",
            fileMode=2,
            hideNameEdit=True,
            setProjectBtnEnabled=False,
        )
        if paths:
            path = paths[0]
            self._custom_folder_text.setText(path)

            self.SAVE_LOCS.CUSTOM.path = path

    @abstractmethod
    def _generate_config(self) -> MPlayblastConfig:
        pass

    def do_export(self):
        date = datetime.now().strftime("%m-%d-%y")

        for shot in self._shot_configs:
            widget = self._shot_widgets[shot.name]
            if not widget.enabled:
                shot.set_enabled(False)
                continue

            paths = [
                str(loc.path) + f"/{shot.name}_{date}.mov"
                for loc, _ in shot.save_locs
                if widget.get_location(loc.name)
            ]
            shot.set_paths(paths)

        MPlayblaster(self._generate_config()).playblast()


class PrevisPlayblastDialog(_PlayblastDialog):
    class SAVE_LOCS(_PlayblastDialog.SAVE_LOCS):
        EDIT = _SaveLocation(
            "Send to Edit",
            get_edit_path() / "previs" / datetime.now().strftime("%m-%d-%y"),
        )
        CURRENT = _SaveLocation(
            "Current Folder",
            Path(mc.file(query=True, sceneName=True)).parent,  # type: ignore[arg-type]
        )

    def __init__(self, parent) -> None:
        shot_list: list[str] = mc.sequenceManager(listShots=True) or []  # type: ignore[assignment]

        # generate playblast configs
        shots = [
            MShotPlayblastConfig(
                name=shot,
                camera=mc.shot(shot, query=True, currentCamera=True),  # type: ignore[arg-type]
                shot=dummy_shot(
                    shot,
                    int(mc.shot(shot, query=True, startTime=True)),
                    int(mc.shot(shot, query=True, endTime=True)),
                    int(mc.shot(shot, query=True, clipDuration=True)),
                ),
                save_locs=[
                    (self.SAVE_LOCS.EDIT, True),
                    (self.SAVE_LOCS.CURRENT, False),
                    (self.SAVE_LOCS.CUSTOM, False),
                ],
            )
            for shot in shot_list
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
            ],
            shots=self._shot_configs,
        )


@dataclass
class _HudDefinition:
    name: str
    command: Callable[[], str]
    event: str
    label: str
    section: int
    blockSize: Literal["small", "large"] = "small"
    labelFontSize: Literal["small", "large"] = "small"


@dataclass
class MPlayblastConfig:
    builtin_huds: list[str]
    custom_huds: list[_HudDefinition]
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

    def __init__(self, config: MPlayblastConfig) -> None:
        self._config = config
        super().__init__(DB.Get(DB_Config))

    def _write_images(self, path: str) -> None:
        """Maya implementation of playblasting image frames"""
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
            for shot_config in self._config.shots:
                if not shot_config.enabled:
                    continue

                self._extra_kwargs = dict()
                if shot_config.use_sequencer:
                    self._extra_kwargs["use_camera_sequencer"] = True
                else:
                    self._extra_kwargs["camera"] = shot_config.camera

                with self(shot_config.shot):
                    super()._do_playblast(
                        shot_config.paths,
                        shot_config.tail,
                    )


# class MPrevisPlayblaster(MPlayblaster):
#     def __init__(self) -> None:
#         super().__init__()

#     def playblast(self) -> None:
#         with _applied_hud(*self.HUDS), _unselect_all():
#             date = datetime.now().strftime("%m-%d-%y")
#             shots: list[str] = mc.sequenceManager(listShots=True)  # type: ignore[assignment]

#             # playblast individual shots
#             for shot_name in shots:
#                 camera: str = mc.shot(shot_name, query=True, currentCamera=True)  # type: ignore[assignment]
#                 cut_in = int(mc.shot(shot_name, query=True, startTime=True))
#                 cut_out = int(mc.shot(shot_name, query=True, endTime=True))
#                 cut_duration = int(mc.shot(shot_name, query=True, clipDuration=True))

#                 shot_data = MPlayblaster.dummy_shot(
#                     shot_name, cut_in, cut_out, cut_duration
#                 )

#                 with self(shot_data, camera):
#                     super()._do_playblast(
#                         [get_edit_path() / "previs" / date / f"{shot_name}_{date}.mov"],
#                         tail=5,
#                     )

#             # playblast sequence
#             sequencer = mc.sequenceManager(query=True, writableSequencer=True)
#             seq_in = mc.getAttr(f"{sequencer}.minFrame")
#             seq_out = mc.getAttr(f"{sequencer}.maxFrame")
#             shot_data = MPlayblaster.dummy_shot(
#                 "sequence", seq_in, seq_out, seq_out - seq_in
#             )

#             with self(shot_data, None):
#                 filename = Path(mc.file(query=True, sceneName=True))  # type: ignore[arg-type]
#                 super()._do_playblast(
#                     [
#                         get_edit_path()
#                         / "previs"
#                         / date
#                         / f"{filename.stem}_{date}.mov",
#                         filename.parent / f"{filename.stem}_{date}.mov",
#                     ],
#                 )


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
        mc.headsUpDisplay(
            chud.name,
            block=mc.headsUpDisplay(nextFreeBlock=chud.section),  # type: ignore[arg-type]
            blockSize=chud.blockSize,
            command=chud.command,
            event=chud.event,
            label=chud.label,
            labelFontSize=chud.labelFontSize,
            section=chud.section,
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
