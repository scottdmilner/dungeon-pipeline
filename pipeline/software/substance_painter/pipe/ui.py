from enum import Enum
from PySide2 import QtCore, QtWidgets
from typing import List, Mapping, Optional, Type

import substance_painter as sp

import pipe
from pipe.glui.dialogs import ButtonPair


class MaterialType(Enum):
    GENERAL = 0
    METAL = 1
    GLASS = 2
    CLOTH = 3
    SKIN = 4


class SubstanceExportWindow(QtWidgets.QMainWindow, ButtonPair):
    central_widget: QtWidgets.QWidget
    main_layout: QtWidgets.QLayout
    tex_set_widgets: List[Type["TexSetWidget"]]
    tex_set_dict: Mapping[sp.textureset.TextureSet, Type["TexSetWidget"]]
    title: QtWidgets.QLabel

    def __init__(
        self,
        flags: Optional[QtCore.Qt.WindowFlags] = None,
    ) -> None:
        super(SubstanceExportWindow, self).__init__(pipe.local.get_main_qt_window())

        self.tex_set_dict = dict.fromkeys(sp.textureset.all_texture_sets(), None)

        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("LnD Exporter")
        self.resize(400, 300)

        self.tex_set_widgets = []

        # Make sure window always stays on top
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        self.title = QtWidgets.QLabel("Publish Textures")
        self.title.setAlignment(QtCore.Qt.AlignCenter)
        font = self.title.font()
        font.setPointSize(48)
        self.title.setFont(font)
        self.main_layout.addWidget(self.title, 0)

        for ts in self.tex_set_dict:
            widget = TexSetWidget(self, ts.name())
            self.tex_set_dict[ts] = widget
            self.main_layout.addWidget(widget)

        # Buttons
        self._init_buttons(has_cancel_button=True, ok_name="Export")
        self.buttons.rejected.connect(self.close)
        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.do_export)
        self.main_layout.addWidget(self.buttons)

    def radio_callback(self):
        """Enable export button when all texture sets accounted for"""
        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(
            all(
                any(button.isChecked() for button in widget.radio_buttons.values())
                for widget in self.tex_set_dict.values()
            )
        )

    def do_export(self):
        pass


class TexSetWidget(QtWidgets.QWidget):
    name: str
    layout: QtWidgets.QLayout
    button_layout: QtWidgets.QLayout
    radio_buttons: Mapping[MaterialType, QtWidgets.QRadioButton]

    MaterialTypeNames = {
        MaterialType.GENERAL: "General",
        MaterialType.METAL: "Metal (not implemented)",
        MaterialType.GLASS: "Glass (not implemented)",
        MaterialType.CLOTH: "Cloth (not implemented)",
        MaterialType.SKIN: "Skin (not implemented)",
    }

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        name: str,
        flags: Optional[QtCore.Qt.WindowFlags] = None,
    ) -> None:
        super().__init__(parent)
        self.setParent(parent)
        self.name = name
        self.radio_buttons = {}
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QtWidgets.QVBoxLayout()
        self.button_layout = QtWidgets.QHBoxLayout()

        self.label = QtWidgets.QLabel(f"Texture Set: {self.name}")
        self.layout.addWidget(self.label)

        for mtype, name in self.MaterialTypeNames.items():
            radio = QtWidgets.QRadioButton(name)
            radio.setChecked(False)
            radio.toggled.connect(self.parentWidget().radio_callback)
            self.button_layout.addWidget(radio)
            self.radio_buttons[mtype] = radio

        self.layout.addLayout(self.button_layout)
        self.setLayout(self.layout)

    def get(self) -> MaterialType:
        return next(
            (mtype for mtype, radio in self.radio_buttons.items() if radio.isChecked()),
            MaterialType.GENERAL,
        )
