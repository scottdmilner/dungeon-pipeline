from __future__ import annotations

import logging
import maya.cmds as mc

from pathlib import Path

import pipe.m
from pipe.db import DB
from pipe.struct.db import Shot
from pipe.util import FileManager

from env_sg import DB_Config

log = logging.getLogger(__name__)


class MFileManagerShot(FileManager):
    def __init__(self) -> None:
        conn = DB.Get(DB_Config)
        window = pipe.m.local.get_main_qt_window()
        super().__init__(conn, Shot, window)

    @staticmethod
    def _check_unsaved_changes() -> bool:
        if mc.file(query=True, modified=True):
            warning_response = mc.confirmDialog(
                title="Do you want to save?",
                message="The current file has not been saved. Continue anyways?",
                button=["Continue", "Cancel"],
                defaultButton="Cancel",
                cancelButton="Cancel",
                dismissString="Cancel",
            )
            if warning_response == "Cancel":
                return False
        return True

    @staticmethod
    def _generate_filename(shot: Shot) -> str:  # type: ignore[override] # Can't do proper generics here
        return shot.code + ".mb"

    @staticmethod
    def _open_file(path: Path) -> None:
        mc.file(str(path), open=True)

    @staticmethod
    def _setup_file(path: Path) -> None:
        mc.file(newFile=True)
        mc.file(str(path), save=True)

        # TODO: set up scene
