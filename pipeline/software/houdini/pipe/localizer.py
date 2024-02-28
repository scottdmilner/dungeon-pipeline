import hou
import re
import sys
from typing import Optional, Type

from PySide2 import QtWidgets

from software.baseclass import DCCLocalizer


class HoudiniLocalizer(DCCLocalizer):
    def __init__(self):
        super().__init__("houdini")

    def get_main_qt_window(self) -> Optional[Type[QtWidgets.QWidget]]:
        if not self.is_headless():
            return hou.qt.mainWindow()
        return None

    def is_headless(self) -> bool:
        return bool(re.match(r"^.*ython(?:\.exe)?3?", sys.executable))
