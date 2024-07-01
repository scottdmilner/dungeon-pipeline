import hou
import logging
from pathlib import Path

import pipe.h
from pipe.db import DB
from pipe.glui.dialogs import FilteredListDialog
from env import DB_Config

log = logging.getLogger(__name__)


class FileManager:
    _conn: DB

    def __init__(self) -> None:
        self._conn = DB.Get(DB_Config)

    def _check_unsaved_changes(self) -> bool:
        """Returns True if safe to proceed, False otherwise"""
        if hou.hipFile.hasUnsavedChanges():
            warning_response = hou.ui.displayMessage(
                "The current file has not been saved. Continue anyways?",
                buttons=("Continue", "Cancel"),
                severity=hou.severityType.ImportantMessage,
                default_choice=1,
            )
            if warning_response == 1:
                return False
        return True

    def _prompt_create_if_not_exist(self, path: Path) -> bool:
        """Returns True if safe to proceed, False otherwise"""
        if not path.exists():
            warning_response = hou.ui.displayMessage(
                f"{str(path)} does not exist. Create?",
                buttons=("Create Folder", "Cancel"),
                severity=hou.severityType.Message,
                default_choice=1,
            )
            if warning_response == 1:
                return False
            path.mkdir(mode=0o770, parents=True)
        return True

    def open_asset_file(self) -> None:
        if not self._check_unsaved_changes():
            return

        asset_names = self._conn.get_asset_name_list(
            sorted=True, child_mode=DB.ChildQueryMode.ROOTS
        )

        asset_open_dialog = FilteredListDialog(
            pipe.h.local.get_main_qt_window(),
            asset_names,
            "Open Asset File",
            "Select the Asset File that you'd like to open.",
            accept_button_name="Open",
        )

        if not asset_open_dialog.exec_():
            log.debug("error initializing dialog")
            return

        asset_response = asset_open_dialog.get_selected_item()

        if not asset_response:
            return

        asset = self._conn.get_asset_by_name(asset_response)
        try:
            assert asset is not None
            assert asset.path is not None
        except AssertionError:
            hou.ui.displayMessage(
                "The asset you are trying to load does not have a path set in ShotGrid. Please let a Lead know",
                buttons=("OK"),
                severity=hou.severityType.ImportantMessage,
            )
            return

        asset_path = pipe.util.get_production_path() / asset.path

        if not self._prompt_create_if_not_exist(asset_path):
            return

        file_path = asset_path / f"{asset.name}.hipnc"

        if file_path.is_file():
            hou.hipFile.load(str(file_path), suppress_save_prompt=True)
            return

        hou.hipFile.clear(suppress_save_prompt=True)
        hou.hipFile.save(str(file_path))
        self.populate_asset_file()

    def populate_asset_file(self) -> None:
        # TODO: create starting nodes
        pass

    def open_shot_file(self) -> None:
        pass
