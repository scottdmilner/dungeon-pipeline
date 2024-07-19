from __future__ import annotations

import hmac
import json
import logging
import os
import platform
import shutil

from hashlib import sha1
from urllib import request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing
from PySide2.QtWidgets import QCheckBox, QWidget
from PySide2.QtGui import QTextCursor

import maya.cmds as mc

import pipe
from pipe.db import DB
from pipe.glui.dialogs import (
    FilteredListDialog,
    MessageDialog,
    MessageDialogCustomButtons,
)
from shared.util import get_production_path
from env import PIPEBOT_SECRET, PIPEBOT_URL
from env_sg import DB_Config

from modelChecker.modelChecker_UI import UI as MCUI

log = logging.getLogger(__name__)


class PublishAssetDialog(FilteredListDialog):
    _substance_only: QCheckBox

    def __init__(self, parent: QWidget | None, items: typing.Sequence[str]) -> None:
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
    window: QWidget | None

    def __init__(self) -> None:
        self._conn = DB.Get(DB_Config)
        self.system = platform.system()
        self.window = pipe.m.local.get_main_qt_window()

    def publish_asset(self) -> None:
        checker = ModelChecker.get()
        override = False
        if not checker.check_selected():
            checker_fail_dialog = MessageDialogCustomButtons(
                self.window,
                "Error. This asset did not pass the model checker. Please "
                "ensure your model meets the requirements set by the model "
                "checker.",
                "Cannot export: Model Checker",
                has_cancel_button=True,
                ok_name="Override",
                cancel_name="Ok",
            )
            override = bool(checker_fail_dialog.exec_())
            if not override:
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
        publish_dir = get_production_path() / asset.path
        publish_dir.mkdir(parents=True, exist_ok=True)

        publish_path = (
            str(publish_dir / asset.name)
            + ("_SUBSTANCE" if dialog.is_substance_only else "")
            + ".usd"
        )
        temp_publish_path = os.getenv("TEMP", "") + asset.name + ".usd"

        # notify webhook of override
        if override:
            override_info = {
                "user": os.getlogin(),
                "asset": asset.disp_name,
                "path": publish_path,
            }
            data = bytes(json.dumps(override_info), encoding="utf-8")
            hashcheck = (
                "sha1=" + hmac.new(PIPEBOT_SECRET.encode(), data, sha1).hexdigest()
            )

            req = request.Request(
                url=PIPEBOT_URL + "/model_checker",
                data=data,
            )
            req.add_header("x-pipebot-signature", hashcheck)
            request.urlopen(req)

        # save the file
        kwargs = {
            "file": temp_publish_path if self.system == "Windows" else publish_path,
            "selection": True,
            "shadingMode": "useRegistry",
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
            #            "selfPenetratingUVs",
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

    # Override
    def sanityCheck(self, contextsUuids, refreshSelection=True) -> None:
        """The `sanityCheck` function cannot handle transforms that do not
        have children. This catches those errors and warns the modelers."""
        try:
            super().sanityCheck(contextsUuids, refreshSelection)
        except RuntimeError as err:
            if (
                "(kInvalidParameter): Object is incompatible with this method"
                in err.args
            ):
                MessageDialog(
                    self.parent(),
                    "The model checker could not run. Please ensure that you do "
                    "not have any empty transforms.",
                    "Model Checker Failed",
                ).exec_()
            else:
                raise err
