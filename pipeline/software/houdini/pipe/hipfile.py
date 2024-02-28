import hou
from pathlib import Path

import pipe.util
from pipe.db import DB
from pipe.struct import Asset
from env import SG_Config


class FileManager:
    _conn: DB

    def __init__(self) -> None:
        self._conn = DB(SG_Config)

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

        asset_response = hou.ui.selectFromList(
            asset_names,
            exclusive=True,
            message="Select the Asset File that you'd like to open.",
            title="Open Asset File",
            column_header="Assets",
        )

        if not asset_response:
            return

        asset_name = asset_names[asset_response[0]]
        asset: Asset = self._conn.get_asset_by_name(asset_name)
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

    def open_shot_file() -> None:
        pass
