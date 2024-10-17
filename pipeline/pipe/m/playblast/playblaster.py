from __future__ import annotations

import copy
import logging
import maya.cmds as mc

from contextlib import contextmanager
from typing import TYPE_CHECKING

from mayacapture.capture import capture  # type: ignore[import-not-found]
from pipe.util import Playblaster

from .struct import HudDefinition, MPlayblastConfig

if TYPE_CHECKING:
    from typing import Any, Generator

log = logging.getLogger(__name__)


class MPlayblaster(Playblaster):
    _config: MPlayblastConfig
    _extra_kwargs: dict[str, Any]

    def __init__(self) -> None:
        super().__init__()

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
        with applied_hud(
            self._config.builtin_huds, self._config.custom_huds
        ), unselect_all():
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
                # assemble shot-specific kwargs
                self._extra_kwargs = copy.deepcopy(global_kwargs)
                if shot_config.use_sequencer:
                    self._extra_kwargs["use_camera_sequencer"] = True
                else:
                    self._extra_kwargs["camera"] = shot_config.camera

                with self(shot_config.shot):
                    super()._do_playblast(
                        shot_config.paths,
                        shot_config.tails,
                    )


@contextmanager
def applied_hud(
    builtin_huds: list[str], custom_huds: list[HudDefinition]
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
def unselect_all() -> Generator[None, None, None]:
    selection = mc.ls(selection=True, long=True, ufeObjects=True, absoluteName=True)
    mc.select(clear=True)

    try:
        yield
    finally:
        mc.select(*selection, replace=True)
