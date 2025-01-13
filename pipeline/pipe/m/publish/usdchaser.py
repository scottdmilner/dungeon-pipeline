from __future__ import annotations

import attrs
import json
import numpy as np
import mayaUsd.lib as mayaUsdLib  # type: ignore[import-not-found]

from enum import IntEnum
from math import isclose
from pathlib import Path
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdUtils, Vt
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from typing import Any, Callable, Iterable, Protocol

    class TimeSampleble(Protocol):
        def GetTimeSamples(self) -> list[float]: ...
        def GetNumTimeSamples(self) -> int: ...


from pipe.db import DB
from pipe.struct.timeline import Timeline
from pipe.util import log_errors
from shared.util import get_production_path

from env_sg import DB_Config


class ChaserMode(IntEnum):
    ANIM = 1
    CAM = 2
    CHAR = 3


def get_frames_from_attr(attr: TimeSampleble) -> Iterable[Usd.TimeCode]:
    return (
        (Usd.TimeCode(f) for f in attr.GetTimeSamples())
        if attr.GetNumTimeSamples()
        else (Usd.TimeCode.Default(),)
    )


def create_or_clear_layer(path: str) -> Sdf.Layer:
    layer = Sdf.Layer.FindOrOpen(path)
    if layer:
        layer.Clear()
    else:
        layer = Sdf.Layer.CreateNew(path)
    return layer


def scale_down_geo(stage: Usd.Stage, scale_factor: float = 0.01) -> None:
    """Recurse through the stage and scale down all Mesh and BasisCurves prims by
    `scale_factor`"""

    root_prim = stage.GetPseudoRoot()
    data: Any

    for prim in (it := iter(Usd.PrimRange(root_prim))):
        extent = prim.GetAttribute(UsdGeom.Tokens.extent)
        if extent.IsValid():
            for frame in get_frames_from_attr(extent):
                data = np.array(extent.Get(frame))
                data *= scale_factor
                extent.Set(Vt.Vec3fArray.FromNumpy(data), frame)  # type: ignore[arg-type]

        xformable = UsdGeom.Xformable(prim)
        xformop: UsdGeom.XformOp
        for xformop in xformable.GetOrderedXformOps():
            xform_type = UsdGeom.XformOp.GetOpTypeToken(xformop.GetOpType())

            if (not xformop.IsDefined()) or xformop.IsInverseOp():
                continue

            if xform_type == UsdGeom.XformOpTypes.translate:
                for frame in get_frames_from_attr(xformop):
                    data: Gf.Vec3d = xformop.Get(frame)  # type: ignore[no-redef]
                    data *= scale_factor
                    xformop.Set(data, frame)

            elif xform_type == UsdGeom.XformOpTypes.transform:
                for frame in get_frames_from_attr(xformop):
                    data: Gf.Matrix4d = xformop.GetOpTransform(frame)  # type: ignore[no-redef]
                    translate = data.ExtractTranslation()
                    translate *= scale_factor
                    data.SetTranslateOnly(translate)
                    xformop.Set(data, frame)

        if not (prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.BasisCurves)):  # type: ignore[call-overload]
            continue

        # don't recurse deeper than this
        it.PruneChildren()

        for attr_token in (UsdGeom.Tokens.points,):
            attr = prim.GetAttribute(attr_token)
            if not attr.IsValid():
                continue

            for frame in get_frames_from_attr(attr):
                data = np.array(attr.Get(frame))
                data *= scale_factor
                attr.Set(Vt.Vec3fArray.FromNumpy(data), frame)  # type: ignore[arg-type]

    UsdGeom.SetStageMetersPerUnit(
        stage, UsdGeom.GetStageMetersPerUnit(stage) / scale_factor
    )


TOPOLOGY_ATTRIBS = (
    UsdGeom.Tokens.cornerIndices,
    UsdGeom.Tokens.cornerSharpnesses,
    UsdGeom.Tokens.creaseIndices,
    UsdGeom.Tokens.creaseLengths,
    UsdGeom.Tokens.creaseSharpnesses,
    UsdGeom.Tokens.faceVaryingLinearInterpolation,
    UsdGeom.Tokens.faceVertexCounts,
    UsdGeom.Tokens.faceVertexIndices,
    UsdGeom.Tokens.holeIndices,
    UsdGeom.Tokens.interpolateBoundary,
    UsdGeom.Tokens.triangleSubdivisionRule,
)


def make_topo_attrs_default(stage: Usd.Stage) -> None:
    root_prim = stage.GetPseudoRoot()
    for prim in (it := iter(Usd.PrimRange(root_prim))):
        if not (prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.BasisCurves)):  # type: ignore[call-overload]
            continue

        # don't recurse deeper than this
        it.PruneChildren()

        for attr_token in TOPOLOGY_ATTRIBS:
            attr = prim.GetAttribute(attr_token)
            if not attr.IsValid():
                continue
            data = attr.Get(1)
            if data:
                attr.Clear()
                attr.Set(data, Usd.TimeCode.Default())


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


def remove_namespace(layer: Sdf.Layer, root: Sdf.Path = Sdf.Path("/")) -> None:
    edit = Sdf.BatchNamespaceEdit()

    def traverse_kernel(path: Sdf.Path | str):
        if isinstance(path, str):
            path = Sdf.Path(path)
        if path.IsPrimPath():
            try:
                edit.Add(Sdf.NamespaceEdit.Rename(path, path.name.split("_", 1)[1]))
            except IndexError:
                print(f"Namespace not changed for {str(path)}")

    layer.Traverse(root, traverse_kernel)
    layer.Apply(edit)


def split_by_namespace(stage: Usd.Stage, suffix: str) -> dict[str, Sdf.Layer]:
    root_layer = stage.GetRootLayer()
    root_layer_path = Path(root_layer.realPath)
    stage.SetEditTarget(root_layer)

    child_names = stage.GetPseudoRoot().GetChildrenNames()
    namespaces = set()
    for n in child_names:
        namespace, item = n.split("_", 1)
        if item.startswith("S_"):  # static props
            remove_namespace(root_layer, Sdf.Path("/" + n))
            remove_namespace(root_layer, Sdf.Path("/" + item))
            s, namespace, _ = item.split("_", 2)
        namespaces.add(namespace)

    child_names = stage.GetPseudoRoot().GetChildrenNames()
    layers: dict[str, Sdf.Layer] = dict()
    for namespace in namespaces:
        layer_name = namespace.lower()
        layer_path = str(root_layer_path.parent / f"{layer_name}.{suffix}.usd")
        layer = create_or_clear_layer(layer_path)
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


def float_range_compare_factory(
    keep_start: float | None, keep_end: float | None
) -> Callable[[float], bool]:
    def check_start(val: float) -> bool:
        return isclose(val, keep_start, rel_tol=1e-4) or (keep_start < val)  # type: ignore[arg-type, operator]

    def check_end(val: float) -> bool:
        return isclose(val, keep_end, rel_tol=1e-4) or (val < keep_end)  # type: ignore[arg-type, operator]

    def check_both(val: float) -> bool:
        return check_start(val) and check_end(val)

    if (keep_start is not None) and (keep_end is not None):
        return check_both
    elif keep_start is not None:
        return check_start
    elif keep_end is not None:
        return check_end
    else:
        raise ValueError("Must provide keep_start or keep_end")


def timesample_erase_kernel_factory(
    layer: Sdf.Layer, *, keep_start: float | None = None, keep_end: float | None = None
) -> Callable[[Sdf.Path | str], None]:
    """Returns a layer traversal kernel that erases time samples not between
    keep_start and keep_end
    NOTE: assume that all time samples are in this layer"""

    def kernel(path: Sdf.Path | str) -> None:
        if isinstance(path, str):
            path = Sdf.Path(path)
        if not path.IsPrimPropertyPath():
            return
        attr_spec = layer.GetAttributeAtPath(path)
        if not attr_spec.variability == Sdf.VariabilityVarying:
            return

        start = (
            layer.GetBracketingTimeSamplesForPath(path, keep_start)[0]
            if keep_start
            else None
        )
        end = (
            layer.GetBracketingTimeSamplesForPath(path, keep_end)[1]
            if keep_end
            else None
        )
        cmp = float_range_compare_factory(start, end)
        for ts in layer.ListTimeSamplesForPath(path):
            if cmp(ts):
                continue
            layer.EraseTimeSample(path, ts)

        if keep_start:
            layer.startTimeCode = keep_start
        if keep_end:
            layer.endTimeCode = keep_end

    return kernel


def split_preroll(
    anim_layer: Sdf.Layer, name: str, prim_path: Sdf.Path, tl: Timeline
) -> Sdf.Layer:
    """Split anim and preroll data into separate files, then stitch them together
    with Value Clips"""
    preroll_layer_path = str(Path(anim_layer.realPath).parent / f"{name}.preroll.usd")
    preroll_layer = create_or_clear_layer(preroll_layer_path)
    preroll_layer.TransferContent(anim_layer)

    preroll_layer.Traverse(
        preroll_layer.pseudoRoot.path,
        timesample_erase_kernel_factory(preroll_layer, keep_end=(tl.head - 1)),
    )
    preroll_layer.Save()

    anim_layer.Traverse(
        anim_layer.pseudoRoot.path,
        timesample_erase_kernel_factory(anim_layer, keep_start=tl.head),
    )
    anim_layer.Save()

    stitched_layer_path = str(Path(anim_layer.realPath).parent / f"{name}.usd")
    stiched_layer = create_or_clear_layer(stitched_layer_path)
    stiched_layer.TransferContent(anim_layer)

    timesample_files = [preroll_layer.realPath, anim_layer.realPath]
    topology_layer = create_or_clear_layer(
        UsdUtils.GenerateClipTopologyName(stiched_layer.resolvedPath)
    )
    manifest_layer = create_or_clear_layer(
        UsdUtils.GenerateClipManifestName(stiched_layer.realPath)
    )
    UsdUtils.StitchClipsTopology(topology_layer, timesample_files)
    UsdUtils.StitchClipsManifest(
        manifest_layer, topology_layer, timesample_files, prim_path
    )
    UsdUtils.StitchClips(
        stiched_layer, timesample_files, prim_path, tl.preroll, tl.end, False
    )
    stiched_layer.Save()

    return stiched_layer


@attrs.define
class ChaserArgs:
    mode: ChaserMode = attrs.field(converter=int)
    timeline: Optional[Timeline] = attrs.field(
        default=None,
        kw_only=True,
        converter=lambda t: Timeline.from_json(t) if t else None,
    )
    props: Optional[dict[str, list[str]]] = attrs.field(
        default=None,
        kw_only=True,
        converter=lambda p: json.loads(p) if p else None,
    )


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
            assert self._chaser_args.props is not None
            assert self._chaser_args.timeline is not None

            scale_down_geo(self._stage)
            make_topo_attrs_default(self._stage)
            layers = split_by_namespace(self._stage, "anim")

            root_layer = self._stage.GetRootLayer()
            root_layer_path = Path(root_layer.realPath)

            conn = DB.Get(DB_Config)

            for name, layer in layers.items():
                print(name)

                # the one rig that needs the controls exported instead of the mesh
                if name == "gemheart":
                    character_root_path = Sdf.Path("/ROOT/CTRLS")
                else:
                    character_root_path = Sdf.Path("/ROOT/MODEL")

                stitched_layer = split_preroll(
                    layer, name, character_root_path, self._chaser_args.timeline
                )

                char_prim_spec = Sdf.CreatePrimInLayer(
                    root_layer, Sdf.Path(f"/__class__/character/{name}")
                )
                char_prim_spec.specifier = Sdf.SpecifierOver

                reference = Sdf.Reference(
                    f"./{Path(stitched_layer.realPath).relative_to(root_layer_path.parent)}",
                    character_root_path,
                )

                char_prim_spec.referenceList.appendedItems = [reference]

                try:
                    asset = conn.get_asset_by_attr("name", name)
                    assert asset.path is not None
                    rig_path = f"{asset.path}/usd/main.usd"
                    walk_up_len = (
                        len(root_layer_path.relative_to(get_production_path()).parts)
                        - 1
                    )
                    root_layer.subLayerPaths.append("../" * walk_up_len + rig_path)
                except Exception:
                    print(f"Warning! Could not find asset matching namespace {name}")

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
