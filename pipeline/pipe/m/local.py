from __future__ import annotations

import re
import sys

from Qt import QtWidgets
import shiboken2
import maya.OpenMayaUI as omUI

from software.baseclass import DCCLocalizer


class _MayaLocalizer(DCCLocalizer):
    def __init__(self) -> None:
        super().__init__("maya")

    def get_main_qt_window(self) -> QtWidgets.QWidget | None:
        if not self.is_headless():
            ptr = omUI.MQtUtil.mainWindow()
            if ptr is not None:
                return shiboken2.wrapInstance(int(ptr), QtWidgets.QWidget)
        return None

    def is_headless(self) -> bool:
        pattern = re.compile("^.*mayapy(?:\.?(?:bin|exe))$")
        return bool(pattern.match(sys.executable))


_l = _MayaLocalizer()

get_main_qt_window = _l.get_main_qt_window
is_headless = _l.is_headless
