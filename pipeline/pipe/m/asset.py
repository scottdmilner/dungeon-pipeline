import logging
import os
import platform
import shutil
from typing import Optional, Sequence
from PySide2.QtWidgets import QCheckBox, QWidget
from PySide2.QtGui import QTextCursor

import maya.cmds as mc

import pipe
from pipe.db import DB
from pipe.glui.dialogs import FilteredListDialog, MessageDialog
from env import DB_Config

from modelChecker.modelChecker_UI import UI as MCUI

log = logging.getLogger(__name__)


class PublishAssetDialog(FilteredListDialog):
    _substance_only: QCheckBox

    def __init__(self, parent: Optional[QWidget], items: Sequence[str]) -> None:
        super().__init__(
            parent,
            items,
            "Publish Asset",
            "Select asset to publish",
            accept_button_name="Publish",
        )

        self._substance_only = QCheckBox(
            "Export Substance-only file? ONLY USE IF INSTRUCTED BY A LEAD"
        )
        self._layout.insertWidget(1, self._substance_only)

    @property
    def is_substance_only(self) -> bool:
        return self._substance_only.isChecked()


class IOManager:
    _conn: DB
    system: str
    window: Optional[QWidget]

    def __init__(self) -> None:
        self._conn = DB.Get(DB_Config)
        self.system = platform.system()
        self.window = pipe.m.local.get_main_qt_window()

    def publish_asset(self) -> None:
        checker = ModelChecker.get()
        if not checker.check_selected():
            cursor = QTextCursor(checker.reportOutputUI.textCursor())
            cursor.setPosition(0)
            cursor.insertHtml(
                "<h1>Asset not exported. Please resolve model checks.</h1>"
            )
            return

        dialog = PublishAssetDialog(
            self.window, self._conn.get_asset_name_list(sorted=True)
        )

        if not dialog.exec_():
            return

        asset_display_name = dialog.get_selected_item()
        if asset_display_name is None:
            error = MessageDialog(
                self.window, "Error: No asset selected. Nothing exported", "Error"
            )
            error.exec_()
            return

        asset = self._conn.get_asset_by_name(asset_display_name)
        assert asset is not None

        log.debug(asset)

        assert asset.path is not None
        publish_dir = pipe.util.get_production_path() / asset.path
        publish_dir.mkdir(parents=True, exist_ok=True)

        publish_path = (
            str(publish_dir / asset.name)
            + ("_SUBSTANCE" if dialog.is_substance_only else "")
            + ".usd"
        )
        temp_publish_path = os.getenv("TEMP", "") + asset.name + ".usd"

        # save the file
        kwargs = {
            "file": temp_publish_path if self.system == "Windows" else publish_path,
            "selection": True,
            "shadingMode": "none",
            "stripNamespaces": True,
        }
        mc.mayaUSDExport(**kwargs)  # type: ignore[attr-defined]

        # if on Windows, work around this bug: https://github.com/PixarAnimationStudios/OpenUSD/issues/849
        # TODO: check if this is still needed in Maya 2025
        if self.system == "Windows":
            shutil.move(temp_publish_path, publish_path)

        confirm = MessageDialog(
            self.window,
            f"The selected objects have been exported to {publish_path}",
            "Export Complete",
        )
        confirm.exec_()


class ModelChecker(MCUI):
    @classmethod
    def get(cls):
        if not cls.qmwInstance or (type(cls.qmwInstance) is not cls):
            cls.qmwInstance = cls()
        return cls.qmwInstance

    def configure(self) -> None:
        self.uncheckAll()
        commands = [
            "crossBorder",
            "hardEdges",
            "lamina",
            "missingUVs",
            "ngons",
            "noneManifoldEdges",
            "onBorder",
            "selfPenetratingUVs",
            "zeroAreaFaces",
            "zeroLengthEdges",
        ]
        for cmd in commands:
            self.commandCheckBox[cmd].setChecked(True)

    def check_selected(self) -> bool:
        self.configure()
        self.sanityCheck(["Selection"], True)
        self.createReport("Selection")

        # loop and show UI if anything had an error
        diagnostics = self.contexts["Selection"]["diagnostics"]
        for error in self.commandsList.keys():
            if (error in diagnostics) and len(self.parseErrors(diagnostics[error])):
                self.show_UI()
                return False

        return True
