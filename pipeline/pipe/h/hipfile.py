from __future__ import annotations

import hou
import logging
from pathlib import Path
from typing import cast

import pipe.h
from pipe.db import DB
from pipe.struct.db import Asset, Environment, SGEntity
from pipe.util import FileManager

from env_sg import DB_Config

log = logging.getLogger(__name__)


class HFileManager(FileManager):
    def __init__(self, entity_type: type[SGEntity]) -> None:
        conn = DB.Get(DB_Config)
        window = pipe.h.local.get_main_qt_window()
        super().__init__(conn, entity_type, window)

    @staticmethod
    def _check_unsaved_changes() -> bool:
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

    @staticmethod
    def _open_file(path: Path) -> None:
        hou.hipFile.load(str(path), suppress_save_prompt=True)

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        hou.hipFile.clear(suppress_save_prompt=True)
        hou.hipFile.save(str(path))


class HAssetFileManager(HFileManager):
    def __init__(self) -> None:
        super().__init__(Asset)

    @staticmethod
    def _generate_filename(entity) -> str:
        asset = cast(Asset, entity)
        return asset.name + ".hipnc"

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        super(HAssetFileManager, HAssetFileManager)._setup_file(self, path, entity)

        hip_path = Path(hou.hscriptStringExpression("$HIP"))
        hou.setContextOption("ASSET", hip_path.name)


class HEnvFileManager(HFileManager):
    def __init__(self) -> None:
        super().__init__(Environment)

    @staticmethod
    def _generate_filename(entity) -> str:
        env = cast(Environment, entity)
        return env.name + ".hipnc"

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        super(HEnvFileManager, HEnvFileManager)._setup_file(self, path, entity)

        hip_path = Path(hou.hscriptStringExpression("$HIP"))
        hou.setContextOption("ENVIRON", hip_path.name)
