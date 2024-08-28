from __future__ import annotations

import logging
import mayaUsd  # type: ignore[import-not-found]
import maya.cmds as mc

from abc import abstractmethod
from pathlib import Path
from pxr import Sdf, Usd, UsdGeom
from timeline_marker.ui import TimelineMarker  # type: ignore[import-not-found]
from typing import cast

from pipe.db import DB
from pipe.glui.dialogs import MessageDialogCustomButtons
from pipe.m.local import get_main_qt_window
from pipe.struct.db import SGEntity, Shot
from pipe.util import FileManager
from shared.util import get_production_path

from env_sg import DB_Config

log = logging.getLogger(__name__)


def timeline_generator(
    pre_roll: list[tuple[str, tuple[int, int, int], int]],
    roll: list[tuple[str, tuple[int, int, int], int]],
    /,
    start_frame: int = 1001,
) -> tuple[list[int], list[tuple[int, int, int]], list[str]]:
    colors = []
    comments = []
    pre_duration = 0
    post_duration = 0

    for comment, color, duration in pre_roll:
        comments += [comment] * duration
        colors += [color] * duration
        pre_duration += duration
    for comment, color, duration in roll:
        comments += [comment] * duration
        colors += [color] * duration
        post_duration += duration

    frames = list(range(start_frame - pre_duration, start_frame + post_duration))
    return frames, colors, comments


def shot_timeline_generator(
    shot_duration: int,
) -> tuple[list[int], list[tuple[int, int, int]], list[str]]:
    return timeline_generator(
        [
            ("Rest Pose @Origin", (70, 0, 0), 15),
            ("Rest Pose -> Windup", (150, 0, 0), 15),
            ("Hold Windup", (255, 0, 0), 10),
            ("Windup", (128, 128, 0), 15),
            ("Head", (128, 255, 128), 5),
        ],
        [
            ("Animate!", (0, 255, 0), shot_duration),
            ("Tail", (100, 160, 255), 5),
        ],
        start_frame=1001,
    )


class MShotFileManager(FileManager):
    def __init__(self) -> None:
        conn = DB.Get(DB_Config)
        window = get_main_qt_window()
        super().__init__(conn, Shot, window)

    @staticmethod
    def _check_unsaved_changes() -> bool:
        if mc.file(query=True, modified=True):
            warning_response = mc.confirmDialog(
                title="Do you want to save?",
                message="The current file has not been saved. Continue anyways?",
                button=["Continue", "Cancel"],
                defaultButton="Cancel",
                cancelButton="Cancel",
                dismissString="Cancel",
            )
            if warning_response == "Cancel":
                return False
        return True

    @staticmethod
    def _generate_filename(entity) -> str:
        shot = cast(Shot, entity)
        return shot.code + ".mb"

    @staticmethod
    def _open_file(path: Path) -> None:
        mc.file(str(path), open=True, force=True)

    def _import_camera(self, shot: Shot, stage: Usd.Stage) -> None:
        assert shot.path is not None
        root_layer = stage.GetRootLayer()

        cam_layer = Sdf.Layer.CreateAnonymous(tag="Camera")
        root_layer.subLayerPaths.append(cam_layer.identifier)
        cam_file_layer = Sdf.Layer.FindOrOpenRelativeToLayer(
            root_layer, "/".join((shot.path, "cam", "cam.usd"))
        )
        cam_layer.subLayerPaths.append(cam_file_layer.identifier)
        # Fix Camera Scale
        stage.SetEditTarget(Usd.EditTarget(cam_layer))
        cam_prim = stage.GetPrimAtPath(Sdf.Path("/LnD_shotCam"))
        cam_xformable = UsdGeom.Xformable(cam_prim)
        cam_xformable.AddScaleOp().Set((0.01, 0.01, 0.01))

    def _import_env(self, shot: Shot, stage: Usd.Stage) -> None:
        assert shot.path is not None
        root_layer = stage.GetRootLayer()

        env_layer = Sdf.Layer.CreateAnonymous(tag="Environment")
        root_layer.subLayerPaths.append(env_layer.identifier)
        env_stub = shot.set or self._conn.get_sequence_by_stub(shot.sequence).set
        if env_stub and (env := self._conn.get_env_by_stub(env_stub)) and env.path:
            env_file_layer = Sdf.Layer.FindOrOpenRelativeToLayer(
                root_layer, "/".join((env.path, "main.usd"))
            )
            env_layer.subLayerPaths.append(env_file_layer.identifier)
        # Set up shot-level overrides
        env_override_layer = Sdf.Layer.CreateNew(
            str(get_production_path() / shot.path / "set" / "maya_override.usd")
        )
        env_override_layer.Save()
        env_layer.subLayerPaths.insert(0, env_override_layer.identifier)
        stage.SetEditTarget(Usd.EditTarget(env_override_layer))

    @abstractmethod
    def _setup_scene(self, shot: Shot, stage: Usd.Stage) -> None:
        pass

    def _setup_file(self, path: Path, entity) -> None:
        mc.file(rename=str(path))

        shot = cast(Shot, entity)

        # Create USD Stage
        transform = mc.createNode("transform", name="stage_transform")
        mc.scale(100, 100, 100, transform, absolute=True)
        mc.createNode("mayaUsdProxyShape", name="stage", parent=transform)
        stage_node = mc.ls(selection=True, long=True)[0]
        mc.connectAttr("time1.outTime", f"{stage_node}.time")

        rel_root_path = (
            Path("../" * (len(path.relative_to(get_production_path()).parents) - 1))
            / "root.usda"
        )
        mc.setAttr(f"{stage_node}.filePath", str(rel_root_path), type="string")

        # Set up stage
        self._setup_scene(shot, mayaUsd.ufe.getStage(stage_node))

        # Import Timeline
        frames, colors, comments = shot_timeline_generator(shot.cut_duration)
        TimelineMarker.set(frames, colors, comments)
        mc.playbackOptions(
            animationStartTime=frames[0],
            animationEndTime=frames[-1],
            minTime=frames[0],
            maxTime=frames[-1],
        )

        # Save USD Edits to the scene file and don't prompt about it
        mc.optionVar(intValue=("mayaUsd_SerializedUsdEditsLocationPrompt", 0))
        mc.optionVar(intValue=("mayaUsd_SerializedUsdEditsLocation", 2))
        mc.file(save=True)


class MAnimShotFileManager(MShotFileManager):
    @staticmethod
    def _get_subpath() -> str:
        return "anim"

    def _setup_scene(self, shot: Shot, stage: Usd.Stage) -> None:
        self._import_camera(shot, stage)
        self._import_env(shot, stage)

        # Import Rigs
        # TODO

    def _setup_file(self, path: Path, entity) -> None:
        mc.file(newFile=True, force=True)
        super()._setup_file(path, entity)


class MRLOShotFileManager(MShotFileManager):
    @staticmethod
    def _check_unsaved_changes() -> bool:
        return True

    @staticmethod
    def _get_subpath() -> str:
        return "rlo"

    def _setup_scene(self, shot: Shot, stage: Usd.Stage) -> None:
        self._import_env(shot, stage)

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        if not path.exists():
            prompt_create = MessageDialogCustomButtons(
                self._main_window,
                f"The RLO file for shot {entity.code} does not exist. Continue "
                "to save a copy of the current file as the RLO file?",
                has_cancel_button=True,
                ok_name="Continue",
                cancel_name="Cancel",
            )
            if not bool(prompt_create.exec_()):
                return
        super()._setup_file(path, entity)
