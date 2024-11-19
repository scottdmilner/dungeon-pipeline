from __future__ import annotations

import logging
import mayaUsd  # type: ignore[import-not-found]
import maya.api.OpenMaya as om
import maya.cmds as mc

from abc import abstractmethod
from pathlib import Path
from pxr import Sdf, Usd, UsdGeom
from timeline_marker.ui import TimelineMarker  # type: ignore[import-not-found]
from typing import cast

from pipe.db import DB
from pipe.m.local import get_main_qt_window
from pipe.struct.db import SGEntity, Shot
from pipe.util import FileManager, log_errors
from shared.util import get_production_path

from env_sg import DB_Config

from .timeline import shot_timeline_generator

log = logging.getLogger(__name__)


class MShotFileManager(FileManager):
    MAYA_OVERRIDE = "maya_override.usd"
    shot: Shot

    def __init__(self, **kwargs) -> None:
        conn = DB.Get(DB_Config)
        window = get_main_qt_window()
        super().__init__(conn, Shot, window, versioning=True, **kwargs)

    @classmethod
    def get_stage_shape(cls) -> str:
        if ss := mc.ls(type="mayaUsdProxyShape", long=True)[0]:
            return ss
        raise RuntimeError("No USD stage found in scene")

    @classmethod
    def get_stage(cls) -> Usd.Stage:
        return mayaUsd.ufe.getStage(cls.get_stage_shape())

    @classmethod
    @log_errors
    def run_on_open(cls) -> None:
        """Function to run on file open via script node"""

        # save edit target layer on save
        beforeSaveId = om.MSceneMessage.addCallback(
            om.MSceneMessage.kBeforeSave,
            lambda _: MShotFileManager.get_stage().GetEditTarget().GetLayer().Save(),
        )

        # remove callback before opening a new file
        om.MSceneMessage.addCallback(
            om.MSceneMessage.kBeforeOpen,
            lambda kwargs: om.MSceneMessage.removeCallback(kwargs["ID"]),
            {"ID": beforeSaveId},
        )

        # change default render resolution
        mc.setAttr("defaultResolution.width", 1920)  # type: ignore[arg-type]
        mc.setAttr("defaultResolution.height", 816)  # type: ignore[arg-type]

        # set session USD target layer to the override layer
        try:
            shot_code = ""
            try:
                shot_code = mc.fileInfo("code", query=True)[0]
            except IndexError:
                mc.error(
                    "Could not find shot code in fileInfo! USD edit target not set"
                )
            if shot_code:
                mc.mayaUsdEditTarget(  # type: ignore[attr-defined]
                    cls.get_stage_shape(),
                    edit=True,
                    editTarget="/".join(["shot", shot_code, "set", cls.MAYA_OVERRIDE]),
                )
        except Exception:
            mc.error("Warning! Could not set edit target!")

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

    def _generate_filename_ext(self, entity) -> tuple[str, str]:
        shot = cast(Shot, entity)
        return shot.code, "mb"

    @staticmethod
    def _open_file(path: Path) -> None:
        mc.file(str(path), open=True, force=True)

    def _post_open_file(self, entity: SGEntity) -> None:
        """create `lndOnOpen` script node"""
        ON_OPEN_SCRIPT = "lndOnOpen"

        if mc.objExists(ON_OPEN_SCRIPT):
            return

        classname = self.__class__.__name__
        mc.scriptNode(
            beforeScript=(
                f"from pipe.m.shotfile import {classname}; {classname}.run_on_open()"
            ),
            name=ON_OPEN_SCRIPT,
            scriptType=1,
            sourceType="python",
        )
        # script node is created, will not run this session, so run manually
        self.run_on_open()

    def _import_camera(self) -> None:
        assert self.shot.path is not None
        root_layer = self.get_stage().GetRootLayer()

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
        stage = self.get_stage()
        root_layer = stage.GetRootLayer()
        # locked_layers: list[str] = []

        # Set up shot-level overrides
        env_override_layer = Sdf.Layer.FindOrOpenRelativeToLayer(
            root_layer,
            "/".join((self.shot.path, "set", MShotFileManager.MAYA_OVERRIDE)),
        ) or Sdf.Layer.CreateNew(
            str(
                get_production_path()
                / self.shot.path
                / "set"
                / MShotFileManager.MAYA_OVERRIDE
            )
        )
        env_override_layer.Save()
        root_layer.subLayerPaths.append(env_override_layer.identifier)
        # Fix env scale
        env_prim = stage.OverridePrim(Sdf.Path("/environment"))
        env_xformable = UsdGeom.Xformable(env_prim)
        env_xformable.AddScaleOp().Set((100, 100, 100))

        stage.SetEditTarget(Usd.EditTarget(env_override_layer))

        if not (env_stub := self.shot.set):
            if not self.shot.sequence:
                env_stub = None
            else:
                env_stub = self._conn.get_sequence_by_stub(self.shot.sequence).set

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
        stage_shape = self.get_stage_shape()
        mc.connectAttr("time1.outTime", f"{stage_shape}.time")

        ROOT_LAYER = "maya_root.usd"
        root_layer_path = str(get_production_path() / self.shot.path / ROOT_LAYER)
        root_layer = Sdf.Layer.FindOrOpen(root_layer_path) or Sdf.Layer.CreateNew(
            root_layer_path
        )
        root_layer.Save()
        mc.setAttr(f"{stage_shape}.filePath", "../" + ROOT_LAYER, type="string")

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
        mc.file(save=True, force=True)
