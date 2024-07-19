from __future__ import annotations

import logging
import os
from math import log2
from PySide2 import QtCore, QtWidgets
from PySide2.QtGui import QIcon, QPixmap, QRegExpValidator
from PySide2.QtWidgets import QComboBox, QLabel, QLayout, QMainWindow
from re import findall
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing

import substance_painter as sp

import pipe
from pipe.db import DB
from pipe.glui.dialogs import ButtonPair, MessageDialog
from pipe.sp.export import Exporter, TexSetExportSettings
from pipe.sp.local import get_main_qt_window
from pipe.struct.db import Asset
from pipe.struct.material import DisplacementSource, NormalSource, NormalType
from pipe.util import dict_index

from env_sg import DB_Config

log = logging.getLogger(__name__)


def _checkbox_callback_helper(
    checkbox: QtWidgets.QCheckBox, widget: QtWidgets.QWidget
) -> typing.Callable[[], None]:
    def inner() -> None:
        widget.setEnabled(checkbox.isChecked())

    return inner


class SubstanceExportWindow(QMainWindow, ButtonPair):
    _asset: Asset
    _central_widget: QtWidgets.QWidget
    _conn: DB
    _main_layout: QLayout
    _mat_var_dropdown: QComboBox
    # _mat_var_enabled: QtWidgets.QCheckBox
    _metadataManager: pipe.sp.metadata.MetadataUpdater
    _srgbChecker: pipe.sp.channels.sRGBChecker
    _tex_set_dict: typing.Mapping[sp.textureset.TextureSet, "TexSetWidget"]
    _tex_set_widgets: list["TexSetWidget"]

    def __init__(
        self,
        flags: QtCore.Qt.WindowFlags | None = None,
    ) -> None:
        super(SubstanceExportWindow, self).__init__(get_main_qt_window())

        self._tex_set_dict = {}
        self._tex_set_widgets = []

        if not self._preflight():
            MessageDialog(
                get_main_qt_window(),
                (
                    "Your file has failed preflight checks. Please follow the "
                    "instructions to fix them when you first open this window."
                ),
                "Preflight failed.",
            ).exec_()
            return

        self._conn = DB.Get(DB_Config)
        metadata = sp.project.Metadata("LnD")
        asset = self._conn.get_asset_by_id(int(metadata.get("asset_id")))
        assert asset is not None
        self._asset = asset

        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("LnD Publish Textures")

        # Make sure window always stays on top
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        # Set up main layout
        self._central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self._central_widget)
        self._main_layout = QtWidgets.QVBoxLayout()
        self._central_widget.setLayout(self._main_layout)

        # title
        title = QLabel("Publish Textures")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self._main_layout.addWidget(title, 0)

        # File lock warning
        lock_warning = QLabel(
            '<a style="color: orangered"><b>WARNING:</b></a> If you '
            "currently have this asset open in Houdini on Windows, you "
            '<b>MUST</b> stop your render and press "Reset Renderman RIS / '
            'XPU" before exporting or TEX file conversion will not work!'
        )
        lock_warning.setWordWrap(True)
        self._main_layout.addWidget(lock_warning)

        # Texture set widgets
        texture_set_layout = QtWidgets.QVBoxLayout()
        for ts in sp.textureset.all_texture_sets():
            widget = TexSetWidget(self, ts)
            self._tex_set_dict[ts] = widget
            texture_set_layout.addWidget(widget)

        texture_set_widget = QtWidgets.QWidget()
        texture_set_widget.setLayout(texture_set_layout)
        texture_set_scroll_area = QtWidgets.QScrollArea()
        texture_set_scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff
        )
        texture_set_scroll_area.setWidget(texture_set_widget)
        texture_set_scroll_area.setWidgetResizable(True)
        self._main_layout.addWidget(texture_set_scroll_area)

        # Material Variants
        mat_var_widget = QtWidgets.QWidget()
        mat_var_layout = QtWidgets.QHBoxLayout(mat_var_widget)
        mat_var_layout.setContentsMargins(0, 0, 0, 0)
        mat_var_layout.setSpacing(0)
        mat_var_settings_widget = QtWidgets.QWidget()
        mat_var_settings_layout = QtWidgets.QHBoxLayout(mat_var_settings_widget)
        mat_var_label = QLabel("Material Variant:")
        mat_var_settings_layout.addWidget(mat_var_label, 30)
        self._mat_var_dropdown = QComboBox()
        mv_set = set(self._asset.material_variants)
        mv_set.add("default")
        mv_items = list(mv_set)
        self._mat_var_dropdown.addItems(mv_items)
        self._mat_var_dropdown.setCurrentText("default")
        self._mat_var_dropdown.setEditable(True)
        mat_var_validator = QRegExpValidator("[a-z][a-z_\d]*")
        self._mat_var_dropdown.setValidator(mat_var_validator)
        mat_var_settings_layout.addWidget(self._mat_var_dropdown, 70)
        mat_var_layout.addWidget(mat_var_settings_widget, 90)
        self._main_layout.addWidget(mat_var_widget)

        # Buttons
        self._init_buttons(has_cancel_button=True, ok_name="Export")
        self.buttons.rejected.connect(self.close)
        # self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.do_export)
        self._main_layout.addWidget(self.buttons)

    def _preflight(self) -> bool:
        """Check for asset metadata and correct channel types before running
        the export"""
        metaUpdater = pipe.sp.metadata.MetadataUpdater()
        srgbChecker = pipe.sp.channels.sRGBChecker()
        meta = metaUpdater.check() or metaUpdater.do_update()
        srgb = srgbChecker.check() or srgbChecker.prompt_srgb_fix()
        return meta and srgb

    @property
    def mat_var(self) -> str:
        return self._mat_var_dropdown.currentText()

    def do_export(self) -> None:
        if self.mat_var not in self._asset.material_variants:
            self._asset.material_variants.add(self.mat_var)
            log.info(f"Updating new material variant: {self.mat_var}")
            self._conn.update_asset(self._asset)

        log.info("Exporting!")
        exporter = Exporter()
        if exporter.export(
            [
                TexSetExportSettings(
                    ts,
                    wgt.extra_channels,
                    wgt.resolution,
                    wgt.displacement_source,
                    wgt.normal_type,
                    wgt.normal_source,
                )
                for ts, wgt in self._tex_set_dict.items()
                if wgt.enabled
            ],
            self.mat_var,
        ):
            MessageDialog(
                get_main_qt_window(),
                "Textures successfully exported!",
            ).exec_()
        else:
            MessageDialog(
                get_main_qt_window(),
                (
                    "An error occured while exporting textures. Please check the "
                    "console for more information"
                ),
            ).exec_()

        self.close()


class TexSetWidget(QtWidgets.QWidget):
    extra_channels: set[sp.textureset.Channel]

    _displacement_source_dropdown: QComboBox
    _enabled_checkbox: QtWidgets.QCheckBox
    _extra_channels_layout: QLayout
    _help_icon: QIcon
    _parent_window: SubstanceExportWindow
    _normal_source_dropdown: QComboBox
    _normal_type_dropdown: QComboBox
    _resolution_dropdown: QComboBox
    _settings_container: QtWidgets.QWidget
    _stack: sp.textureset.Stack
    _tex_set: sp.textureset.TextureSet

    DEFAULT_CHANNELS = [
        sp.textureset.ChannelType.BaseColor,
        sp.textureset.ChannelType.Height,
        sp.textureset.ChannelType.Roughness,
        sp.textureset.ChannelType.Opacity,
        sp.textureset.ChannelType.Emissive,
        sp.textureset.ChannelType.Metallic,
        sp.textureset.ChannelType.Normal,
        sp.textureset.ChannelType.Displacement,
    ]

    _NORM_TYPE_STRS = {
        NormalType.STANDARD: "Standard (default)",
        NormalType.BUMP_ROUGHNESS: "Bump Roughness",
    }

    _NORM_SOURCE_STRS = {
        NormalSource.NORMAL_HEIGHT: "Normal + Height (default)",
        NormalSource.NORMAL_ONLY: "Normal Only",
    }

    _DISP_SOURCE_STRS = {
        DisplacementSource.NONE: "None (default)",
        DisplacementSource.HEIGHT: "Height",
        DisplacementSource.DISPLACEMENT: "Displacement",
    }

    def __init__(
        self,
        parent: SubstanceExportWindow,
        tex_set: sp.textureset.TextureSet,
        flags: QtCore.Qt.WindowFlags | None = None,
    ) -> None:
        super().__init__(parent)
        self.setParent(parent)
        self._parent_window = parent
        self._tex_set = tex_set
        self.extra_channels = set()
        self._help_icon = QIcon(
            QPixmap(os.getenv("PIPE_PATH", "") + "/lib/icon/material-help.svg")
        )

        try:
            self._stack = self._tex_set.get_stack()
        except ValueError:
            MessageDialog(
                get_main_qt_window(),
                (
                    "Warning! Could not get material stacks! You are doing "
                    "something cool with material layering. Please show this to "
                    "Scott so he can fix it."
                ),
            ).exec_()

        self._setup_ui()

    def _info_tooltip(self, message: str) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setIcon(self._help_icon)
        button.setStyleSheet("background-color: #00000000; border: none;")
        button.setToolTip(message)
        return button

    @staticmethod
    def _get_default(items: typing.Iterable[str]) -> str:
        return next((i for i in items if i.endswith("(default)")), "")

    def _setup_ui(self) -> None:
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(QtCore.Qt.AlignTop)

        # Enable/disable checkbox and set up layouts
        self._enabled_checkbox = QtWidgets.QCheckBox()
        self._enabled_checkbox.setChecked(True)
        self._enabled_checkbox.setStyleSheet("padding-top: 10px;")
        layout.addWidget(self._enabled_checkbox, 10, QtCore.Qt.AlignTop)
        settings_container = QtWidgets.QWidget()
        self._enabled_checkbox.toggled.connect(
            _checkbox_callback_helper(self._enabled_checkbox, settings_container)
        )
        settings_layout = QtWidgets.QGridLayout(settings_container)
        settings_layout.setSpacing(2)
        layout.addWidget(settings_container, 90)

        # Texture set title
        self.label = QLabel(self._tex_set.name())
        self.label.setStyleSheet("font-size: 11px; font-weight: bold;")
        settings_layout.addWidget(self.label, 0, 0, 1, 3)

        # Extra channels
        extra_channels = QtWidgets.QWidget()
        self._extra_channels_layout = QtWidgets.QHBoxLayout(extra_channels)
        if self._setup_extra_channel_layout():
            settings_layout.addWidget(QLabel("Extra Maps:"), 1, 0)
            settings_layout.addWidget(extra_channels)

        # Resolution selection
        settings_layout.addWidget(QLabel("Resolution:"), 2, 0)
        self._resolution_dropdown = QComboBox()
        self._resolution_dropdown.addItems(
            ["128", "256", "512", "1024", "2048", "4096"]
        )
        current_res_log2 = int(log2(self._tex_set.get_resolution().width))
        self._resolution_dropdown.setCurrentIndex(current_res_log2 - 7)
        settings_layout.addWidget(self._resolution_dropdown)

        # Normal map source
        settings_layout.addWidget(QLabel("Normal Map Source:"), 3, 0)
        self._normal_source_dropdown = QComboBox()
        ns_items = self._NORM_SOURCE_STRS.values()
        self._normal_source_dropdown.addItems(ns_items)
        self._normal_source_dropdown.setCurrentText(self._get_default(ns_items))
        settings_layout.addWidget(self._normal_source_dropdown)
        settings_layout.addWidget(
            self._info_tooltip(
                "Substance's default behavior is to convert the Height channel "
                "to a normal map, then combine it with the Normal channel. \n"
                '"Normal + Height" keeps this behavior. \n'
                '"Normal Only" does not combine in the Height channel.'
            )
        )

        # Normal map type
        settings_layout.addWidget(QLabel("Normal Map Type:"), 4, 0)
        self._normal_type_dropdown = QComboBox()
        nt_items = self._NORM_TYPE_STRS.values()
        self._normal_type_dropdown.addItems(nt_items)
        self._normal_type_dropdown.setCurrentText(self._get_default(nt_items))
        settings_layout.addWidget(self._normal_type_dropdown)
        settings_layout.addWidget(
            self._info_tooltip(
                "Bump Roughness mapping preserves detail in shiny items with "
                "variance/breakup in the roughness (i.e. scratches, smudges, "
                "etc.). \n"
                "Select Bump Roughness if your texture set is a shiny "
                "material with variance/breakup in the roughness. Otherwise, "
                "leave it on Standard."
            )
        )

        # Displacement map source
        settings_layout.addWidget(QLabel("Displacement Map Source:"), 5, 0)
        self._displacement_source_dropdown = QComboBox()
        ds_items = list(self._DISP_SOURCE_STRS.values())
        self._displacement_source_dropdown.addItems(ds_items)
        self._displacement_source_dropdown.setCurrentText(self._get_default(ds_items))
        if sp.textureset.ChannelType.Displacement in self._stack.all_channels().keys():
            self._displacement_source_dropdown.setCurrentText(
                self._DISP_SOURCE_STRS[DisplacementSource.DISPLACEMENT]
            )
        else:
            self._displacement_source_dropdown.removeItem(
                ds_items.index(self._DISP_SOURCE_STRS[DisplacementSource.DISPLACEMENT])
            )
        settings_layout.addWidget(self._displacement_source_dropdown)
        settings_layout.addWidget(
            self._info_tooltip(
                "Displacement is expensive and should only be used on assets "
                "that will be close enough to the camera that the changes to "
                "the silhouette will be noticeable. You can source the "
                "displacement map from the Height channel, or from the "
                "Displacement channel."
            )
        )

        self.setLayout(layout)

    def _setup_extra_channel_layout(self) -> bool:
        """Sets up extra channel layout. Returns False if there are no extra channels"""
        has_channels: bool = False
        for channel_type, channel in self._stack.all_channels().items():
            if channel_type not in self.DEFAULT_CHANNELS:
                # get channel name
                name = (
                    getattr(channel, "label", None)
                    and channel.label().title().replace(" ", "")
                    or channel.type().name
                )
                # add spaces
                name = " ".join(
                    findall(r"[A-Z0-9](?:[a-z0-9]+|[A-Z]*(?=[A-Z]|$))", name)
                )
                # set up checkboxes
                checkbox = QtWidgets.QCheckBox(name)
                checkbox.setChecked(False)
                checkbox.stateChanged.connect(self._extra_channels_updater(channel))
                self._extra_channels_layout.addWidget(checkbox)
                has_channels = True

        return has_channels

    def _extra_channels_updater(
        self, ch: sp.textureset.Channel
    ) -> typing.Callable[[], None]:
        """Callback function generator for extra channels checkboxes"""

        def inner() -> None:
            if ch in self.extra_channels:
                self.extra_channels.remove(ch)
            else:
                self.extra_channels.add(ch)

        return inner

    @property
    def enabled(self) -> bool:
        return self._enabled_checkbox.isChecked()

    @property
    def resolution(self) -> int:
        """Returns the resolution log 2"""
        return self._resolution_dropdown.currentIndex() + 7

    @property
    def normal_type(self) -> NormalType:
        return dict_index(
            self._NORM_TYPE_STRS, self._normal_type_dropdown.currentText()
        )

    @property
    def normal_source(self) -> NormalSource:
        return dict_index(
            self._NORM_SOURCE_STRS, self._normal_source_dropdown.currentText()
        )

    @property
    def displacement_source(self) -> DisplacementSource:
        return dict_index(
            self._DISP_SOURCE_STRS,
            self._displacement_source_dropdown.currentText(),
        )
