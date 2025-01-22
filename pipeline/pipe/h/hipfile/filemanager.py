from __future__ import annotations

import hou
import logging
from pathlib import Path

import pipe.h
from pipe.db import DB
from pipe.struct.db import SGEntity
from pipe.util import FileManager

from env_sg import DB_Config

log = logging.getLogger(__name__)


class HFileManager(FileManager):
    def __init__(
        self,
        entity_type: type[SGEntity],
        versioning: bool = False,
        version_glob: str = "",
        override_entity_code: str | None = None,
    ) -> None:
        conn = DB.Get(DB_Config)
        window = pipe.h.local.get_main_qt_window()
        super().__init__(
            conn,
            entity_type,
            window,
            versioning=versioning,
            version_glob=version_glob,
            override_entity_code=override_entity_code,
        )

    def _check_unsaved_changes(self) -> bool:
        if self._override_entity_code:
            return True

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

    def _open_file(self, path: Path) -> None:
        hou.hipFile.load(str(path), suppress_save_prompt=True)

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        hou.hipFile.clear(suppress_save_prompt=True)
        hou.hipFile.save(str(path))
