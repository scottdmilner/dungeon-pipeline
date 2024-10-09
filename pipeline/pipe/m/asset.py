from __future__ import annotations

import hmac
import json
import logging
import os
from hashlib import sha1
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib import request
from Qt.QtWidgets import QCheckBox, QWidget
from Qt.QtGui import QTextCursor

if TYPE_CHECKING:
    from typing import Any, Sequence

from pipe.m.publish import Publisher
from pipe.glui.dialogs import (
    FilteredListDialog,
    MessageDialog,
    MessageDialogCustomButtons,
)
from pipe.struct.db import Asset, SGEntity
from shared.util import get_production_path
from env import PIPEBOT_SECRET, PIPEBOT_URL

from modelChecker.modelChecker_UI import UI as MCUI

log = logging.getLogger(__name__)


class _PublishAssetDialog(FilteredListDialog):
    _substance_only: QCheckBox

    def __init__(self, parent: QWidget | None, items: Sequence[str]) -> None:
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


class AssetPublisher(Publisher):
    _override: bool

    def __init__(self) -> None:
        super().__init__(_PublishAssetDialog)

    def _prepublish(self) -> bool:
        checker = ModelChecker.get()
        self._override = False
        if not checker.check_selected():
            checker_fail_dialog = MessageDialogCustomButtons(
                self._window,
                "Error. This asset did not pass the model checker. Please "
                "ensure your model meets the requirements set by the model "
                "checker.",
                "Cannot export: Model Checker",
                has_cancel_button=True,
                ok_name="Override",
                cancel_name="Ok",
            )
            self._override = bool(checker_fail_dialog.exec_())
            if not self._override:
                cursor = QTextCursor(checker.reportOutputUI.textCursor())
                cursor.setPosition(0)
                cursor.insertHtml(
                    "<h1>Asset not exported. Please resolve model checks.</h1>"
                )
                return False
        return True

    def _get_entity_list(self) -> list[str]:
        return self._conn.get_asset_name_list(sorted=True)

    def _get_entity_from_name(self, name: str) -> SGEntity | None:
        return self._conn.get_asset_by_name(name)

    def _get_save_path(self) -> Path | None:
        dialog = cast(_PublishAssetDialog, self._dialog)
        asset = cast(Asset, self._entity)
        assert asset.path is not None
        return (
            get_production_path()
            / asset.path
            / (asset.name + ("_SUBSTANCE" if dialog.is_substance_only else "") + ".usd")
        )

    def _presave(self) -> bool:
        # notify webhook of override
        if self._override:
            asset = cast(Asset, self._entity)
            override_info = {
                "user": os.getlogin(),
                "asset": asset.disp_name,
                "path": str(self._publish_path),
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
        return True

    def _get_mayausd_kwargs(self) -> dict[str, Any]:
        return {
            "shadingMode": "useRegistry",
        }


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
            # "selfPenetratingUVs",
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
