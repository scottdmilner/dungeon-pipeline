from __future__ import annotations

from .filemanager import FileManager
from .playblaster import Playblaster
from .struct import dict_index, dotdict

import logging
import platform
import subprocess
import sys

from functools import wraps
from Qt import QtWidgets

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Any, Callable, Sequence
    from types import ModuleType

log = logging.getLogger(__name__)


def checkbox_callback_helper(
    checkbox: QtWidgets.QCheckBox, widget: QtWidgets.QWidget
) -> Callable[[], None]:
    """Helper function to generate a callback to enable/disable a widget when
    a checkbox is checked"""

    def inner() -> None:
        widget.setEnabled(checkbox.isChecked())

    return inner


def log_errors(fun):
    @wraps(fun)
    def wrap(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except Exception as e:
            log.error(e, exc_info=True)
            raise

    return wrap


def reload_pipe(extra_modules: Sequence[ModuleType] | None = None) -> None:
    """Reload all pipe python modules"""
    if extra_modules is None:
        extra_modules = []
    else:
        extra_modules = list(extra_modules)

    pipe_modules = [
        module
        for name, module in sys.modules.items()
        if (name.startswith("pipe") or name.startswith("shared"))
        and ("shotgun_api3" not in name)
        or (name == "env")
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

    def silent_startupinfo() -> Any | None:
        pass


__all__ = [
    "checkbox_callback_helper",
    "dict_index",
    "dotdict",
    "log_errors",
    "reload_pipe",
    "silent_startupinfo",
    "FileManager",
    "Playblaster",
]
