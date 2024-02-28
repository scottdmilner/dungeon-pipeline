from substance_painter import ui
from typing import Optional, Type

from PySide2 import QtWidgets

from software.baseclass import DCCLocalizer


class SubstancePainterLocalizer(DCCLocalizer):
    def __init__(self):
        super().__init__("substance_painter")

    def get_main_qt_window(self) -> Optional[Type[QtWidgets.QWidget]]:
        return ui.get_main_window()

    def is_headless(self) -> bool:
        return False
