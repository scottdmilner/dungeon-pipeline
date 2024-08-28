from __future__ import annotations

import attrs
import logging
import numpy as np
import mayaUsd.lib as mayaUsdLib  # type: ignore[import-not-found]
from functools import wraps

from enum import IntEnum
from pxr import Sdf, Usd, UsdGeom, UsdShade, Vt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing

log = logging.getLogger(__name__)


def _log_errors(fun):
    """Errors in the chaser don't make it out to the console by default"""

    @wraps(fun)
    def wrap(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except Exception as e:
            log.error(e, exc_info=True)
            raise

    return wrap


class ChaserMode(IntEnum):
    RIG = 1
    CAM = 2


@attrs.define
class ChaserArgs:
    mode: ChaserMode = attrs.field(converter=int)


class ExportChaser(mayaUsdLib.ExportChaser):
    ID: str = "lnd"

    _chaser_args: ChaserArgs
    _dag_to_usd: mayaUsdLib.DagToUsdMap
    _stage: Usd.Stage

    def __init__(self, factoryContext, *args, **kwargs) -> None:
        super(ExportChaser, self).__init__(factoryContext, *args, **kwargs)

        self._dag_to_usd = factoryContext.GetDagToUsdMap()
        self._stage = factoryContext.GetStage()
        self.job_args = factoryContext.GetJobArgs()
        self._chaser_args = ChaserArgs(**self.job_args.allChaserArgs["lnd"])

    def scale_down_geo(self, scale_factor: float = 0.01) -> None:
        root_prim = self._stage.GetPseudoRoot()

        for prim in (it := iter(Usd.PrimRange(root_prim))):
            if not prim.IsA(UsdGeom.Mesh):
                continue
            # don't recurse deeper than this
            it.PruneChildren()

            for attr_name in ["points", "extent"]:
                attr = prim.GetAttribute(attr_name)
                if not attr.IsValid():
                    continue

                frames: typing.Iterable[Usd.TimeCode]
                if attr.ValueMightBeTimeVarying():
                    frames = (Usd.TimeCode(f) for f in attr.GetTimeSamples())
                else:
                    frames = (Usd.TimeCode.Default(),)

                for frame in frames:
                    data = np.array(attr.Get(frame))
                    data *= scale_factor
                    attr.Set(Vt.Vec3fArray.FromNumpy(data), frame)  # type: ignore[arg-type]

            for attr_name in ["xformOp:translate:pivot"]:
                attr = prim.GetAttribute(attr_name)
                if not attr.IsValid():
                    continue
                data = attr.Get()
                data *= scale_factor
                attr.Set(data)

        UsdGeom.SetStageMetersPerUnit(self._stage, 1.0)

    def update_material_bindings(self) -> None:
        """Update material bindings to what Houdini will expect"""

        bindings = UsdShade.MaterialBindingAPI(
            self._stage.GetPrimAtPath(Sdf.Path("/CHAR/MODEL"))
        )
        for rel in bindings.GetCollectionBindingRels():
            t1, t2 = rel.GetTargets()
            # strip the namespace because the USD exporter strips the geo namespace but not the material namespace
            new_name = t2.name.split("_", 1)[1]
            # Change the material binding to match how it will look in Houdini
            rel.SetTargets(
                (
                    t1,
                    Sdf.Path(
                        str(t2.GetParentPath()).replace("/CHAR", "/CHAR/MODEL")
                        + "/MAT_"
                        + new_name
                    ),
                )
            )

    @_log_errors
    def PostExport(self) -> bool:
        if self._chaser_args.mode == ChaserMode.RIG:
            self.scale_down_geo()
            self.update_material_bindings()
        elif self._chaser_args.mode == ChaserMode.CAM:
            # TODO: will work in Usd v24
            # editor = Usd.NamespaceEditor(self._stage)
            # editor.MovePrimAtPath(Sdf.Path("/WORLD/CAM/LnD_shotCam"), Sdf.Path("/"))
            # editor.ApplyEdits()

            with Sdf.ChangeBlock():
                edit = Sdf.BatchNamespaceEdit()
                edit.Add(
                    Sdf.NamespaceEdit.Reparent(
                        Sdf.Path("/WORLD/CAM/LnD_shotCam"), Sdf.Path("/"), -1
                    )
                )
                edit.Add(Sdf.NamespaceEdit.Remove(Sdf.Path("/WORLD")))
                self._stage.GetEditTarget().GetLayer().Apply(edit)

            self._stage.SetDefaultPrim(
                self._stage.GetPrimAtPath(Sdf.Path("/LnD_shotCam"))
            )
        else:
            raise ValueError(
                f"{self._chaser_args.mode} is not a valid LnD chaser mode."
            )

        return True
