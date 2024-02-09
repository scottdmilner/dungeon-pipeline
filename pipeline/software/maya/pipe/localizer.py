import re
import sys
from typing import Optional, Type

from PySide2 import QtWidgets
import shiboken2
import maya.OpenMayaUI as omUI

from software.baseclass import DCCLocalizer


class MayaLocalizer(DCCLocalizer):
    def __init__(self):
        super().__init__("maya")

    def get_main_qt_window(self) -> Optional[Type[QtWidgets.QWidget]]:
        if not self.is_headless():
            ptr = omUI.MQtUtil.mainWindow()
            if ptr is not None:
                return shiboken2.wrapInstance(int(ptr), QtWidgets.QWidget)
        return None

    def is_headless(self) -> bool:
        pattern = re.compile("^.*mayapy(?:\.?(?:bin|exe))$")
        return bool(pattern.match(sys.executable))
