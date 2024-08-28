from __future__ import annotations

import logging
import platform
import subprocess
import sys

from abc import ABCMeta, abstractmethod
from pathlib import Path
from PySide2 import QtWidgets

from typing import TYPE_CHECKING

from pipe.db import DBInterface
from pipe.glui.dialogs import (
    FilteredListDialog,
    MessageDialog,
    MessageDialogCustomButtons,
)
from pipe.struct.db import SGEntity
from shared.util import get_production_path

if TYPE_CHECKING:
    import typing
    from types import ModuleType

    KT = typing.TypeVar("KT")
    VT = typing.TypeVar("VT")


log = logging.getLogger(__name__)


class dotdict(dict):
    """dot notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore[assignment]
    __delattr__ = dict.__delitem__  # type: ignore[assignment]


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


def dict_index(d: dict[KT, VT], v: VT) -> KT:
    """List index function for dicts"""
    return list(d.keys())[list(d.values()).index(v)]


def reload_pipe(extra_modules: typing.Sequence[ModuleType] | None = None) -> None:
    """Reload all pipe python modules"""
    if extra_modules is None:
        extra_modules = []
    else:
        extra_modules = list(extra_modules)

    pipe_modules = [
        module
        for name, module in sys.modules.items()
        if (name.startswith("pipe")) and ("shotgun_api3" not in name) or (name == "env")
    ] + extra_modules

    for module in pipe_modules:
        if (name := module.__name__) in sys.modules:
            log.info(f"Unloading {name}")
            del sys.modules[name]


try:

    def silent_startupinfo() -> subprocess.STARTUPINFO | None:  # type: ignore[name-defined]
        """Returns a Windows-only object to make sure tasks launched through
        subprocess don't open a cmd window.

        Returns:
            subprocess.STARTUPINFO -- the properly configured object if we are on
                                    Windows, otherwise None
        """
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
        return startupinfo
except Exception:

    def silent_startupinfo() -> typing.Any | None:
        pass
