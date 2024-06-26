import logging
import numpy as np
from pathlib import Path
from pxr import Usd, UsdGeom, Vt
from typing import Dict, Iterable, Optional, Union
from PySide2.QtWidgets import QWidget

import maya.cmds as mc

import pipe
from pipe.db import DB
from env import SG_Config

log = logging.getLogger(__name__)


class RiggedExporter:
    EXPORT_SETS: Dict[str, str] = {
        "rayden": "Rayden:cache_SET",
        "robin": "Robin:cache_SET",
    }

    _conn: DB
    _path: str
    window: Optional[QWidget]

    def __init__(self) -> None:
        self._conn = DB(SG_Config)
        self.window = pipe.m.local.get_main_qt_window()

    @staticmethod
    def convert_to_houdini_scale(path: str) -> None:
        """Scale everything in the file by 0.01 to convert from Maya (cm) to
        to Houdini (m) units"""
        stage = Usd.Stage.Open(path)
        root_prim = stage.GetPseudoRoot()

        for prim in (it := iter(Usd.PrimRange(root_prim))):
            if not prim.IsA(UsdGeom.Mesh):
                continue
            # don't recurse deeper than this
            it.PruneChildren()

            for attr_name in ["points", "extent"]:
                attr = prim.GetAttribute(attr_name)
                if not attr.IsValid():
                    continue

                frames: Iterable[Usd.TimeCode]
                if attr.ValueMightBeTimeVarying():
                    frames = (Usd.TimeCode(f) for f in attr.GetTimeSamples())
                else:
                    frames = (Usd.TimeCode.Default(),)

                for frame in frames:
                    data = np.array(attr.Get(frame))
                    data *= 0.01
                    attr.Set(Vt.Vec3fArray.FromNumpy(data), frame)  # type: ignore[arg-type]

            for attr_name in ["xformOp:translate:pivot"]:
                attr = prim.GetAttribute(attr_name)
                if not attr.IsValid():
                    continue
                data = attr.Get()
                data *= 0.01
                attr.Set(data)

        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        stage.Save()

    def publish_char(
        self, char: str, anim: bool = False, path: Optional[Union[Path, str]] = None
    ) -> None:
        if not path:
            if user_select := mc.fileDialog2(fileFilter="*.usd"):
                path = user_select[0]
            else:
                return

        kwargs = {
            "file": str(path),
            "pythonPostCallback": f"{type(self).__name__}.{self.convert_to_houdini_scale.__name__}('{str(path)}')",
            "selection": True,
            "shadingMode": "none",
            "stripNamespaces": True,
        }

        if anim:
            kwargs.update(
                {
                    "exportColorSets": False,
                    "exportUVs": False,
                    "frameRange": [1, 20],
                    "frameStride": 1.0,
                }
            )
        mc.select(self.EXPORT_SETS[char])
        mc.mayaUSDExport(**kwargs)  # type: ignore[attr-defined]
