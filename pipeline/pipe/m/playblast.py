from __future__ import annotations

import maya.cmds as mc

from contextlib import contextmanager
from typing import TYPE_CHECKING

from mayacapture.capture import capture  # type: ignore[import-not-found]
from pipe.db import DB
from pipe.util import Playblaster
from shared.util import get_edit_path

from env_sg import DB_Config

if TYPE_CHECKING:
    from pipe.struct.db import Shot
    from typing import Generator


class MPlayblaster(Playblaster):
    _conn: DB
    _shot: Shot
    _camera: str

    def __init__(self) -> None:
        super().__init__(DB.Get(DB_Config), mc.fileInfo("code", query=True)[0])
        self._camera = "|__mayaUsd__|shotCamParent|shotCam"

    def _write_images(self, path: str) -> None:
        huds = [
            "HUDCameraNames",
            "HUDCurrentFrame",
            "HUDFocalLength",
        ]
        with _applied_hud(huds), _unselect_all():
            capture(
                camera=self._camera,
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
                raw_frame_numbers=True,
                viewer=0,
            )

    def playblast(self) -> None:
        super()._do_playblast(
            [
                get_edit_path()
                / "anim"
                / self._shot.code
                / (self._shot.code + "_V002.mov")
            ]
        )


@contextmanager
def _applied_hud(huds) -> Generator[None, None, None]:
    # hide current huds and store current state
    orig_visibility: dict[str, bool] = {}
    orig_huds: list[str] = mc.headsUpDisplay(query=True, listHeadsUpDisplays=True) # type: ignore[assignment]
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
    selection = mc.ls(selection=True, long=True)
    mc.select(clear=True)

    try:
        yield
    finally:
        mc.select(*selection, replace=True)
