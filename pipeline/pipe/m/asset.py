import logging
import os
import platform
import shutil
from typing import Optional, Sequence
from PySide2.QtWidgets import QCheckBox, QWidget

import maya.cmds as mc

import pipe
from pipe.db import DB
from pipe.glui.dialogs import FilteredListDialog, MessageDialog
from env import SG_Config

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
        self._conn = DB(SG_Config)
        self.system = platform.system()
        self.window = pipe.m.local.get_main_qt_window()

    def publish_asset(self) -> None:
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
        mc.file(
            temp_publish_path if self.system == "Windows" else publish_path,
            options=";".join(
                [
                    "",
                    "exportUVs=1",
                    "exportSkels=none",
                    "exportSkin=none",
                    "exportBlendShapes=0",
                    "exportDisplayColor=0",
                    "exportColorSets=1",
                    "exportComponentTags=1",
                    "defaultMeshScheme=catmullClark",
                    "animation=0",
                    "eulerFilter=0",
                    "staticSingleSample=0",
                    "startTime=1",
                    "endTime=1",
                    "frameStride=1",
                    "frameSample=0.0",
                    "defaultUSDFormat=usdc",
                    "parentScope=" + asset.name,
                    "shadingMode=useRegistry",
                    "convertMaterialsTo=[UsdPreviewSurface]",
                    "exportInstances=1",
                    "exportVisibility=0",
                    "mergeTransformAndShape=1",
                    "stripNamespaces=0",
                    "worldspace=0",
                ]
            ),
            type="USD Export",
            preserveReferences=True,
            exportSelected=True,
        )

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
