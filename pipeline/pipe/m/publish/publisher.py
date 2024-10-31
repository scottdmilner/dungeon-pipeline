from __future__ import annotations

import logging
import os
import platform
import shutil
from functools import wraps
from pathlib import Path

import maya.cmds as mc

import pipe
from pipe.db import DB
from pipe.glui.dialogs import FilteredListDialog, MessageDialog
from pipe.struct.db import SGEntity
from env_sg import DB_Config

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from Qt.QtWidgets import QWidget

log = logging.getLogger(__name__)


class Publisher:
    """Class for publishing USDs out of Maya"""

    _conn: DB
    _dialog: FilteredListDialog
    _dialog_T: type[FilteredListDialog]
    _entity: SGEntity
    _publish_path: Path
    _system: str
    _window: QWidget | None

    def __init__(self, dialog: type[FilteredListDialog] | None = None) -> None:
        self._conn = DB.Get(DB_Config)
        self._window = pipe.m.local.get_main_qt_window()
        self._system = platform.system()
        self._dialog_T = dialog or FilteredListDialog

    @staticmethod
    def _assert_not_none(fun):
        @wraps(fun)
        def wrap(*args, **kwargs):
            result = fun(*args, **kwargs)
            if result is None:
                raise AssertionError
            return result

        return wrap

    def __init_subclass__(cls, *args, **kwargs) -> None:
        """Wrap overridden definitions of these methods"""
        super().__init_subclass__(*args, **kwargs)
        funcs = (cls._get_entity_from_name, cls._get_save_path)
        for f in funcs:
            setattr(cls, f.__name__, cls._assert_not_none(f))

    @property
    def _IS_WINDOWS(self) -> bool:
        return self._system == "Windows"

    def _prepublish(self) -> bool:
        """Runs before any other part of the publish function"""
        return True

    def _get_entity_list(self) -> list[str]:
        """Get a list of strings to prompt in the dialog"""
        return []

    @_assert_not_none
    def _get_entity_from_name(self, name: str) -> SGEntity | None:
        """Turn the string chosen in the dialog into a SG entity"""
        return None

    @_assert_not_none
    def _get_save_path(self) -> Path | None:
        """Get the save path"""
        if user_select := mc.fileDialog2(fileFilter="*.usd"):
            return Path(user_select[0])
        return None

    def _presave(self) -> bool:
        """Run before any files are saved out"""
        return True

    def _get_mayausd_kwargs(self) -> dict[str, Any]:
        """A dictionary of additional arguments to `mc.mayaUSDExport`"""
        return {}

    def _get_confirm_message(self) -> str:
        return f"The selected objects have been exported to {self._publish_path}"

    def publish(self):
        """Generic publishing function.
        `Exporter().publish()` will publish the selected geometry to the place
        chosen in the pop-up dialog, accounting for the USD export bug on
        Windows. Specific functionality is defined by passing a
        `FilteredListDialog` class into `__init__` and by overriding the
        following functions:
          - `prepublish(self)`
          - `get_entity_list(self) -> list[str]`
          - `get_entity_from_name(self, disp_name: str) -> SGEntity`
          - `get_save_path(self) -> Path`
          - `presave(self)`
          - `get_mayausd_kwargs(self) -> dict[str, Any]`
        """
        if not self._prepublish():
            return

        if entity_list := self._get_entity_list():
            # if there is a non-empty entity list, prompt the user with a dialog
            self._dialog = self._dialog_T(self._window, entity_list)
            if not self._dialog.exec_():
                return

            disp_name = self._dialog.get_selected_item()

            if disp_name is None:
                error = MessageDialog(
                    self._window, "Error: Nothing selected. Nothing exported", "Error"
                )
                error.exec_()
                return

            # get the corresponding SGEntity object
            try:
                self._entity = self._get_entity_from_name(disp_name)
            except AssertionError:
                error = MessageDialog(
                    self._window,
                    f"Error: The selected item did not correspond to a valid {self._entity.__class__.__name__} "
                    "in ShotGrid. Please report this error. Nothing exported",
                    "Error",
                )
                error.exec_()
                return
            log.debug(self._entity)

        try:
            self._publish_path = self._get_save_path()
        except AssertionError:
            error = MessageDialog(
                self._window,
                f"Error: No path for this {self._entity.__class__.__name__} "
                "set in ShotGrid. Nothing exported",
                "Error",
            )
            error.exec_()
            return

        if not self._presave():
            return

        self._publish_path.parent.mkdir(parents=True, exist_ok=True)
        temp_publish_path = os.getenv("TEMP", "") + os.pathsep + self._publish_path.name

        kwargs = {
            "file": str(temp_publish_path if self._IS_WINDOWS else self._publish_path),
            "selection": True,
            "stripNamespaces": True,
            **self._get_mayausd_kwargs(),
        }

        mc.mayaUSDExport(**kwargs)  # type: ignore[attr-defined]

        # if on Windows, work around this bug: https://github.com/PixarAnimationStudios/OpenUSD/issues/849
        # TODO: check if this is still needed in Maya 2025
        if self._IS_WINDOWS:
            shutil.move(temp_publish_path, self._publish_path)

        confirm = MessageDialog(
            self._window,
            self._get_confirm_message(),
            "Export Complete",
        )
        confirm.exec_()
