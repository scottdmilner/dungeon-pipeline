from __future__ import annotations

import attrs
import numpy as np
import mayaUsd.lib as mayaUsdLib  # type: ignore[import-not-found]

from enum import IntEnum
from pxr import Sdf, Usd, UsdGeom, UsdShade, Vt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable

from pipe.util import log_errors


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
        self._chaser_args = ChaserArgs(**self.job_args.allChaserArgs[self.ID])

    def scale_down_geo(self, scale_factor: float = 0.01) -> None:
        root_prim = self._stage.GetPseudoRoot()

        for prim in (it := iter(Usd.PrimRange(root_prim))):
            if not (prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.BasisCurves)):  # type: ignore[call-overload]
                continue
            # don't recurse deeper than this
            it.PruneChildren()

            for attr_token in (UsdGeom.Tokens.points, UsdGeom.Tokens.extent):
                attr = prim.GetAttribute(attr_token)
                if not attr.IsValid():
                    continue

                frames: Iterable[Usd.TimeCode] = (
                    (Usd.TimeCode(f) for f in attr.GetTimeSamples())
                    if attr.GetNumTimeSamples()
                    else (Usd.TimeCode.Default(),)
                )

                for frame in frames:
                    data = np.array(attr.Get(frame))
                    data *= scale_factor
                    attr.Set(Vt.Vec3fArray.FromNumpy(data), frame)  # type: ignore[arg-type]

            for attr_name in ("xformOp:translate", "xformOp:translate:pivot"):
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
            self._stage.GetPrimAtPath(Sdf.Path("/ROOT/MODEL"))
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
                        str(t2.GetParentPath()).replace("/ROOT", "/ROOT/MODEL")
                        + "/MAT_"
                        + new_name
                    ),
                )
            )

    @log_errors
    def PostExport(self) -> bool:
        if self._chaser_args.mode == ChaserMode.RIG:
            self.scale_down_geo()
            self.update_material_bindings()
        elif self._chaser_args.mode == ChaserMode.CAM:
            # TODO: will work in Usd v24
            # editor = Usd.NamespaceEditor(self._stage)
            # editor.MovePrimAtPath(Sdf.Path("/WORLD/CAM/LnD_shotCam"), Sdf.Path("/"))
            # editor.ApplyEdits()

            new_shotCam_path = Sdf.Path("/LnD_shotCam")
            with Sdf.ChangeBlock():
                layer = self._stage.GetEditTarget().GetLayer()

                world_ctrl_find: list[Sdf.Path] = []
                cam_rig_root_find: list[Sdf.Path] = []

                def traverse_kernel(path: Sdf.Path | str):
                    if isinstance(path, str):
                        path = Sdf.Path(path)
                    if path.IsPrimPath():
                        if path.name == "world_CTRL":
                            world_ctrl_find.append(path)
                        elif path.name == "LnD_shotCam":
                            cam_rig_root_find.append(path)

                layer.Traverse(Sdf.Path("/"), traverse_kernel)

                try:
                    world_ctrl_path = world_ctrl_find.pop()
                except IndexError:
                    raise RuntimeError("Could not find world_CTRL in export!")
                try:
                    cam_rig_root = cam_rig_root_find.pop()
                except IndexError:
                    raise RuntimeError("Could not find camera rig root in export!")

                if cam_rig_root != new_shotCam_path:
                    prim_spec = Sdf.CreatePrimInLayer(layer, new_shotCam_path)
                    prim_spec.SetInfo(prim_spec.SpecifierKey, Sdf.SpecifierDef)

                    edit = Sdf.BatchNamespaceEdit()
                    edit.Add(
                        Sdf.NamespaceEdit.Reparent(
                            world_ctrl_path, new_shotCam_path, -1
                        )
                    )
                    edit.Add(Sdf.NamespaceEdit.Remove(cam_rig_root))

                    if not layer.Apply(edit):
                        raise Exception("Failed to apply layer edit!")

            self._stage.SetDefaultPrim(self._stage.GetPrimAtPath(new_shotCam_path))
        else:
            raise ValueError(
                f"{self._chaser_args.mode} is not a valid LnD chaser mode."
            )

        return True
