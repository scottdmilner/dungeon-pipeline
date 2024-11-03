from __future__ import annotations

import attrs
import numpy as np
import mayaUsd.lib as mayaUsdLib  # type: ignore[import-not-found]

from enum import IntEnum
from pathlib import Path
from pxr import Sdf, Usd, UsdGeom, UsdShade, Vt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable

from pipe.util import log_errors


class ChaserMode(IntEnum):
    ANIM = 1
    CAM = 2
    CHAR = 3


def scale_down_geo(stage: Usd.Stage, scale_factor: float = 0.01) -> None:
    """Recurse through the stage and scale down all Mesh and BasisCurves prims by
    `scale_factor`"""

    root_prim = stage.GetPseudoRoot()

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

    UsdGeom.SetStageMetersPerUnit(
        stage, UsdGeom.GetStageMetersPerUnit(stage) / scale_factor
    )


def update_material_bindings(
    stage: Usd.Stage, old: str, new: str, name_prepend: str = ""
) -> None:
    """Update material bindings to what Houdini will expect"""

    bindings = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath(Sdf.Path(new)))
    for rel in bindings.GetCollectionBindingRels():
        t1, t2 = rel.GetTargets()
        # strip the namespace because the USD exporter strips the geo namespace but not the material namespace
        new_name = t2.name.split("_", 1)[1]
        # Change the material binding to match how it will look in Houdini
        rel.SetTargets(
            (
                t1,
                Sdf.Path(
                    f"{str(t2.GetParentPath()).replace(old, new)}/{name_prepend}{new_name}"
                ),
            )
        )


def move_prim(
    layer: Sdf.Layer, prim_to_move: Sdf.Path, new_prim_parent: Sdf.Path
) -> None:
    with Sdf.ChangeBlock():
        old_prim_parent = prim_to_move.GetParentPath()
        if old_prim_parent != new_prim_parent:
            prim_spec = Sdf.CreatePrimInLayer(layer, new_prim_parent)
            prim_spec.SetInfo(prim_spec.SpecifierKey, Sdf.SpecifierDef)

            edit = Sdf.BatchNamespaceEdit()
            edit.Add(Sdf.NamespaceEdit.Reparent(prim_to_move, new_prim_parent, -1))
            edit.Add(Sdf.NamespaceEdit.Remove(old_prim_parent.GetPrefixes()[0]))

            if not layer.Apply(edit):
                raise Exception("Failed to apply layer edit!")


def find_and_move_prim(
    layer: Sdf.Layer, prim_to_find: str, new_prim_parent: Sdf.Path
) -> None:
    """Searches for the prim with name `prim_to_find` and moves it underneath
    `new_prim_parent`. *Assumes only 1 prim with the given name*"""
    # TODO: will work in Usd v24?
    # editor = Usd.NamespaceEditor(self._stage)
    # editor.MovePrimAtPath(Sdf.Path("/WORLD/CAM/LnD_shotCam"), Sdf.Path("/"))
    # editor.ApplyEdits()

    prim_search: list[Sdf.Path] = []

    def traverse_kernel(path: Sdf.Path | str):
        if isinstance(path, str):
            path = Sdf.Path(path)
        if path.IsPrimPath():
            if path.name == prim_to_find:
                prim_search.append(path)

    layer.Traverse(Sdf.Path("/"), traverse_kernel)

    try:
        prim_to_move = prim_search.pop()
    except IndexError:
        raise RuntimeError(f"Could not find {prim_to_find} in export!")

    move_prim(layer, prim_to_move, new_prim_parent)


def remove_namespace(layer: Sdf.Layer) -> None:
    edit = Sdf.BatchNamespaceEdit()

    def traverse_kernel(path: Sdf.Path | str):
        if isinstance(path, str):
            path = Sdf.Path(path)
        if path.IsPrimPath():
            edit.Add(Sdf.NamespaceEdit.Rename(path, path.name.split("_", 1)[1]))

    layer.Traverse(Sdf.Path("/"), traverse_kernel)
    layer.Apply(edit)


def split_by_namespace(stage: Usd.Stage) -> dict[str, Sdf.Layer]:
    root_layer = stage.GetRootLayer()
    root_layer_path = Path(root_layer.realPath)
    stage.SetEditTarget(root_layer)

    child_names = stage.GetPseudoRoot().GetChildrenNames()
    namespaces = set((n.split("_", 1)[0] for n in child_names))

    layers: dict[str, Sdf.Layer] = dict()
    for namespace in namespaces:
        layer_name = namespace.lower()
        layer_path = str(root_layer_path.parent / f"{layer_name}.usd")

        layer = Sdf.Layer.FindOrOpen(layer_path)
        if layer:
            layer.Clear()
        else:
            layer = Sdf.Layer.CreateNew(layer_path)
        layer.TransferContent(root_layer)

        children_to_keep = [c for c in child_names if c.startswith(namespace)]
        edit = Sdf.BatchNamespaceEdit()
        for child in child_names:
            if child not in children_to_keep:
                edit.Add(Sdf.NamespaceEdit.Remove("/" + child))

        layer.Apply(edit)
        remove_namespace(layer)
        layer.Save()

        layers.update({layer_name: layer})

    # clear out root layer
    edit = Sdf.BatchNamespaceEdit()
    for child in child_names:
        edit.Add(Sdf.NamespaceEdit.Remove("/" + child))
    root_layer.Apply(edit)
    root_layer.Save()

    return layers


def split_preroll(stage: Usd.Stage) -> None:
    pass


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

    @log_errors
    def PostExport(self) -> bool:
        if self._chaser_args.mode == ChaserMode.ANIM:
            scale_down_geo(self._stage)
            layers = split_by_namespace(self._stage)

            root_layer = self._stage.GetRootLayer()
            root_layer_path = Path(root_layer.realPath)

            for name, layer in layers.items():
                char_prim_path = Sdf.Path(f"/__class__/character/{name}")
                char_prim_spec = Sdf.CreatePrimInLayer(root_layer, char_prim_path)
                char_prim_spec.specifier = Sdf.SpecifierOver
                reference = Sdf.Reference(
                    f"./{Path(layer.realPath).relative_to(root_layer_path.parent)}",
                    Sdf.Path("/ROOT/MODEL"),
                )
                char_prim_spec.referenceList.appendedItems = [reference]
            split_preroll(self._stage)

        elif self._chaser_args.mode == ChaserMode.CHAR:
            scale_down_geo(self._stage)
            update_material_bindings(self._stage, "/ROOT", "/ROOT/MODEL", "MAT_")

        elif self._chaser_args.mode == ChaserMode.CAM:
            # We don't scale down the camera here because we need to import it
            # back into Maya. Instead we'll scale it down when we import it into
            # Solaris.

            new_shotCam_path = Sdf.Path("/LnD_shotCam")
            find_and_move_prim(
                self._stage.GetEditTarget().GetLayer(), "world_CTRL", new_shotCam_path
            )
            self._stage.SetDefaultPrim(self._stage.GetPrimAtPath(new_shotCam_path))
        else:
            raise ValueError(
                f"{self._chaser_args.mode} is not a valid LnD chaser mode."
            )

        return True
