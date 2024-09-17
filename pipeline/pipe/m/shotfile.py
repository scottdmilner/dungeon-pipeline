from __future__ import annotations

import logging
import mayaUsd  # type: ignore[import-not-found]
import maya.api.OpenMaya as om
import maya.cmds as mc

from abc import abstractmethod
from functools import cached_property
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
    MAYA_OVERRIDE = "maya_override.usd"
    shot: Shot

    def __init__(self) -> None:
        conn = DB.Get(DB_Config)
        window = get_main_qt_window()
        super().__init__(conn, Shot, window)

    @cached_property
    def stage_shape(self) -> str:
        if ss := mc.ls(type="mayaUsdProxyShape", long=True)[0]:
            return ss
        raise RuntimeError("No USD stage found in scene")

    @cached_property
    def stage(self) -> Usd.Stage:
        return mayaUsd.ufe.getStage(self.stage_shape)

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

    def _post_open_file(self, entity: SGEntity) -> None:
        self.shot = cast(Shot, entity)
        STAGE_SHAPE = "stage_shape"

        def saveEditTargetLayer(clientData: dict[str, str]) -> None:
            stage: Usd.Stage = mayaUsd.ufe.getStage(clientData[STAGE_SHAPE])
            stage.GetEditTarget().GetLayer().Save()

        om.MSceneMessage.addCallback(
            om.MSceneMessage.kBeforeSave,
            saveEditTargetLayer,
            {
                STAGE_SHAPE: self.stage_shape,
            },
        )

        mc.mayaUsdEditTarget(  # type: ignore[attr-defined]
            self.stage_shape,
            edit=True,
            editTarget="/".join(
                ["shot", self.shot.code, "set", MShotFileManager.MAYA_OVERRIDE]
            ),
        )

    def _import_camera(self) -> None:
        assert self.shot.path is not None
        root_layer = self.stage.GetRootLayer()

        # mc.mayaUsdLayerEditor(cam_layer.identifier, edit=True, lockLayer=(2, 0, stageShape))

        cam_file_layer = Sdf.Layer.FindOrOpenRelativeToLayer(
            root_layer, "/".join((self.shot.path, "cam", "cam.usd"))
        )
        if not cam_file_layer:
            mc.warning("No exported camera found")
            return

        root_layer.subLayerPaths.append(cam_file_layer.identifier)

    def _import_env(self) -> None:
        assert self.shot.path is not None
        root_layer = self.stage.GetRootLayer()
        # locked_layers: list[str] = []

        # Set up shot-level overrides
        Sdf.Layer.CreateNew(
            str(
                get_production_path()
                / self.shot.path
                / "set"
                / MShotFileManager.MAYA_OVERRIDE
            )
        ).Save()
        env_override_layer = Sdf.Layer.FindOrOpenRelativeToLayer(
            root_layer,
            "/".join((self.shot.path, "set", MShotFileManager.MAYA_OVERRIDE)),
        )
        root_layer.subLayerPaths.append(env_override_layer.identifier)
        # Fix env scale
        env_prim = self.stage.OverridePrim(Sdf.Path("/environment"))
        env_xformable = UsdGeom.Xformable(env_prim)
        env_xformable.AddScaleOp().Set((100, 100, 100))

        self.stage.SetEditTarget(Usd.EditTarget(env_override_layer))

        env_stub = (
            self.shot.set or self._conn.get_sequence_by_stub(self.shot.sequence).set
        )
        if env_stub and (env := self._conn.get_env_by_stub(env_stub)) and env.path:
            env_file_layer = Sdf.Layer.FindOrOpenRelativeToLayer(
                root_layer, "/".join((env.path, "main.usd"))
            )
            root_layer.subLayerPaths.append(env_file_layer.identifier)
            # locked_layers.append(env_file_layer.identifier)
            env_file_layer.SetPermissionToSave(False)

        # for id in locked_layers:
        #     mc.mayaUsdLayerEditor(id, edit=True, lockLayer=(2, 0, stageShape))

    @abstractmethod
    def _setup_scene(self) -> None:
        pass

    def _setup_file(self, path: Path, entity) -> None:
        mc.file(rename=str(path))

        self.shot = cast(Shot, entity)
        assert self.shot.path is not None

        # Create USD Stage
        transform = mc.createNode("transform", name="stage_transform")
        mc.createNode("mayaUsdProxyShape", name="stage", parent=transform)
        self.stage_shape = mc.ls(selection=True, long=True)[0]
        mc.connectAttr("time1.outTime", f"{self.stage_shape}.time")

        ROOT_LAYER = "maya_root.usd"
        root_layer_path = str(get_production_path() / self.shot.path / ROOT_LAYER)
        root_layer = Sdf.Layer.FindOrOpen(root_layer_path) or Sdf.Layer.CreateNew(
            root_layer_path
        )
        mc.setAttr(f"{self.stage_shape}.filePath", "../" + ROOT_LAYER, type="string")

        # mc.mayaUsdLayerEditor(str(get_production_path() / "root.usda"), edit=True, lockLayer=(2, 0, stage_shape))

        # Set up stage
        self._setup_scene()
        root_layer.Save()
        root_layer.SetPermissionToSave(False)

        # Import Timeline
        frames, colors, comments = shot_timeline_generator(self.shot.cut_duration)
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

        # Save shot code to file
        mc.fileInfo("code", self.shot.code)
        mc.file(save=True)


class MAnimShotFileManager(MShotFileManager):
    @staticmethod
    def _get_subpath() -> str:
        return "anim"

    def _setup_scene(self) -> None:
        self._import_camera()
        self._import_env()

        # Import Rigs
        for asset_stub in self.shot.assets:
            asset = self._conn.get_asset_by_stub(asset_stub)
            if not asset.path:
                continue
            rig_path = "/".join(("production", asset.path, "rig", "rig.mb"))
            if (get_production_path() / ".." / rig_path).exists():
                mc.file(rig_path, reference=True, namespace=asset.name)
            else:
                print(f'Unable to find rig for asset "{asset.disp_name}"')

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

    def _setup_scene(self) -> None:
        self._import_env()

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
