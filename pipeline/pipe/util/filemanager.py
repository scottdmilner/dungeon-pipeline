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


class OpenFileDialog(FilteredListDialog):
    _version_cb: QtWidgets.QCheckBox | None

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        items: list[str],
        entity_type: type[SGEntity],
        versioning: bool,
        version_msg: str,
    ) -> None:
        super().__init__(
            parent,
            items,
            f"Open {entity_type.__name__} File",
            f"Select the {entity_type.__name__} file that you'd like to open.",
            accept_button_name="Open",
        )

        if versioning:
            self._version_cb = QtWidgets.QCheckBox(version_msg)
            self._layout.insertWidget(1, self._version_cb)
        else:
            self._version_cb = None

    @property
    def open_old_file(self) -> bool:
        if self._version_cb:
            return self._version_cb.isChecked()
        return False


class FileManager(metaclass=ABCMeta):
    _conn: DBInterface
    _entity_type: type[SGEntity]
    _main_window: QtWidgets.QWidget | None
    _versioning: bool
    _version_glob: str
    _version_msg: str
    _override_entity_code: str | None

    def __init__(
        self,
        conn: DBInterface,
        entity_type: type[SGEntity],
        main_window: QtWidgets.QWidget | None,
        *,
        versioning: bool = False,
        version_glob: str = "{}.*.{}",
        version_msg: str = "Open older version",
        override_entity_code: str | None = None,
    ) -> None:
        self._conn = conn
        self._entity_type = entity_type
        self._main_window = main_window
        self._versioning = versioning
        self._version_glob = version_glob
        self._version_msg = version_msg
        self._override_entity_code = override_entity_code

    @abstractmethod
    def _check_unsaved_changes(self) -> bool:
        pass

    @abstractmethod
    def _generate_filename_ext(self, entity: SGEntity) -> tuple[str, str]:
        pass

    def _get_subpath(self) -> str:
        return ""

    @abstractmethod
    def _open_file(self, path: Path) -> None:
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
            if not self._override_entity_code:
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
        if not self._override_entity_code:
            entity_names = self._conn.get_entity_code_list(
                self._entity_type,
                sorted=True,
                child_mode=DBInterface.ChildQueryMode.ROOTS,
            )
            open_file_dialog = OpenFileDialog(
                self._main_window,
                entity_names,
                self._entity_type,
                versioning=self._versioning,
                version_msg=self._version_msg,
            )

            if not open_file_dialog.exec_():
                log.debug("error intializing dialog")
                return

            response = open_file_dialog.get_selected_item()
        else:
            response = self._override_entity_code

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

        filename, ext = self._generate_filename_ext(entity)
        file_path = entity_path / f"{filename}.{ext}"

        if self._versioning:
            files = [file_path] + sorted(
                entity_path.glob(self._version_glob.format(filename, ext))
            )

            # prompt the user for which version to open
            if (not self._override_entity_code) and open_file_dialog.open_old_file:
                version_file_dialog = FilteredListDialog(
                    self._main_window,
                    [file.name for file in files],
                    "Choose a version",
                    "Select the version filename to open",
                    accept_button_name="Select",
                )
                if not version_file_dialog.exec_():
                    log.debug("error initializing version dialog")
                    return

                version = version_file_dialog.get_selected_item()
                if not version:
                    return
                file_path = entity_path / version

            # otherwise get the alphabetically last file
            else:
                file_path = files.pop()

        if file_path.is_file():
            self._open_file(file_path)
        else:
            self._setup_file(file_path, entity)

        self._post_open_file(entity)
