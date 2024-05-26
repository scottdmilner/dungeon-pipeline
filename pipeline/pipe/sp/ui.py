import logging
from math import log2
from PySide2 import QtCore, QtWidgets
from re import findall
from typing import Callable, Dict, List, Mapping, Optional, Set

import substance_painter as sp

import pipe
from pipe.sp.local import get_main_qt_window
from pipe.glui.dialogs import ButtonPair, MessageDialog
from pipe.sp.export import Exporter, TexSetExportSettings, DefaultChannels
from pipe.struct import MaterialType

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
        # self.resize(480, self.height())

        self.tex_set_widgets = []

        # Make sure window always stays on top
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QtWidgets.QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        self.title = QtWidgets.QLabel("Publish Textures")
        self.title.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(self.title, 0)
        # title_font = self.title.font()
        # print(title_font.pointSize())
        # title_font = QtGui.QFont('Arial')
        # title_font.setPointSize(28)
        # title_font.setWeight(18)
        # self.title.setFont(title_font)

        # File lock warning
        self.lock_warning = QtWidgets.QLabel(
            'WARNING: If you currently have this asset open in Houdini on Windows, you MUST stop your render and press "Reset Renderman RIS / XPU" before exporting or TEX file conversion will not work!'
        )
        self.lock_warning.setWordWrap(True)
        self.main_layout.addWidget(self.lock_warning)

        for ts in sp.textureset.all_texture_sets():
            widget = TexSetWidget(self, ts)
            self.tex_set_dict[ts] = widget
            self.main_layout.addWidget(widget)

        # Buttons
        self._init_buttons(has_cancel_button=True, ok_name="Export")
        self.buttons.rejected.connect(self.close)
        # self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.do_export)
        self.main_layout.addWidget(self.buttons)

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
                TexSetExportSettings(
                    ts, wgt.mat_type, wgt.extra_channels, wgt.resolution
                )
                for ts, wgt in self.tex_set_dict.items()
                if wgt.enabled
            ]
        ):
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
    ts_layout: QtWidgets.QLayout
    ts_channels_layout: QtWidgets.QLayout
    button_layout: QtWidgets.QLayout
    radio_buttons: Dict[MaterialType, QtWidgets.QRadioButton]
    extra_channels: Set[sp.textureset.Channel]
    parent_window: SubstanceExportWindow
    enabled_checkbox: QtWidgets.QCheckBox
    ts_container: QtWidgets.QWidget
    resolution_dropdown: QtWidgets.QComboBox

    MaterialTypeNames = {
        MaterialType.GENERAL: "General",
        MaterialType.SHINY: "Shiny",
        # MaterialType.METAL: "Metal (not implemented)",
        # MaterialType.GLASS: "Glass (not implemented)",
        # MaterialType.CLOTH: "Cloth (not implemented)",
        # MaterialType.SKIN: "Skin (not implemented)",
    }

    def __init__(
        self,
        parent: SubstanceExportWindow,
        tex_set: sp.textureset.TextureSet,
        flags: Optional[QtCore.Qt.WindowFlags] = None,
    ) -> None:
        super().__init__(parent)
        self.setParent(parent)
        self.parent_window = parent
        self.tex_set = tex_set
        self.radio_buttons = {}
        self.extra_channels = set()
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.ts_layout = QtWidgets.QHBoxLayout()
        self.ts_layout.setContentsMargins(0, 0, 0, 0)
        self.ts_layout.setSpacing(0)

        # Enable/disable checkbox
        self.enabled_checkbox = QtWidgets.QCheckBox()
        self.enabled_checkbox.setChecked(True)
        self.enabled_checkbox.resize(24, 24)
        self.enabled_checkbox.toggled.connect(self._enabled_checkbox_callback)
        self.ts_layout.addWidget(self.enabled_checkbox, 10)

        self.ts_container = QtWidgets.QWidget()
        self.ts_layout.addWidget(self.ts_container, 90, QtCore.Qt.AlignLeft)
        self.ts_inner_layout = QtWidgets.QHBoxLayout(self.ts_container)
        self.ts_channels_layout = QtWidgets.QVBoxLayout()
        self.ts_inner_layout.addLayout(self.ts_channels_layout, 70)

        self.button_layout = QtWidgets.QHBoxLayout()

        self.label = QtWidgets.QLabel(f"Texture Set: {self.tex_set.name()}")
        self.ts_channels_layout.addWidget(self.label)

        for mtype, name in self.MaterialTypeNames.items():
            radio = QtWidgets.QRadioButton(name)
            radio.setChecked(mtype == MaterialType.GENERAL)
            radio.toggled.connect(self._setup_extra_channel_layout)
            self.button_layout.addWidget(radio)
            self.radio_buttons[mtype] = radio

        self.ts_channels_layout.addLayout(self.button_layout)

        self.extra_channel_layout = QtWidgets.QHBoxLayout()
        self._setup_extra_channel_layout()

        self.ts_channels_layout.addLayout(self.extra_channel_layout)

        self.resolution_dropdown = QtWidgets.QComboBox()
        self.resolution_dropdown.addItems(["128", "256", "512", "1024", "2048", "4096"])
        self.resolution_dropdown.setCurrentIndex(
            int(log2(self.tex_set.get_resolution().width)) - 7
        )
        self.ts_inner_layout.addWidget(self.resolution_dropdown, 20, QtCore.Qt.AlignTop)

        self.setLayout(self.ts_layout)

    def _enabled_checkbox_callback(self) -> None:
        self.ts_container.setEnabled(self.enabled_checkbox.isChecked())

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
        except ValueError:
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
                checkbox.stateChanged.connect(self._extra_channels_updater(ch))
                self.extra_channel_layout.addWidget(checkbox)

    def _extra_channels_updater(self, ch: sp.textureset.Channel) -> Callable[[], None]:
        def inner() -> None:
            if ch in self.extra_channels:
                self.extra_channels.remove(ch)
            else:
                self.extra_channels.add(ch)

        return inner

    @property
    def mat_type(self) -> MaterialType:
        return next(
            (mtype for mtype, radio in self.radio_buttons.items() if radio.isChecked()),
            MaterialType.GENERAL,
        )

    @property
    def enabled(self) -> bool:
        return self.enabled_checkbox.isChecked()

    @property
    def resolution(self) -> int:
        """Returns the resolution log 2"""
        return self.resolution_dropdown.currentIndex() + 7
