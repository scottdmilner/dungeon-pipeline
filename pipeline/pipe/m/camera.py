from __future__ import annotations

import logging
from pathlib import Path
from Qt.QtCore import QRegExp
from Qt.QtGui import QRegExpValidator
from Qt.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Any, Sequence

import maya.cmds as mc

from pipe.glui.dialogs import FilteredListDialog
from pipe.m.publish import Publisher
from pipe.m.usdchaser import ExportChaser, ChaserMode
from pipe.struct.db import SGEntity, Shot
from shared.util import get_production_path


log = logging.getLogger(__name__)


class _PublishCameraDialog(FilteredListDialog):
    _camera: QComboBox

    def __init__(self, parent: QWidget | None, items: Sequence[str]) -> None:
        super().__init__(
            parent,
            items,
            "Publish Camera",
            "Select a shot to publish the camera for",
            accept_button_name="Publish",
        )

        self._camera = QComboBox(
            self,
        )
        cameras = mc.ls(cameras=True, visible=True)
        self._camera.addItems(cameras)
        self._camera.setCurrentText(cameras[0])
        validator = QRegExpValidator(QRegExp("|".join(cameras)))
        self._camera.setValidator(validator)

        camera_widget = QWidget()
        camera_layout = QHBoxLayout(camera_widget)
        camera_label = QLabel("Camera:")
        camera_layout.addWidget(camera_label, 1)
        camera_layout.addWidget(self._camera, 99)

        self._layout.insertWidget(0, camera_widget)


class CameraPublisher(Publisher):
    def __init__(self) -> None:
        super().__init__(_PublishCameraDialog)

    def _get_entity_list(self) -> list[str]:
        return self._conn.get_shot_code_list(sorted=True)

    def _get_entity_from_name(self, name: str) -> SGEntity | None:
        return self._conn.get_shot_by_code(name)

    def _get_save_path(self) -> Path | None:
        assert self._entity.path is not None
        return get_production_path() / self._entity.path / "cam" / "cam.usd"

    def _presave(self) -> bool:
        mc.select(self._camera, replace=True)
        return True

    def _get_mayausd_kwargs(self) -> dict[str, Any]:
        shot = cast(Shot, self._entity)
        start = shot.cut_in - 5
        end = shot.cut_out + 5
        return {
            "chaser": [ExportChaser.ID],
            "chaserArgs": [(ExportChaser.ID, "mode", ChaserMode.CAM)],
            "frameRange": (start, end),
            "frameStride": 1.0,
        }

    def _get_confirm_message(self) -> str:
        return f"The camera has been exported to {self._publish_path}"

    @property
    def _camera(self) -> str:
        return cast(_PublishCameraDialog, self._dialog)._camera.currentText()
