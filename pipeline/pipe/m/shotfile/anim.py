import logging
import maya.cmds as mc

from pathlib import Path
from pxr import Usd, UsdGeom

from shared.util import get_production_path

from .shotfile_manager import MShotFileManager

log = logging.getLogger(__name__)


class MAnimShotFileManager(MShotFileManager):
    @classmethod
    def run_on_open(cls):
        super().run_on_open()

        # Duplicate the USD camera into a temp Maya camera
        CAM_NAME = "shotCam"
        try:
            mc.mayaUsdDiscardEdits(CAM_NAME)
        finally:
            camera_prim = next(
                prim
                for prim in cls.get_stage().Traverse(Usd.PrimIsDefined)
                if prim.IsA(UsdGeom.Camera) and prim.GetName() == CAM_NAME
            )
            mc.mayaUsdEditAsMaya(
                cls.get_stage_shape() + "," + str(camera_prim.GetPrimPath())
            )
            camera_shape = mc.listRelatives(CAM_NAME, fullPath=True, shapes=True)[0]
            mc.lookThru(CAM_NAME)
            mc.camera(camera_shape, edit=True, lockTransform=True)

    def _get_subpath(self) -> str:
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
