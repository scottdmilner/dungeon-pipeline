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
    metaUpdater = pipe.metadata.MetadataUpdater()
    srgbChecker = pipe.channels.sRGBChecker()
    metaUpdater.check() or metaUpdater.prompt_update()
    srgbChecker.check() or srgbChecker.prompt_srgb_fix()


if __name__ == "__main__":
    window = start_plugin()
