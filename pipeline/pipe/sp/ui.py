import logging
from PySide2 import QtCore, QtWidgets
from re import findall
from typing import Callable, Dict, List, Mapping, Optional, Set

import substance_painter as sp

import pipe
from pipe.sp.local import get_main_qt_window
from pipe.glui.dialogs import ButtonPair, MessageDialog
from pipe.sp.export import Exporter, MaterialType, TexSetExportSettings, DefaultChannels

log = logging.getLogger(__name__)


class SubstanceExportWindow(QtWidgets.QMainWindow, ButtonPair):
    central_widget: QtWidgets.QWidget
    main_layout: QtWidgets.QLayout
    tex_set_widgets: List["TexSetWidget"]
    tex_set_dict: Mapping[sp.textureset.TextureSet, "TexSetWidget"]
    title: QtWidgets.QLabel

    def __init__(
        self,
        flags: Optional[QtCore.Qt.WindowFlags] = None,
    ) -> None:
        super(SubstanceExportWindow, self).__init__(get_main_qt_window())

        self.tex_set_dict = {}

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

        for ts in sp.textureset.all_texture_sets():
            widget = TexSetWidget(self, ts)
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

    def _preflight(self) -> bool:
        """Check for asset metadata and correct channel types before running
        the export"""
        metaUpdater = pipe.sp.metadata.MetadataUpdater()
        srgbChecker = pipe.sp.channels.sRGBChecker()
        meta = metaUpdater.check() or metaUpdater.do_update()
        srgb = srgbChecker.check() or srgbChecker.prompt_srgb_fix()
        return meta and srgb

    def do_export(self) -> None:
        if not self._preflight():
            MessageDialog(
                get_main_qt_window(),
                "Your file has failed preflight checks. Please follow the instructions to fix them when you press Export.",
                "Preflight failed.",
            ).exec_()
            return

        print("Exporting!")
        exporter = Exporter()
        if exporter.export(
            [
                TexSetExportSettings(ts, wgt.mat_type, wgt.extra_channels)
                for ts, wgt in self.tex_set_dict.items()
            ]
        ):
            # TODO: not using tex_set_dict.values.get() and passing separate material types
            MessageDialog(
                get_main_qt_window(),
                "Textures successfully exported!",
            ).exec_()
        else:
            MessageDialog(
                get_main_qt_window(),
                "An error occured while exporting textures. Please check the console for more information",
            ).exec_()

        self.close()


class TexSetWidget(QtWidgets.QWidget):
    tex_set: sp.textureset.TextureSet
    layout: QtWidgets.QLayout
    button_layout: QtWidgets.QLayout
    radio_buttons: Dict[MaterialType, QtWidgets.QRadioButton]
    extra_channels: Set[sp.textureset.ChannelType]

    MaterialTypeNames = {
        MaterialType.GENERAL: "General",
        # MaterialType.METAL: "Metal (not implemented)",
        # MaterialType.GLASS: "Glass (not implemented)",
        # MaterialType.CLOTH: "Cloth (not implemented)",
        # MaterialType.SKIN: "Skin (not implemented)",
    }

    def __init__(
        self,
        parent: QtWidgets.QWidget,
        tex_set: sp.textureset.TextureSet,
        flags: Optional[QtCore.Qt.WindowFlags] = None,
    ) -> None:
        super().__init__(parent)
        self.setParent(parent)
        self.tex_set = tex_set
        self.radio_buttons = {}
        self.extra_channels = set()
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.layout = QtWidgets.QVBoxLayout()
        self.button_layout = QtWidgets.QHBoxLayout()

        self.label = QtWidgets.QLabel(f"Texture Set: {self.tex_set.name()}")
        self.layout.addWidget(self.label)

        for mtype, name in self.MaterialTypeNames.items():
            radio = QtWidgets.QRadioButton(name)
            radio.setChecked(False)
            radio.toggled.connect(self.parentWidget().radio_callback)
            radio.toggled.connect(self._setup_extra_channel_layout)
            self.button_layout.addWidget(radio)
            self.radio_buttons[mtype] = radio

        self.layout.addLayout(self.button_layout)

        self.extra_channel_layout = QtWidgets.QHBoxLayout()
        self._setup_extra_channel_layout()

        self.layout.addLayout(self.extra_channel_layout)

        self.setLayout(self.layout)

    def _setup_extra_channel_layout(self) -> None:
        # clear out layout
        for i in reversed(range(self.extra_channel_layout.count())):
            widget_to_remove = self.extra_channel_layout.itemAt(i).widget()
            self.extra_channel_layout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)

        # clear out channel list
        self.extra_channels.clear()

        stack: sp.textureset.Stack
        try:
            stack = self.tex_set.get_stack()
        except:
            MessageDialog(
                get_main_qt_window(),
                "Warning! Could not get material stacks! You are doing something cool with material layering. Please show this to Scott so he can fix it.",
            ).exec_()
            return

        current_mt = self.mat_type
        for ct, ch in stack.all_channels().items():
            if ct not in DefaultChannels[current_mt]:
                name = (
                    getattr(ch, "label", None)
                    and ch.label().title().replace(" ", "")
                    or ch.type().name
                )
                # add spaces
                name = " ".join(
                    findall(r"[A-Z0-9](?:[a-z0-9]+|[A-Z]*(?=[A-Z]|$))", name)
                )
                checkbox = QtWidgets.QCheckBox(name)
                checkbox.setChecked(False)
                checkbox.stateChanged.connect(self._extra_channels_updater(ct))
                self.extra_channel_layout.addWidget(checkbox)

    def _extra_channels_updater(
        self, ct: sp.textureset.ChannelType
    ) -> Callable[[], None]:
        def inner() -> None:
            if ct in self.extra_channels:
                self.extra_channels.remove(ct)
            else:
                self.extra_channels.add(ct)

        return inner

    @property
    def mat_type(self) -> MaterialType:
        return next(
            (mtype for mtype, radio in self.radio_buttons.items() if radio.isChecked()),
            MaterialType.GENERAL,
        )
