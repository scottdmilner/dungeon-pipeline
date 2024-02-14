"""Preflight checks to run on file load"""

import substance_painter as sp
from typing import List

import pipe
from pipe.db import DB
from pipe.glui.dialogs import MessageDialog
from env import SG_Config

conn = DB(SG_Config)


def start_plugin():
    sp.event.DISPATCHER.connect_strong(sp.event.ProjectEditionEntered, do_preflight)


def close_plugin():
    sp.event.DISPATCHER.disconnect(sp.event.ProjectEditionEntered, do_preflight)


def do_preflight(event: sp.event.Event) -> None:
    check_metadata()
    check_rgb_channels()


def check_metadata() -> None:
    data = sp.project.Metadata("LnD")

    if data.get("asset_id") in conn.get_asset_attr_list("id"):
        return
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
        return

    pipe.metadata.MetadataUpdater().do_update()


def check_rgb_channels() -> None:
    pipe.channels.sRGBChecker().do_srgb_check()


if __name__ == "__main__":
    window = start_plugin()
