"""Preflight checks to run on file load"""

import substance_painter as sp

import pipe.sp
from pipe.db import DB
from env import DB_Config

conn = DB.Get(DB_Config)


def start_plugin():
    sp.event.DISPATCHER.connect_strong(sp.event.ProjectEditionEntered, do_preflight)


def close_plugin():
    sp.event.DISPATCHER.disconnect(sp.event.ProjectEditionEntered, do_preflight)


def do_preflight(event: sp.event.Event) -> None:
    metaUpdater = pipe.sp.metadata.MetadataUpdater()
    srgbChecker = pipe.sp.channels.sRGBChecker()
    metaUpdater.check() or metaUpdater.prompt_update()
    srgbChecker.check() or srgbChecker.prompt_srgb_fix()


if __name__ == "__main__":
    window = start_plugin()
