from pathlib import Path
from typing import Dict, Iterable, List

import hou
import json

import pipe
from pipe.db import DB
from pipe.struct import Asset, AssetStub, MaterialType
from pipe.glui.dialogs import MessageDialog

from env import SG_Config

MATLIB_NAME = "Material_Library"


# https://github.com/Student-Accomplice-Pipeline-Team/accomplice_pipe/blob/prod/pipe/accomplice/software/houdini/pipe/tools/shading/edit_shader.py
class MatlibManager:
    _conn: DB

    def __init__(self) -> None:
        self._conn = DB(SG_Config)

    @property
    def _asset(self) -> Asset:
        return self._conn.get_asset_by_attr("sg_pipe_name", self._hip.parent.name)

    @property
    def _hip(self) -> Path:
        return Path(hou.hipFile.path())

    @property
    def matlib(self) -> hou.LopNode:
        return hou.node(f"./{MATLIB_NAME}")

    @property
    def node(self) -> hou.LopNode:
        return hou.node("./")

    @property
    def hsite(self) -> str:
        return hou.hscriptExpression("$HSITE")

    @property
    def variant_id(self) -> int:
        return self.node.parm("variant_id").evalAsInt()

    @variant_id.setter
    def variant_id(self, id) -> None:
        self.node.parm("variant_id").set(id)

    @property
    def mat_info(self) -> List:
        try:
            variant = self._conn.get_asset_by_id(self.variant_id)
            with open(
                self._hip.parent / f"tex/{variant.variant_name}/mat.json", "r"
            ) as f:
                return json.load(f)
        except:
            return None

    def import_matnets(self) -> None:
        if not (mat_info := self.mat_info):
            MessageDialog(
                pipe.local.get_main_qt_window(),
                "Error! Could not get material info. Make sure that textures have been exported.",
            ).exec_()

        for sg in mat_info:
            name = sg["name"]
            nodes = self._load_items_from_file(
                self.matlib, f"{self.hsite}/matl/general.matl"
            )
            self._rename_matnet(nodes, name)

    def _load_items_from_file(
        self, dest_node: hou.LopNode, file_path: str
    ) -> List[hou.NetworkMovableItem]:
        """Loads a VOP network into a LOP node. Returns list of added items"""
        before = dest_node.allItems()
        dest_node.loadItemsFromFile(file_path)
        after = dest_node.allItems()

        return list(set(after) - set(before))

    def get_variant_list(self) -> Dict[int, str]:
        return {v.id: v.disp_name for v in self._asset.variants}

    def _rename_matnet(
        self,
        new_items: Iterable[hou.NetworkMovableItem],
        name: str,
        name_placeholder: str = "matname",
    ) -> None:
        # iterate over new nodes and swap placeholder names for the shading group name
        for item in new_items:
            if item.networkItemType() == hou.networkItemType.Node:
                new_name = item.name().replace(name_placeholder, name)
                item.setName(new_name)

                # update control null
                if item.name() == f"CONTROLS_{name}":
                    node = hou.node(item.path())
                    node.parm("name").set(name)
