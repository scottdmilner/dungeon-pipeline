import hou
import re
import sys
from typing import Optional, Type

from PySide2 import QtWidgets

from software.baseclass import DCCLocalizer


class _HoudiniLocalizer(DCCLocalizer):
    def __init__(self) -> None:
        super().__init__("houdini")

    def get_main_qt_window(self) -> Optional[QtWidgets.QWidget]:
        if not self.is_headless():
            return hou.qt.mainWindow()
        return None

    def is_headless(self) -> bool:
        return bool(re.match(r"^.*ython(?:\.exe)?3?", sys.executable))


_l = _HoudiniLocalizer()

get_main_qt_window = _l.get_main_qt_window
is_headless = _l.is_headless
