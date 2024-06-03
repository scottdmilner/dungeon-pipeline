from itertools import count
from pathlib import Path
from typing import cast, Any, Dict, Generator, Iterable, List, Optional

import hou
import json

from pipe.h.local import get_main_qt_window
from pipe.db import DB
from pipe.struct.asset import Asset
from pipe.struct.material import DisplacementSource, NormalSource, NormalType
from pipe.glui.dialogs import MessageDialog

from env import SG_Config

_MATLIB_NAME = "Material_Library"
_MATNAME = "matname"


# https://github.com/Student-Accomplice-Pipeline-Team/accomplice_pipe/blob/prod/pipe/accomplice/software/houdini/pipe/tools/shading/edit_shader.py
class MatlibManager:
    _conn: DB

    def __init__(self, node: Optional[hou.LopNode] = None) -> None:
        self._conn = DB(SG_Config)
        if node:
            self._init_hda(node)

    def _init_hda(self, node: hou.LopNode) -> None:
        """Initialize values on the HDA instance.
        Note that self.node does not work before initialization, so
        node is passed in as an arg"""
        var_name = node.parm("variant_name")
        assert var_name is not None
        var_id = node.parm("variant_id")
        assert var_id is not None

        variants = self._asset.variants
        if not variants:
            var_name.set("main")
            assert self._asset.id is not None
            var_id.set(self._asset.id)
            return

        var2 = self._conn.get_asset_by_stub(self._asset.variants[0])
        assert var2 is not None
        assert var2.variant_name is not None
        assert var2.id is not None
        var_name.set(var2.variant_name)
        var_id.set(var2.id)

    @property
    def _asset(self) -> Asset:
        """Get asset based off of the path of the current hipfile"""
        a = self._conn.get_asset_by_attr("sg_pipe_name", self._hip.name)
        assert a is not None
        return a

    @property
    def _hip(self) -> Path:
        """Get $HIP variable as a Path object"""
        return Path(hou.hscriptStringExpression("$HIP"))

    @property
    def _hsite(self) -> Path:
        """Get $HSITE variable as a Path object"""
        return Path(hou.hscriptStringExpression("$HSITE"))

    @property
    def mat_info(self) -> Optional[List[Dict[str, Any]]]:
        """Attempt to get mat.json file for selected variant"""
        try:
            variant = self._conn.get_asset_by_id(self.variant_id)
            assert variant is not None

            if not (variant_name := variant.variant_name):
                variant_name = "main"

            with open(self._hip / "tex" / variant_name / "mat.json", "r") as f:
                return json.load(f)
        except Exception:
            return None

    @property
    def matlib(self) -> hou.LopNode:
        """Get Material Library node inside of current node"""
        node = hou.node(f"./{_MATLIB_NAME}")
        assert isinstance(node, hou.LopNode)
        return node

    @property
    def node(self) -> hou.LopNode:
        """Get current node (the HDA)"""
        node = hou.node("./")
        assert isinstance(node, hou.LopNode)
        return node

    @property
    def variant_id(self) -> int:
        """Get the id of the current variant"""
        var_id = self.node.parm("variant_id")
        assert var_id is not None
        if (node_val := var_id.evalAsInt()) == -1:
            ## if it hasn't been set yet, set it to the default value
            default = int(self.get_variant_list()[0])
            var_id.set(default)
            return default
        return node_val

    @variant_id.setter
    def variant_id(self, id: int) -> None:
        """Set the variant ID and update the variant name"""
        var_id = self.node.parm("variant_id")
        assert var_id is not None
        var_id.set(id)
        asset = self._conn.get_asset_by_id(id)
        assert asset is not None
        assert asset.variant_name is not None
        var_name = self.node.parm("variant_name")
        assert var_name is not None
        if self._asset.variants:
            var_name.set(asset.variant_name)
        else:
            var_name.set("main")

    @property
    def variant_name(self) -> str:
        var_name = self.node.parm("variant_name")
        assert var_name is not None
        if (node_val := var_name.evalAsString()) == "none":
            variants = self._asset.variants
            variant_name: str
            if variants:
                var1 = self._conn.get_asset_by_stub(variants[0])
                assert var1 is not None
                assert var1.variant_name is not None
                variant_name = var1.variant_name
            else:
                variant_name = "main"
            var_name.set(variant_name)
            return variant_name
        return node_val

    def _cleanup_matnet(
        self, new_items: Iterable[hou.NetworkMovableItem], mat_info: Dict[str, Any]
    ) -> None:
        def get_map_paths(node: hou.Node) -> Generator[Path, None, None]:
            filename_parm = node.parm("filename")
            assert filename_parm is not None
            dir, filename = filename_parm.evalAsString().rsplit("/", 1)
            return Path(dir).glob(filename.replace("<UDIM>", "*"))

        # locate relevant nodes
        control_node: hou.Node
        displacement_map: hou.Node
        displacement_nodes: List[hou.Node] = []
        emissive_node: hou.Node
        ior_node: hou.Node
        normal_node: hou.Node
        presence_node: hou.Node
        preview_node: hou.Node
        for item in new_items:
            if item.networkItemType() != hou.networkItemType.Node:
                continue
            item = cast(hou.Node, item)
            name = item.name().lower()
            if "disp" in name:
                if name.startswith("disp"):
                    displacement_map = item
                else:
                    displacement_nodes.append(item)
            elif name.startswith("ior"):
                ior_node = item
            elif name.startswith("emissive"):
                emissive_node = item
            elif name.startswith("presence"):
                presence_node = item
            elif name.startswith("control"):
                control_node = item
            elif name.startswith("normal_"):
                normal_node = item
            elif name.startswith("usdpreview"):
                preview_node = item

        # Remove optional maps
        if not next(get_map_paths(ior_node), None):
            ior_node.destroy()

        if not next(get_map_paths(emissive_node), None):
            emissive_node.destroy()

        if not next(get_map_paths(presence_node), None):
            preview_node.setInput(8, None)
            presence_node.destroy()

        # Remove unused displacement nodes
        if not next(get_map_paths(displacement_map), None):
            displacement_map.destroy()
            for node in displacement_nodes:
                node.destroy()
            for parm in ["disp_depth", "disp_height"]:
                p = control_node.parm(parm)
                assert p is not None
                p.hide(True)

        # Set bump roughness undisplaced bool
        if (
            (NormalSource(mat_info["normal_source"]) == NormalSource.NORMAL_HEIGHT)
            and (
                DisplacementSource(mat_info["displacement_source"])
                == DisplacementSource.HEIGHT
            )
            and (NormalType(mat_info["normal_type"]) == NormalType.BUMP_ROUGHNESS)
        ):
            undisplaced_parm = normal_node.parm("useUndisplacedPosition")
            assert undisplaced_parm is not None
            undisplaced_parm.set(True)

    def _load_items_from_file(
        self, dest_node: hou.LopNode, file_path: str
    ) -> List[hou.NetworkMovableItem]:
        """Loads a VOP network into a LOP node. Returns list of added items"""
        before = dest_node.allItems()
        dest_node.loadItemsFromFile(file_path)
        after = dest_node.allItems()

        return list(set(after) - set(before))

    def _move_matnet(
        self, new_items: Iterable[hou.NetworkMovableItem], x_pos: int
    ) -> None:
        master_box = next(
            (
                cast(hou.NetworkBox, i)
                for i in new_items
                if (i.networkItemType() == hou.networkItemType.NetworkBox)
                and (cast(hou.NetworkBox, i).comment() == _MATNAME)
            )
        )
        if not master_box:
            return
        master_box.setPosition((x_pos, 0))

    def _rename_matnet(
        self,
        new_items: Iterable[hou.NetworkMovableItem],
        name: str,
        name_placeholder: str = _MATNAME,
    ) -> None:
        # iterate over new nodes and swap placeholder names for the shading group name
        for item in new_items:
            if item.networkItemType() == hou.networkItemType.Node:
                new_name = item.name().replace(name_placeholder, name)
                item.setName(new_name)

                # update "Shading Group Name" on control null
                if new_name == f"CONTROLS_{name}":
                    node = hou.node(item.path())
                    assert node is not None
                    node_name = node.parm("name")
                    assert node_name is not None
                    node_name.set(name)
            elif item.networkItemType() == hou.networkItemType.NetworkBox:
                item = cast(hou.NetworkBox, item)
                if item.comment() == name_placeholder:
                    item.setComment(name)

    def get_variant_list(self) -> List[str]:
        """Gets list of variants in the way that the HDA interface expects:
        [id1, label1, id2, label2, ...]"""
        if len(self._asset.variants):
            return [s for v in self._asset.variants for s in (str(v.id), v.disp_name)]
        else:
            return [str(self._asset.id), "Main"]

    def export_selected_to_path(
        self, path: str, curr_name: str, new_name: str = _MATNAME
    ) -> None:
        items = hou.selectedItems()
        self._rename_matnet(items, new_name, curr_name)
        items[0].parent().saveItemsToFile(items, path)
        self._rename_matnet(items, curr_name, new_name)

    def import_matnets(self) -> None:
        """Import a material network for each shading group in the export"""
        if not (mat_info := self.mat_info):
            MessageDialog(
                get_main_qt_window(),
                "Error! Could not get material info. Make sure that textures have been exported for the currently selected variant.",
            ).exec_()
            return

        pos = count(start=0, step=20)
        for shading_group in mat_info:
            name = shading_group["name"]
            norm_type = NormalType(shading_group["normal_type"])
            if norm_type == NormalType.STANDARD:
                template_name = "standard"
            elif norm_type == NormalType.BUMP_ROUGHNESS:
                template_name = "b2r"
            else:
                raise ValueError(f"Unimplemented NormalType: {norm_type}")

            nodes = self._load_items_from_file(
                self.matlib, str(self._hsite / f"matl/{template_name}.cpio")
            )
            self._move_matnet(nodes, next(pos))
            self._rename_matnet(nodes, name)
            self._cleanup_matnet(nodes, shading_group)


class MatlibErrorChecker:
    @staticmethod
    def CheckFilepathsRelative(matlib: hou.LopNode) -> int:
        for node in matlib.children():
            if (fn := node.parm("filename")) is not None:
                if not fn.unexpandedString().startswith("$"):
                    return 1
        return 0
