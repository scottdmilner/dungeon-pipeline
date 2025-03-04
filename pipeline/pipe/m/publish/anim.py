from __future__ import annotations

import json
import logging
import os

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from pxr import Sdf
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Generator
    from pipe.struct.db import Shot

import maya.cmds as mc
import tractor.api.author as author  # type: ignore[import-not-found]

from pipe.glui.dialogs import MessageDialog
from pipe.m.util import maintain_selection
from pipe.struct.timeline import Timeline
from software.houdini import HoudiniDCC
from shared.util import get_pipe_path, get_production_path

from .publisher import Publisher
from .usdchaser import ChaserMode, ExportChaser

log = logging.getLogger(__name__)

CACHE_SET = "cache_SET"
PROP_SET = "prop_SET"


class AnimPublisher(Publisher):
    _shot: Shot
    _timeline: Timeline
    _init_success: bool

    def __init__(self, headless: bool = False):
        super().__init__(use_sg_entity=False, headless=headless)
        try:
            shot_code = mc.fileInfo("code", query=True)[0]
            self._init_success = True
        except IndexError:
            mc.error("Could not find shot code in fileInfo! Cannot export shot.")
            if not self._is_headless:
                error = MessageDialog(
                    self._window,
                    "Error: could not detect shot code. Please reach out to Scott",
                )
                error.exec_()
            self._init_success = False

        self._shot = self._conn.get_shot_by_code(shot_code)
        self._timeline = Timeline.from_shot(self._shot, preroll_duration=55)

    def _set_origin_keyframes(self) -> None:
        with maintain_current_time():
            keyframed = [
                o
                for o in mc.ls(dagObjects=True, type="transform")
                if mc.keyframe(o, query=True)
            ]
            mc.currentTime(self._timeline.preroll + 4)
            mc.setKeyframe(*keyframed, insert=True)
            mc.currentTime(self._timeline.preroll)
            mc.xform(
                *keyframed,
                matrix=(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),  # type: ignore[arg-type]
            )
            mc.setKeyframe(*keyframed)

    def _prepublish(self) -> bool:
        if not self._init_success:
            return False

        self._set_origin_keyframes()

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
        prop_sets = mc.ls("::" + PROP_SET, sets=True)
        props = dict()
        with maintain_selection():
            for s in prop_sets:
                mc.select(s)
                namespace = s.split(":")[0]
                props[namespace] = [n.split(":")[1] for n in mc.ls(selection=True)]

        return {
            "chaser": [ExportChaser.ID],
            "chaserArgs": [
                (ExportChaser.ID, "mode", ChaserMode.ANIM),
                (ExportChaser.ID, "props", json.dumps(props)),
                (ExportChaser.ID, "timeline", self._timeline.to_json()),
            ],
            "exportColorSets": False,
            "exportComponentTags": False,
            "exportUVs": False,
            "frameRange": (
                self._timeline.preroll,
                self._timeline.tail,
            ),
            "frameStride": 1.0 / self._shot.substeps,
            "shadingMode": "none",
            "stripNamespaces": False,
        }

    def _get_confirm_message(self):
        return f"Animation has been exported to {self._publish_path}"

    def _postpublish(self) -> None:
        """Launch a Houdini process to compute the anim post-process HDA"""
        post_anim_script = ";".join(
            [
                "from pipe.h.animpostprocess import AnimPostProcessor",
                f"AnimPostProcessor().run('{self._shot.code}')",
                "exit()",
            ]
        )
        HoudiniDCC(is_python_shell=True, extra_args=["-c", post_anim_script]).launch()

        root_layer = Sdf.Layer.FindOrOpen(str(self._publish_path))
        root_layer.subLayerPaths.append("post-process.usd")
        root_layer.Save()

        # send CFX to farm
        job = author.Job()
        job.title = (
            f"CFX {self._shot.code} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        job.envkey = [
            generate_tractor_setenv(
                [
                    "OCIO",
                    "PATH",
                    "PIXAR_LICENSE_FILE",
                    "PXR_AR_DEFAULT_SEARCH_PATH",
                    "PXR_PLUGINPATH_NAME",
                    "RMANTREE",
                ]
            )
        ]
        job.priority = 90
        task = author.Task(title="cache")
        task.addCommand(
            author.Command(
                argv=[
                    "python",
                    str(get_pipe_path()),
                    "-l",
                    "DEBUG",
                    "-p",
                    "houdini",
                    "-c",
                    (
                        "from pipe.h.animpostprocess import CfxPostProcessor;"
                        f"CfxPostProcessor().run('{self._shot.code}');"
                        "exit()"
                    ),
                ],
                retryrc=[-11, 3, 139],
                service="EL9",
            )
        )
        job.addChild(task)
        job.spool(block=True)
        author.closeEngineClient()


def generate_tractor_setenv(parms: list[str]) -> str:
    return " ".join(
        ["setenv"]
        + [f"{var}={os.getenv(var)}" for var in parms if var]
        + ["HOUDINI_LICENSE_SERVER=animlic.cs.byu.edu"]
    )


@contextmanager
def maintain_current_time() -> Generator[int, None, None]:
    ctime = mc.currentTime(query=True)
    try:
        yield ctime
    finally:
        mc.currentTime(ctime)
