from __future__ import annotations

import logging

from abc import ABCMeta, abstractmethod
from pathlib import Path
from Qt import QtWidgets

from typing import TYPE_CHECKING

from pipe.db import DBInterface
from pipe.glui.dialogs import (
    FilteredListDialog,
    MessageDialog,
    MessageDialogCustomButtons,
)
from shared.util import get_production_path

if TYPE_CHECKING:
    from pipe.struct.db import SGEntity


log = logging.getLogger(__name__)


class FileManager(metaclass=ABCMeta):
    _conn: DBInterface
    _entity_type: type[SGEntity]
    _main_window: QtWidgets.QWidget | None

    def __init__(
        self,
        conn: DBInterface,
        entity_type: type[SGEntity],
        main_window: QtWidgets.QWidget | None,
    ) -> None:
        self._conn = conn
        self._entity_type = entity_type
        self._main_window = main_window

    @staticmethod
    @abstractmethod
    def _check_unsaved_changes() -> bool:
        pass

    @staticmethod
    @abstractmethod
    def _generate_filename(entity: SGEntity) -> str:
        pass

    @staticmethod
    def _get_subpath() -> str:
        return ""

    @staticmethod
    @abstractmethod
    def _open_file(path: Path) -> None:
        """Opens the file into the current session"""
        pass

    @abstractmethod
    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        """Setup a new file in the current session"""
        pass

    def _post_open_file(self, entity: SGEntity) -> None:
        """Execute additional code after opening or creating a scene"""
        pass

    def _prompt_create_if_not_exist(self, path: Path) -> bool:
        """Returns True if safe to proceed, False otherwise"""
        if not path.exists():
            prompt_create = MessageDialogCustomButtons(
                self._main_window,
                f"{str(path)} does not exist. Create?",
                has_cancel_button=True,
                ok_name="Create Folder",
                cancel_name="Cancel",
            )
            if not bool(prompt_create.exec_()):
                return False
            path.mkdir(mode=0o770, parents=True)
        return True

    def open_file(self) -> None:
        if not self._check_unsaved_changes():
            return

        entity_names = self._conn.get_entity_code_list(
            self._entity_type, sorted=True, child_mode=DBInterface.ChildQueryMode.ROOTS
        )
        open_file_dialog = FilteredListDialog(
            self._main_window,
            entity_names,
            f"Open {self._entity_type.__name__} File",
            f"Select the {self._entity_type.__name__} file that you'd like to open.",
            accept_button_name="Open",
        )

        if not open_file_dialog.exec_():
            log.debug("error intializing dialog")
            return

        response = open_file_dialog.get_selected_item()
        if not response:
            return

        entity = self._conn.get_entity_by_code(self._entity_type, response)

        try:
            assert entity is not None
            assert entity.path is not None
        except AssertionError:
            MessageDialog(
                self._main_window,
                f"The {self._entity_type.__name__.lower()} you are trying to "
                "load does not have a path set in ShotGrid.",
                "Error: No path set",
            ).exec_()
            return

        entity_path = get_production_path() / entity.path / self._get_subpath()
        if not self._prompt_create_if_not_exist(entity_path):
            return

        file_path = entity_path / self._generate_filename(entity)
        if file_path.is_file():
            self._open_file(file_path)
        else:
            self._setup_file(file_path, entity)

        self._post_open_file(entity)
