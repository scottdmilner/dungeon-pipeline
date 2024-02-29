import substance_painter as sp

import pipe
from pipe.db import DB
from pipe.glui.dialogs import FilteredListDialog, MessageDialog
from env import SG_Config


class MetadataUpdater:
    conn: DB

    def __init__(self) -> None:
        self.conn = DB(SG_Config)

    def check(self) -> bool:
        data = sp.project.Metadata("LnD")
        return data.get("asset_id") in self.conn.get_asset_attr_list("id")

    def prompt_update(self) -> bool:
        if self.check():
            return True

        update = MessageDialog(
            pipe.local.get_main_qt_window(),
            "It looks like this file is not associated with an asset in ShotGrid. Would you like to associate it now?",
            "Associate Asset with ShotGrid?",
            has_cancel_button=True,
        ).exec_()

        if not update:
            MessageDialog(
                pipe.local.get_main_qt_window(),
                "Warning! You will need to associate this asset with ShotGrid before exporting textures.",
                "No asset selected",
            ).exec_()
            return False

        return self.do_update()

    def do_update(self) -> bool:
        fld = FilteredListDialog(
            pipe.local.get_main_qt_window(),
            self.conn.get_asset_name_list(sorted=True),
            "Associate Asset with ShotGrid",
            "Select an asset to associate this Substance Painter file with",
            accept_button_name="Associate",
        )
        if not fld.exec_():
            return False
        item = fld.get_selected_item()

        if item is None:
            MessageDialog(
                pipe.local.get_main_qt_window(),
                "Warning! No asset selected, you will need to associate this asset with ShotGrid before exporting.",
                "No asset selected",
            ).exec_()
            return False

        asset = self.conn.get_asset_by_name(item)
        assert asset is not None
        data = sp.project.Metadata("LnD")
        data.set("asset_id", asset.id)

        MessageDialog(
            pipe.local.get_main_qt_window(),
            f"Successfully associated with asset {asset.disp_name} in ShotGrid!",
            "Success",
        ).exec_()
        return True
