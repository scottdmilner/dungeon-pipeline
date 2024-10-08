from __future__ import annotations

import maya.cmds as mc

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from mayacapture.capture import capture  # type: ignore[import-not-found]
from pipe.db import DB
from pipe.struct.db import Shot
from pipe.util import Playblaster
from shared.util import get_edit_path

from env_sg import DB_Config

if TYPE_CHECKING:
    from typing import Any, Generator


class MPlayblaster(Playblaster):
    HUDS = [
        "HUDCameraNames",
        "HUDCurrentFrame",
        "HUDFocalLength",
        "LnDfilename",
    ]
    _camera: str | None

    def __init__(self) -> None:
        super().__init__(DB.Get(DB_Config))
        huds_to_create: dict[str, dict[str, Any]] = {
            "LnDfilename": {
                "block": mc.headsUpDisplay(nextFreeBlock=5),
                "blockSize": "small",
                "command": lambda: mc.file(query=True, sceneName=True),
                "event": "SceneSaved",
                "label": "File:",
                "labelFontSize": "small",
                "section": 5,
            },
        }

        # check if these huds exist in the file and create them if not
        huds: list[str] = mc.headsUpDisplay(query=True, listHeadsUpDisplays=True)  # type: ignore[assignment]
        for name, kwargs in huds_to_create.items():
            if name not in huds:
                mc.headsUpDisplay(name, **kwargs)

    def __call__(self, shot: Shot, camera: str | None, *args):  # type: ignore[override]
        super().__call__(shot)
        self._camera = camera
        return self

    def _write_images(self, path: str) -> None:
        """Maya implementation of playblasting image frames"""
        kwargs: dict[str, Any] = dict()
        if self._camera:
            kwargs["camera"] = self._camera
        else:
            kwargs["use_camera_sequencer"] = True
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
            **kwargs,
        )

    @staticmethod
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


class MPrevisPlayblaster(MPlayblaster):
    def __init__(self) -> None:
        super().__init__()

    def playblast(self) -> None:
        date = datetime.now().strftime("%m-%d-%y")
        shots: list[str] = mc.sequenceManager(listShots=True)  # type: ignore[assignment]

        # playblast individual shots
        for shot_name in shots:
            camera: str = mc.shot(shot_name, query=True, currentCamera=True)  # type: ignore[assignment]
            cut_in = int(mc.shot(shot_name, query=True, startTime=True))
            cut_out = int(mc.shot(shot_name, query=True, endTime=True))
            cut_duration = int(mc.shot(shot_name, query=True, clipDuration=True))

            shot_data = MPlayblaster.dummy_shot(
                shot_name, cut_in, cut_out, cut_duration
            )

            with _applied_hud(self.HUDS), _unselect_all(), self(shot_data, camera):
                super()._do_playblast(
                    [get_edit_path() / "previs" / date / f"{shot_name}_{date}.mov"],
                    tail=5,
                )

        # playblast sequence
        sequencer = mc.sequenceManager(query=True, writableSequencer=True)
        seq_in = mc.getAttr(f"{sequencer}.minFrame")
        seq_out = mc.getAttr(f"{sequencer}.maxFrame")
        shot_data = MPlayblaster.dummy_shot(
            "sequence", seq_in, seq_out, seq_out - seq_in
        )

        with self(shot_data, None):
            filename = Path(mc.file(query=True, sceneName=True))  # type: ignore[arg-type]
            super()._do_playblast(
                [
                    get_edit_path() / "previs" / date / f"{filename.stem}_{date}.mov",
                    filename.parent / f"{filename.stem}_{date}.mov",
                ],
            )


class MAnimPlayblaster(MPlayblaster):
    _code: str

    def __init__(self) -> None:
        self._code = mc.fileInfo("code", query=True)[0]
        super().__init__()

    def playblast(self) -> None:
        with _applied_hud(self.HUDS), _unselect_all(), self(
            self._conn.get_shot_by_code(self._code),
            "|__mayaUsd__|shotCamParent|shotCam",
        ):
            super()._do_playblast(
                [
                    get_edit_path()
                    / "testing"
                    / self._shot.code
                    / (self._shot.code + "_V002.mov")
                ],
                tail=5,
            )


@contextmanager
def _applied_hud(huds) -> Generator[None, None, None]:
    # hide current huds and store current state
    orig_visibility: dict[str, bool] = {}
    orig_huds: list[str] = mc.headsUpDisplay(query=True, listHeadsUpDisplays=True)  # type: ignore[assignment]
    for hud in orig_huds:
        vis = bool(mc.headsUpDisplay(hud, query=True, visible=True))
        orig_visibility[hud] = vis
        if vis:
            mc.headsUpDisplay(hud, edit=True, visible=False)

    # display requested huds
    for hud in huds:
        mc.headsUpDisplay(hud, edit=True, visible=True)

    try:
        yield
    finally:
        # restore original visibility
        for hud, state in orig_visibility.items():
            mc.headsUpDisplay(hud, edit=True, visible=state)


@contextmanager
def _unselect_all() -> Generator[None, None, None]:
    selection = mc.ls(selection=True, long=True, ufeObjects=True, absoluteName=True)
    mc.select(clear=True)

    try:
        yield
    finally:
        mc.select(*selection, replace=True)
