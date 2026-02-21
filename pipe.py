"""Dungeon pipeline."""

from __future__ import annotations

import atexit
import copy
import datetime
import filecmp
import hmac
import importlib
import importlib.util
import json
import logging
import logging as _l
import os
import platform
import random
import re
import shutil
import site
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
from abc import ABC, ABCMeta, abstractmethod
from argparse import ArgumentParser
from collections import defaultdict
from contextlib import closing, contextmanager, suppress
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from functools import partial, wraps
from functools import partialmethod as pm
from hashlib import sha1
from importlib import reload
from inspect import getmembers, isabstract, isclass, isfunction
from itertools import count
from math import ceil, floor, isclose, log2, sqrt
from os import environ as _e
from os import getenv as _getenv
from pathlib import Path
from re import findall
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Literal,
    Optional,
    Protocol,
    Type,
    TypedDict,
    TypeVar,
    Union,
    cast,
)
from urllib import request

import attrs
import cattrs
import dwpicker
import ffmpeg
import hou
import loptoolutils
import maya.api.OpenMaya as om
import maya.cmds as cmds
import maya.cmds as mc
import maya.mel as mel
import maya.OpenMayaUI as omUI
import mayaUsd
import mayaUsd.lib as mayaUsdLib
import nuke
import numpy as np
import studiolibrary
import substance_painter as sp
import substance_painter_plugins as spp
import tractor.api.author as author
from attr._make import _frozen_setattrs
from attrs import field
from env import PIPEBOT_SECRET, PIPEBOT_URL, Executables
from env import production_path as _prp
from env_sg import DB_Config
from filelock import FileLock
from maya import mel
from mayacapture.capture import capture
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdUtils, Vt
from Qt import QtCompat, QtCore, QtGui, QtWidgets
from Qt.QtCore import QRegExp
from Qt.QtGui import QIcon, QPixmap, QRegExpValidator, QTextCursor
from Qt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QSpinBox,
    QWidget,
)
from substance_painter import ui
from timeline_marker.ui import TimelineMarker
from typing_extensions import NotRequired, Unpack

if TYPE_CHECKING:
    import typing

"""Adapted/updated from 2024 (Accomplice) / 2022 (Cenote) pipelines"""

log = logging.getLogger(__name__)


class ButtonPair:
    buttons: QtWidgets.QDialogButtonBox

    def _init_buttons(
        self,
        has_cancel_button: bool,
        ok_name: str = "OK",
        cancel_name: str = "Cancel",
    ) -> None:
        button_list = QtWidgets.QDialogButtonBox.StandardButtons(
            QtWidgets.QDialogButtonBox.Ok
        )
        if has_cancel_button:
            button_list |= QtWidgets.QDialogButtonBox.Cancel
        self.buttons = QtWidgets.QDialogButtonBox(button_list)

        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setText(ok_name)

        if has_cancel_button:
            self.buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText(cancel_name)


class DialogButtons(ButtonPair):
    # stubs for attributes that will be on class this is inherited by
    buttons: QtWidgets.QDialogButtonBox
    accept: typing.Callable[..., None]
    reject: typing.Callable[..., None]

    def _init_buttons(self, has_cancel_button: bool, *args) -> None:
        super(DialogButtons, self)._init_buttons(has_cancel_button, *args)

        self.buttons.accepted.connect(self.accept)
        if has_cancel_button:
            self.buttons.rejected.connect(self.reject)


class DialogFilteredList:
    filtered_list: QtWidgets.QVBoxLayout
    _filter_field: QtWidgets.QLineEdit
    _list_label: QtWidgets.QLabel
    _list_widget: QtWidgets.QListWidget

    def _init_filtered_list(
        self,
        items: typing.Sequence[str],
        list_label: str | None = None,
        include_filter_field: bool | None = True,
    ) -> None:
        self.filtered_list = QtWidgets.QVBoxLayout()

        if list_label is not None:
            assert isinstance(list_label, str)
            self._list_label = QtWidgets.QLabel(list_label)
            self.filtered_list.addWidget(self._list_label)

        if include_filter_field:
            self._filter_field = QtWidgets.QLineEdit()
            self._filter_field.setPlaceholderText("Type here to filter...")
            self._filter_field.textChanged.connect(self._filter_items)
            self.filtered_list.addWidget(self._filter_field)

        self._list_widget = QtWidgets.QListWidget()
        self._list_widget.addItems(items)
        self.filtered_list.addWidget(self._list_widget)

    def _filter_items(self) -> None:
        filter_text = self._filter_field.text().lower()
        reg = re.compile(".*".join(["", *filter_text.split(), ""]))
        for row in range(self._list_widget.count()):
            item = self._list_widget.item(row)
            item_text = item.text().lower()
            if reg.match(item_text):
                item.setHidden(False)
            else:
                item.setHidden(True)

    def get_selected_item(self) -> str | None:
        selected_items = self._list_widget.selectedItems()
        if selected_items:
            return selected_items[0].text()
        return None


class MessageDialog(QtWidgets.QDialog, DialogButtons):
    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        message: str,
        title: str = "Message",
        /,
        has_cancel_button: bool = False,
    ) -> None:
        super(MessageDialog, self).__init__(parent)
        self._init_buttons(has_cancel_button)

        self.setParent(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel(message)
        layout.addWidget(label)

        layout.addWidget(self.buttons)

        self.setLayout(layout)


class MessageDialogCustomButtons(QtWidgets.QDialog, DialogButtons):
    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        message: str,
        title: str = "Message",
        /,
        has_cancel_button: bool = False,
        ok_name: str = "",
        cancel_name: str = "",
    ) -> None:
        super(MessageDialogCustomButtons, self).__init__(parent)
        self._init_buttons(has_cancel_button, ok_name, cancel_name)

        self.setParent(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel(message)
        layout.addWidget(label)

        layout.addWidget(self.buttons)

        self.setLayout(layout)


class FilteredListDialog(QtWidgets.QDialog, DialogButtons, DialogFilteredList):
    filter_field: QtWidgets.QLineEdit
    list_label: QtWidgets.QLabel
    list_widget: QtWidgets.QListWidget
    _layout: QtWidgets.QBoxLayout

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        items: typing.Sequence[str],
        title: str = "Filtered List",
        list_label: str | None = None,
        include_filter_field: bool | None = True,
        accept_button_name: str | None = "OK",
        reject_button_name: str | None = "Cancel",
    ) -> None:
        super(FilteredListDialog, self).__init__(parent)
        self._init_buttons(True, accept_button_name, reject_button_name)
        self._init_filtered_list(items, list_label, include_filter_field)

        self.setParent(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

        self.resize(500, 600)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.addLayout(self.filtered_list)
        self._layout.addWidget(self.buttons)


# class DialogFactory:
#     main_window: Type["QtWidgets.QWidget"]

#     def __init__(self, main_window: Type["QtWidgets.QWidget"]):
#         self.main_window = main_window

#     def message(
#         self,
#         msg: str = " ",
#         details: str | None = None,
#         title: str | None = "Message",
#     ) -> None:
#         """Reports a message"""
#         log.info(msg)

#         msgBox = QtWidgets.QMessageBox()
#         msgBox.setText(msgBox.tr(msg))
#         if title == "Warning":
#             msgBox.setIcon(QtWidgets.QMessageBox.Warning)
#         elif title == "Error":
#             msgBox.setIcon(QtWidgets.QMessageBox.Critical)
#         else:
#             msgBox.setIcon(QtWidgets.QMessageBox.Information)
#         msgBox.setWindowTitle(title)
#         msgBox.addButton(QtWidgets.QMessageBox.Ok)

#         if details is not None:
#             msgBox.setDetailedText(str(details))

#         msgBox.exec_()

#     def error(
#         self, errMsg: str, details: str | None = None, title: str | None = "Error"
#     ) -> None:
#         """Reports a critical error"""
#         self.message(errMsg, details=details, title=title)

#     def warning(
#         self,
#         warnMsg: str,
#         details: str | None = None,
#         title: str | None = "Warning",
#     ) -> None:
#         """Reports a non-critical warning"""
#         self.message(warnMsg, details=details, title=title)

#     def info(self, infoMsg: str, title: str | None = "Info") -> None:
#         """Reports an informational message"""
#         self.message(msg=infoMsg, title=title)

#     def yes_or_no(
#         self,
#         question: str,
#         details: str | None = None,
#         title: str | None = "Question",
#     ) -> bool:
#         """Asks a question that can be resolved with a yes or no
#         returns True if yes, otherwise False"""
#         msgBox = QtWidgets.QMessageBox()
#         msgBox.setText(msgBox.tr(question))
#         msgBox.setWindowTitle(title)
#         if title == "Question":
#             msgBox.setIcon(QtWidgets.QMessageBox.Question)
#         else:
#             msgBox.setIcon(QtWidgets.QMessageBox.Warning)
#         noButton = msgBox.addButton(QtWidgets.QMessageBox.No)
#         yesButton = msgBox.addButton(QtWidgets.QMessageBox.Yes)

#         if details is not None:
#             msgBox.setDetailedText(details)

#         msgBox.exec_()

#         if msgBox.clickedButton() == yesButton:
#             return True
#         elif msgBox.clickedButton() == noButton:
#             return False

#     def input(
#         self, label: str, title: str | None = "Input", text: str | None = None
#     ) -> str | None:
#         """
#         Allows the user to respond with a text input
#         If the okay button is pressed it returns the inputed text, otherwise None
#         """
#         dialog = QtWidgets.QInputDialog()
#         text = dialog.getText(None, title, label, text=text)

#         if text[1]:
#             return text[0]
#         else:
#             return None

#     def choose_file(
#         self,
#         dir: str = str(get_pipe_path()),
#         filter: str = "All Files (*)",
#         caption=None,
#         parent=None,
#     ) -> Path:
#         """
#         Allows the user to select a file location
#         """
#         if parent is None:
#             parent = self.main_window

#         fileName, _ = QtWidgets.QFileDialog.getOpenFileName(
#             parent, caption, dir, filter
#         )
#         return Path(fileName).resolve()

#     def


# class HoudiniInput(QtWidgets.QDialog):
#     '''
#     submitted is a class variable that must be instantiated outside of __init__
#     in order for the Signal to be created correctly.
#     Have to use this instead of input in houdini to avoid black text on black bar
#     '''
#     submitted = QtCore.Signal(list)

#     def __init__(self, parent=None, title="Enter info", info="", width=350, height=75):
#         super(HoudiniInput, self).__init__(parent)

#         self.info = info
#         if parent:
#             self.parent = parent
#         self.setWindowTitle(title)
#         self.setObjectName('HoudiniInput')
#         self.resize(width, height)
#         self.initializeVBox()
#         self.setLayout(self.vbox)
#         self.show()

#     def initializeVBox(self):
#         self.vbox = QtWidgets.QVBoxLayout()
#         # QApplication.setActiveWindow()
#         self.initializeInfoText()
#         self.initializeTextBar()
#         self.initializeSubmitButton()

#     def initializeInfoText(self):
#         info_text = QtWidgets.QLabel()
#         info_text.setText(self.info)
#         self.vbox.addWidget(info_text)

#     def initializeTextBar(self):
#         hbox = QtWidgets.QHBoxLayout()
#         self.text_input = QtWidgets.QLineEdit()
#         self.text_input.setStyleSheet(
#             "color: white; selection-color: black; selection-background-color: white;")
#         self.text_input.textEdited.connect(self.textEdited)
#         self.text_input.setFocus()
#         hbox.addWidget(self.text_input)
#         self.vbox.addLayout(hbox)

#     def initializeSubmitButton(self):
#         # Create the button widget
#         self.button = QtWidgets.QPushButton("Confirm")
#         self.button.setDefault(True)
#         self.button.setSizePolicy(
#             QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
#         self.button.clicked.connect(self.submit)
#         self.button.setEnabled(False)
#         self.vbox.addWidget(self.button)

#     def textEdited(self, newText):
#         if len(newText) > 0:
#             self.button.setEnabled(True)
#             self.button.setDefault(True)
#         else:
#             self.button.setEnabled(False)

#         self.values = newText

#     def setButtonIcon(self, frame):
#         '''Get the current state of the loading indicator gif as an icon'''
#         icon = QtGui.QIcon(self.movie.currentPixmap())
#         self.button.setIcon(icon)

#     def submit(self):
#         '''
#             Send the selected values to a function set up in the calling class and
#             close the window. Use connect() on submitted to set up the receiving func.
#         '''
#         print('comment input: ' + self.values + '\n')
#         self.button.setText("Loading...")
#         icon_path = str(get_pipe_path() / "lib/icon/loading.gif")
#         self.movie = QtGui.QMovie(icon_path)
#         self.movie.frameChanged.connect(self.setButtonIcon)
#         if not self.movie.loopCount() == -1:
#             self.movie.finished().connect(self.movie.start())
#         self.movie.start()
#         self.button.setEnabled(False)
#         self.submitted.emit(self.values)
#         self.close()


class VersionWindow(QtWidgets.QMainWindow):
    """
    I don't think this was ever used.
    """

    def __init__(self, parent):  # =hou.qt.mainWindow()):
        super(VersionWindow, self).__init__(parent)
        # you're going to have to set the parent explicitly when you call this function
        # because importing hou raises an error when this runs in maya

        # Function to build the UI
        # Create main widget
        main_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(main_widget)

        # Initialize the layout
        global_layout = QtWidgets.QVBoxLayout()
        layout = QtWidgets.QFormLayout()
        main_widget.setLayout(global_layout)

        # Create Controls - Display Current Version
        self.current_version_label = QtWidgets.QLabel()
        self.current_version_label.setMinimumWidth(300)
        # Create Controls - Display Library Path
        self.current_path_label = QtWidgets.QLabel()
        # Create Controls - Display Divider
        line = QtWidgets.QFrame()
        line.setFrameStyle(QtWidgets.QFrame.HLine | QtWidgets.QFrame.Sunken)
        # Create Controls - Major version int editor
        self.major_version = QtWidgets.QSpinBox()
        # Create Controls - Minor version int editor
        self.minor_version = QtWidgets.QSpinBox()
        # Create Controls - custom spin box that supports a zero padded syntax for integers (001 instead of 1)
        self.revision_version = PaddedSpinBox()
        # Create Controls - Create New Version button
        self.set_version = QtWidgets.QPushButton("Create New Version")

        # Add controls to layout and set label
        layout.addRow("Current Version:", self.current_version_label)
        layout.addRow("Library Path:", self.current_path_label)
        layout.addRow(line)
        layout.addRow("Major Version:", self.major_version)
        layout.addRow("Minor Version:", self.minor_version)
        layout.addRow("Revision Version:", self.revision_version)

        # Global layout setting
        global_layout.addLayout(layout)
        global_layout.addWidget(self.set_version)


# PySide2 UI - custom QSpinBox that supports a zero padded syntax
# Subclass PySide2.QtWidgets.QSpinBox
class PaddedSpinBox(QtWidgets.QSpinBox):
    def __init__(self, parent=None):
        super(PaddedSpinBox, self).__init__(parent)

    # Custom format of the actual value returned from the text
    def valueFromText(self, text):
        regExp = QtCore.QRegExp(("(\\d+)(\\s*[xx]\\s*\\d+)?"))

        if regExp.exactMatch(text):
            return regExp.cap(1).toInt()
        else:
            return 0

    # Custom format of the text displayed from the value
    def textFromValue(self, value):
        return str(value).zfill(3)


# def large_input(label, title='Input', text=None):
#     '''
#     Allows the user to respond with a larger text input
#     If the okay button is pressed it returns the inputed text, otherwise None
#     '''

#     dialog = QtWidgets.QTextEdit()
#     # dialog.setCancelButtonText("Skip")toPlainText
#     text = dialog.toPlainText(None, title, label, text=text)

#     if text[1]:
#         return text[0]
#     else:
#         return None


class CheckboxSelect(QtWidgets.QDialog):
    submitted = QtCore.Signal(list)

    def __init__(self, text, options, title="", parent=None):
        """Creates check box options based on the given list of strings"""
        """returns a list of booleans, each one correstponding to its respective option"""
        super(CheckboxSelect, self).__init__(parent=parent)

        # window = QtWidgets.QDialog(parent=parent)
        # self.setWindowTitle(title)

        self.layout = QtWidgets.QVBoxLayout()

        label = QtWidgets.QLabel()
        label.setText(text)
        self.layout.addWidget(label)

        self.boxes = []

        for option in options:
            print(option)
            newBox = QtWidgets.QCheckBox()
            newBox.setText(option)
            newBox.setChecked(True)
            self.boxes.append(newBox)
            self.layout.addWidget(newBox)

        self.initializeSubmitButton()

        self.setLayout(self.layout)
        self.show()

    def initializeSubmitButton(self):
        self.button = QtWidgets.QPushButton("Accept")
        self.button.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum
        )
        self.button.clicked.connect(self.submit)
        self.layout.addWidget(self.button)

    def submit(self):
        values = []
        for box in self.boxes:
            values.append(box.isChecked())
        self.submitted.emit(values)
        self.close()


# class ShotSelectDialog(QtWidgets.QDialog):
#     """A dialog that allows the user to select a shot. The selected shot can be
#     accessed with the selectedShot() method"""

#     def __init__(self):
#         super(ShotSelectDialog, self).__init__()

#         self.env = env()
#         self.baseDir = os.path.abspath(os.path.join(self.env.project_dir, os.pardir, "Editing", "Animation"))

#         self.sequences = self.gettyping.Sequences()
#         self.shots = []

#         self.setupUI()

#     def setupUI(self):
#         self.setWindowTitle("Choose a shot")
#         self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
#         self.setFixedSize(325, 200)

#         self.setLayout(QtWidgets.QVBoxLayout())
#         self.mainLayout = self.layout()

#         self.searchBar = QtWidgets.QLineEdit()
#         self.searchBar.setPlaceholderText("Search")
#         self.searchBar.textChanged.connect(self.search)
#         self.mainLayout.addWidget(self.searchBar)

#         # LISTS
#         self.listLayout = QtWidgets.QHBoxLayout()
#         self.mainLayout.addLayout(self.listLayout)

#         self.sequenceLayout = QtWidgets.QVBoxLayout()
#         self.listLayout.addLayout(self.sequenceLayout)

#         self.sequenceLabel = QtWidgets.QLabel("typing.Sequences")
#         self.sequenceLabel.setAlignment(QtCore.Qt.AlignCenter)
#         self.sequenceLayout.addWidget(self.sequenceLabel)

#         self.sequenceListWidget = QtWidgets.QListWidget()
#         self.sequenceListWidget.setFixedWidth(150)
#         self.sequenceListWidget.addItems(self.sequences)
#         self.sequenceLayout.addWidget(self.sequenceListWidget)

#         self.shotLayout = QtWidgets.QVBoxLayout()
#         self.listLayout.addLayout(self.shotLayout)

#         self.shotLabel = QtWidgets.QLabel("Shots")
#         self.shotLabel.setAlignment(QtCore.Qt.AlignCenter)
#         self.shotLayout.addWidget(self.shotLabel)

#         self.shotListWidget = QtWidgets.QListWidget()
#         self.shotListWidget.setFixedWidth(150)
#         self.shotListWidget.addItems(self.shots)
#         self.shotLayout.addWidget(self.shotListWidget)

#         self.sequenceListWidget.itemClicked.connect(self.updateUI)

#         # BUTTONS
#         self.buttonLayout = QtWidgets.QHBoxLayout()
#         self.mainLayout.addLayout(self.buttonLayout)

#         self.exportButton = QtWidgets.QPushButton("OK")
#         self.exportButton.clicked.connect(self.close)
#         self.exportButton.clicked.connect(self.accept)
#         self.buttonLayout.addWidget(self.exportButton)

#         self.cancelButton = QtWidgets.QPushButton("Cancel")
#         self.buttonLayout.addWidget(self.cancelButton)

#         self.cancelButton.clicked.connect(self.close)
#         self.cancelButton.clicked.connect(self.reject)

#     def updateUI(self):
#         self.shotListWidget.clear()
#         self.shotListWidget.addItems(self.getShots())

#     def search(self):
#         search = self.searchBar.text()
#         self.sequenceListWidget.clear()
#         self.shotListWidget.clear()
#         if search == "":
#             self.sequenceListWidget.addItems(self.sequences)
#             self.shotListWidget.addItems(self.shots)
#         else:
#             self.sequenceListWidget.addItems([s for s in self.sequences if search in s])
#             self.shotListWidget.addItems([s for s in self.getAllShots() if search in s])

#     def gettyping.Sequences(self):
#         """Returns an alphabetically sorted list of sequences in the project.
#         @return: list of sequences"""

#         sequences = [d for d in os.listdir(self.baseDir) if d.startswith(("SEQ"))]
#         sequences.sort()
#         return sequences

#     def getShots(self):
#         """Returns a list of shots in the current sequence. Returns an empty list if no sequence is selected.
#         @return: list of shots"""

#         if self.sequenceListWidget.currentItem() is None:
#             return []

#         currenttyping.Sequence = self.sequenceListWidget.currentItem().text()[-1]
#         # shots = os.listdir(os.path.join(self.baseDir, currenttyping.Sequence))
#         shots = os.listdir(self.env.get_shot_dir())
#         shots = [shot for shot in shots if shot.startswith(currenttyping.Sequence)]
#         shots.sort()
#         return shots

#     def getAllShots(self):
#         shots = os.listdir(self.env.get_shot_dir())
#         shots.sort()
#         return shots

#     def selectedShot(self):
#         """Returns the currently selected shot, or None if no shot is selected."""

#         if self.shotListWidget.currentItem() is None:
#             return None

#         currentShot = self.shotListWidget.currentItem().text()
#         return currentShot


# mypy: disable-error-code="union-attr"


if TYPE_CHECKING:
    from typing import Optional


"""Scripts for building node setups. Called by lnd_nodelayouts.hdanc in Interactive > Shelf Tools, also make sure to check a network context in the context tab"""


def lnd_clustersetup(kwargs: dict, parent: Optional[hou.Node] = None) -> hou.Node:
    out: hou.LopNode = loptoolutils.genericTool(kwargs, "componentoutput")
    out.setColor(hou.Color((0.616, 0.871, 0.769)))

    out_pos = out.position()

    # This is the context within the out node exists, which should be the stage context
    p = out.parent()

    # Fetches the other nodes
    ldv = p.createNode("sdm223::dev::LnD_Lookdev")
    prim = p.createNode("primitive")
    graft = p.createNode("graftstages")
    env = p.createNode("fetch")
    err = p.createNode("error")

    # Establishes Connections
    out.setInput(0, graft)
    graft.setInput(0, err)
    err.setInput(0, prim)
    ldv.setInput(0, out)
    out.setInput(1, env)

    # Arrange nodes in "Y" shape
    err_move = hou.Vector2(-1.22, 2.3)
    prim_move = hou.Vector2(-1.22, 3.5)
    graft_move = hou.Vector2(0.0, 1.0)
    ldv_move = hou.Vector2(0.0, -1.0)
    env_move = hou.Vector2(1.5, 0.5)
    prim.setPosition(prim_move + out_pos)
    err.setPosition(err_move + out_pos)
    graft.setPosition(graft_move + out_pos)
    ldv.setPosition(ldv_move + out_pos)
    env.setPosition(env_move + out_pos)

    # Configure environment fetch
    env.parm("loppath").set(f"../{ldv.name()}/OUT_ENV")

    # Configure Component Output node
    out.parm("mode").set(1)
    out.parm("doclassinherit").set(False)
    out.parm("lopoutput").set('$HIP/export/`chs("filename")`')
    graft.parm("destpath").set("/")
    prim.parm("primpath").set("$OS")
    out.parm("rootprim").set("`lopinputprim('.', 0)`")
    err.parm("errormsg1").set("Please name your primitive node")
    err.parm("severity1").set("error")

    error_expression = 'import re\nrgx = re.compile("primitive[0-9]+")\nreturn any(rgx.match(node.name()) for node in hou.pwd().inputAncestors())'
    err.parm("enable1").setExpression(
        error_expression, language=hou.exprLanguage.Python
    )

    # Set the Component Output as Selected
    out.setCurrent(True)
    out.setSelected(True, clear_all_selected=True)

    return out


def lnd_componentgeometry(kwargs: dict, parent: Optional[hou.Node] = None) -> hou.Node:
    if parent:
        cgeo = parent.createNode("componentgeometry")
    else:
        cgeo = loptoolutils.genericTool(kwargs, "componentgeometry")

    # Set up nodes inside of Component Geometry
    geo_sop = cgeo.node("./sopnet/geo")
    geo_sop.loadItemsFromFile(
        hou.hscriptStringExpression("$HSITE") + "/sop/component.cpio"
    )
    for name in ["default", "proxy", "simproxy"]:
        geo_sop.node(f"./{name}").setInput(0, geo_sop.node(f"./OUT_{name}"))

    # Configure Component Geometry node
    cgeo.parm("dogeommodelapi").set(True)
    cgeo.parm("attribs").set("P uv")
    cgeo.parm("indexattribs").set("texset")

    cgeo.setColor(hou.Color((0.616, 0.871, 0.769)))

    return cgeo


def lnd_componentmaterial(kwargs: dict, parent: Optional[hou.Node] = None) -> hou.Node:
    MAT_ROOT = "/ASSET/mtl/MAT_"
    TS_PRIMVAR = "texset"

    if parent:
        cmat = parent.createNode("componentmaterial")
    else:
        cmat = loptoolutils.genericTool(kwargs, "componentmaterial")

    # configure component material node
    cmat.parm("variantname").set("`chs(opinputpath('.', 1)/mat_var)`")

    # set up primvar-based material assignment
    edit = cmat.node("./edit")
    assign = edit.createNode("assignmaterial")
    assign.setInput(0, edit.indirectInputs()[0])
    edit.node("./output0").setInput(0, assign)
    assign.parm("primpattern1").set(
        "%descendants(`lopinputprims('.', 0)`) & %type:Mesh"
    )
    assign.parm("matspecmethod1").set("vexpr")
    assign.parm("matspecvexpr1").set(
        f"return '{MAT_ROOT}' + usd_primvarelement(0, @primpath, '{TS_PRIMVAR}', usd_primvarindices(0, @primpath, '{TS_PRIMVAR}')[@elemnum]);"
    )
    assign.parm("geosubset1").set(True)

    cmat.setColor(hou.Color((0.616, 0.871, 0.769)))

    return cmat


def lnd_componentsetup(kwargs: dict) -> hou.Node:
    out: hou.LopNode = loptoolutils.genericTool(kwargs, "componentoutput")
    out.setColor(hou.Color((0.616, 0.871, 0.769)))

    out_pos = out.position()
    p = out.parent()
    geo = lnd_componentgeometry(kwargs, parent=p)
    mtl = lnd_componentmaterial(kwargs, parent=p)
    lib = p.createNode("sdm223::main::LnD_MatLib")
    cnf = p.createNode("sdm223::lnd_componentconfig")
    ldv = p.createNode("sdm223::dev::LnD_Lookdev")
    env = p.createNode("fetch")
    out.setInput(0, cnf)
    out.setInput(1, env)
    cnf.setInput(0, mtl)
    mtl.setInput(0, geo)
    mtl.setInput(1, lib)
    ldv.setInput(0, out)

    # Arrange nodes in "Y" shape
    geo_move = hou.Vector2(-1.22, 3.5)
    mtl_move = hou.Vector2(0.0, 2.0)
    lib_move = hou.Vector2(1.22, 3.0)
    cnf_move = hou.Vector2(0.0, 1.0)
    ldv_move = hou.Vector2(0.0, -1.0)
    env_move = hou.Vector2(1.5, 0.5)
    geo.setPosition(geo_move + out_pos)
    mtl.setPosition(mtl_move + out_pos)
    lib.setPosition(lib_move + out_pos)
    cnf.setPosition(cnf_move + out_pos)
    ldv.setPosition(ldv_move + out_pos)
    env.setPosition(env_move + out_pos)

    # Configure environment fetch
    env.parm("loppath").set(f"../{ldv.name()}/OUT_ENV")

    # Configure Component Output node
    asset_name = hou.hscriptStringExpression("$HIP").split("/")[-1]
    out.parm("rootprim").set("/" + asset_name)
    out.parm("localize").set(False)
    out.parm("lopoutput").set('$HIP/export/`chs("filename")`')
    out.parm("thumbnailmode").set(2)
    out.parm("renderer").set("RenderMan RIS")
    out.parm("thumbnailscenesource").set(1)
    out.parm("thumbnailinputcamera").set("/lookdev/cam")

    # Set Geometry as last selected
    geo.setSelected(True, clear_all_selected=True)

    return out


def _hide_contextoptions_folders(node: hou.Node) -> None:
    ptg = node.parmTemplateGroup()
    for f in ("Basic Options", "Time Based Options", "Pattern Matching Options"):
        ptg.hideFolder(f, True)
    node.setParmTemplateGroup(ptg)


def lnd_layoutgroup(kwargs: dict) -> hou.Node:
    contextoptions: hou.LopNode = loptoolutils.genericTool(kwargs, "editcontextoptions")

    pos = contextoptions.position()
    p = contextoptions.parent()
    beginblock = p.createNode("begincontextoptionsblock")
    groupprim = p.createNode("primitive")

    if old_inputs := contextoptions.inputs():
        beginblock.setInput(0, old_inputs[0])
    contextoptions.setInput(0, groupprim)
    contextoptions.parm("createoptionsblock").set(True)
    groupprim.setInput(0, beginblock)

    for n in (beginblock, groupprim, contextoptions):
        n.setColor(hou.Color(0.565, 0.494, 0.863))

    groupprim.setUserData("nodeshape", "chevron_down")
    contextoptions.setUserData("nodeshape", "chevron_up")

    beginblock.setName("beginlayoutgroup", True)
    groupprim.setName("layoutprim", True)
    contextoptions.setName("layoutgroup", True)

    groupprim.parm("primpath").set("`@PATH`")
    groupprim.parm("primkind").set("Group")
    groupprim.parm("parentprimtype").set("Scope")

    contextoptions.addSpareParmTuple(
        hou.StringParmTemplate(
            name="group", label="Group Name", num_components=1, default_value=("$OS",)
        )
    )
    contextoptions.parm("optioncount").insertMultiParmInstance(0)
    contextoptions.parm("optionname1").set("GROUP")
    contextoptions.parm("optionstrvalue1").set('`chs("./group")`')
    contextoptions.parm("optionname2").set("PATH")
    contextoptions.parm("optionstrvalue2").set(
        '/environment/`@ASSEMBLY`/`chs("./group")`'
    )

    contextoptions.parm("createoptionsblock").hide(True)
    _hide_contextoptions_folders(contextoptions)

    beginblock_move = hou.Vector2(0, 2.0)
    groupprim_move = hou.Vector2(0, 1.5)
    beginblock.setPosition(beginblock_move + pos)
    groupprim.setPosition(groupprim_move + pos)

    return contextoptions


def lnd_layout(kwargs: dict) -> hou.Node:
    contextoptions: hou.Node = loptoolutils.genericTool(kwargs, "editcontextoptions")

    pos = contextoptions.position()
    p = contextoptions.parent()
    envprim = p.createNode("primitive")
    layoutprim = p.createNode("primitive")
    merge = p.createNode("merge")

    contextoptions.setInput(0, merge)
    merge.setInput(0, layoutprim)
    layoutprim.setInput(0, envprim)

    contextoptions.setName("layout_name", True)
    envprim.setName("environment_xform", True)
    layoutprim.setName("assembly_prim", True)

    for n in (contextoptions, envprim, layoutprim, merge):
        n.setColor(hou.Color(0.188, 0.529, 0.45))

    envprim.setUserData("nodeshape", "chevron_down")
    layoutprim.setUserData("nodeshape", "chevron_down")
    contextoptions.setUserData("nodeshape", "chevron_up")

    envprim.parm("primpath").set("/environment")
    envprim.parm("parentprimtype").set("None")
    envprim.parm("primtype").set("UsdGeomXform")

    layoutprim.parm("primpath").set("`@PATH`")
    layoutprim.parm("primkind").set("Assembly")
    layoutprim.parm("parentprimtype").set("UsdGeomXform")

    contextoptions.addSpareParmTuple(
        hou.StringParmTemplate(
            name="assembly",
            label="Assembly Name",
            num_components=1,
            default_value=("$OS",),
        )
    )
    contextoptions.parm("optioncount").insertMultiParmInstance(0)
    contextoptions.parm("optionname1").set("ASSEMBLY")
    contextoptions.parm("optionstrvalue1").set('`chs("./assembly")`')
    contextoptions.parm("optionname2").set("PATH")
    contextoptions.parm("optionstrvalue2").set('/environment/`chs("./assembly")`')

    contextoptions.parm("createoptionsblock").hide(True)
    _hide_contextoptions_folders(contextoptions)

    envprim_move = hou.Vector2(0, 6.7)
    layoutprim_move = hou.Vector2(0, 6.0)
    merge_move = hou.Vector2(0, 1.0)
    envprim.setPosition(envprim_move + pos)
    layoutprim.setPosition(layoutprim_move + pos)
    merge.setPosition(merge_move + pos)

    return contextoptions


if TYPE_CHECKING:
    from typing import Any, Protocol

    import hou

    class T_ParmData(Protocol):
        _node: hou.Node


def get_eval_fn(typ: str) -> str:
    if typ == "str":
        eval_fn = "evalAsString"
    elif typ == "float":
        eval_fn = "evalAsFloat"
    elif typ == "int":
        eval_fn = "evalAsInt"
    else:
        raise AttributeError(f"Unrecognized parm type: {typ}")
    return eval_fn


def get_cast(typ: str) -> type:
    t_cast: type
    if typ == "str":
        t_cast = str
    elif typ == "float":
        t_cast = float
    elif typ == "int":
        t_cast = int
    else:
        raise AttributeError(f"Unrecognized parm type: {typ}")
    return t_cast


def create_property(
    typ: str, parm: str, has_toggle: bool = False, writable: bool = False
) -> property:
    def getter(self: T_ParmData):
        return getattr(self._node.parm(parm), get_eval_fn(typ))()

    def getter_toggled(self: T_ParmData):
        if self._node.parm("toggle_" + parm).evalAsInt():  # type: ignore[union-attr]
            return getter(self)
        return None

    def setter(self: T_ParmData, value):
        self._node.parm(parm).set(get_cast(typ)(value))  # type: ignore[union-attr]

    return property(
        getter_toggled if has_toggle else getter, setter if writable else None
    )


@dataclass
class parmfield:
    has_toggle: bool = False
    writable: bool = False


class ParmData(type):
    def __new__(cls, name, bases, attrs: dict) -> ParmData:
        def __init__(self: T_ParmData, node: hou.Node) -> None:
            self._node = node
            for attr in self.__annotations__.keys():
                if not node.parm(attr):
                    raise AttributeError(f"Parm {attr} not found on node {node.name()}")

        new_attrs: dict[str, Any] = {
            cls.__init__.__name__: __init__,
        }

        annotations: dict[str, str] = attrs.get("__annotations__")  # type: ignore[assignment]
        if annotations:
            for attr, typ in annotations.items():
                has_toggle = False
                writable = False
                if isinstance(f := attrs.get(attr), parmfield):
                    has_toggle = f.has_toggle
                    writable = f.writable

                new_attrs[attr] = create_property(typ, attr, has_toggle, writable)

        return super().__new__(cls, name, bases, {**attrs, **new_attrs})


# mypy: disable-error-code="call-arg,arg-type"


def parentChain(chainList):
    i = 1
    while i < (len(chainList)):
        cmds.parent(chainList[i], chainList[i - 1])
        i += 1


def parentAll(list):
    try:
        for each in list:
            cmds.parent(each, list[0])
    except Exception:
        print("oopsies")


def locToJoint(headLocator):
    cmds.select(cl=True)

    def recursiveHelper(callOn, parentJointName):
        if cmds.listRelatives(callOn, c=True, type="transform") is not None:
            for each in cmds.listRelatives(str(callOn), c=True, type="transform"):
                translate = cmds.xform(each, query=True, ws=True, rotatePivot=True)

                cmds.select(cl=True)

                cmds.joint(p=(translate[0], translate[1], translate[2]))

                currentJointName = cmds.rename(
                    cmds.ls(selection=True), str(each)[: (len(str(each)) - 5)]
                )

                # HEY DUMDUM YOU NEED TO GIVE THE PARENT COMMAND THE NAME OF THE JOINTS NOT THE LOCATORS.
                # YOU SHOULD ALSO CREATE THIS AS A PARAMETER TO BE FED INTO THE RECURSIVE FUNCTION

                cmds.parent(currentJointName, parentJointName)

                recursiveHelper(each, currentJointName)

    translate = cmds.xform(str(headLocator), query=True, ws=True, rotatePivot=True)
    cmds.joint(p=(translate[0], translate[1], translate[2]))
    cmds.rename(
        cmds.ls(selection=True), str(headLocator)[: (len(str(headLocator)) - 5)]
    )

    rootJointName = str(headLocator)[: (len(str(headLocator)) - 5)]

    if cmds.listRelatives(headLocator):
        recursiveHelper(headLocator, rootJointName)


def makeCurve(edges, name):
    cmds.select(edges)
    cmds.polyToCurve()
    cmds.rename(cmds.ls(selection=True), name)


def snapTo(startingLocation, endLocation):
    wS = cmds.xform(endLocation, query=True, rotatePivot=True, worldSpace=True)
    cmds.xform(startingLocation, ws=True, t=(wS[0], wS[1], wS[2]))


def snapJointTo(listGroup, jntSize):
    jointList = []
    for each in listGroup:
        if cmds.objectType(each) == "joint":
            wS = cmds.xform(str(each), query=True, rotatePivot=True, worldSpace=True)
            Joint = cmds.joint(p=(wS[0], wS[1], wS[2]), rad=jntSize)
            jointList.append(Joint)
            cmds.select(cl=True)

        if cmds.objectType(each) == "mesh":
            wS = cmds.pointPosition(each)
            Joint = cmds.joint(p=(wS[0], wS[1], wS[2]), rad=jntSize)
            jointList.append(Joint)
            cmds.select(cl=True)
    return jointList


def JointFollicleSnapper(fGroup):
    for each in fGroup:
        wS = cmds.xform(str(each), query=True, rotatePivot=True, worldSpace=True)
        Joint = cmds.joint(p=(wS[0], wS[1], wS[2]), rad=0.25)
        cmds.parent(cmds.ls(selection=True)[0], each)

        Circle = cmds.circle(nr=(0, 0, 1), c=(0, 0, 0), r=0.25)
        cmds.xform(t=(wS[0], wS[1], wS[2]))
        cmds.parent(cmds.ls(selection=True)[0], each)
        cmds.parentConstraint(Circle, Joint)
        ###ADD in parent to group and parent constraaint

        cmds.select(clear=True)


def searchFor(object, type):
    everythingInFollicle = cmds.listRelatives(object, ad=True)
    typeList = []

    for each in everythingInFollicle:
        if cmds.objectType(each) == type:
            typeList.append(each)

    return typeList


def jawControllerLinker(controls=cmds.ls(sl=1)):
    # Written by AntCGI

    jawJoint = "jaw_JNT"
    jawControl = "jaw_ctrl"

    # controlList = cmds.ls(sl=1)
    controlList = controls

    cmds.shadingNode("multiplyDivide", au=1, n=controlList[0] + "_multi")
    cmds.shadingNode("remapValue", au=1, n=controlList[0] + "_remap")

    cmds.connectAttr(jawJoint + ".rotate", controlList[0] + "_multi.input1", f=1)

    cmds.connectAttr(
        jawControl + ".Lip Influence", controlList[0] + "_remap.inputValue", f=1
    )

    cmds.connectAttr(
        controlList[0] + "_remap.outValue", controlList[0] + "_multi.input2X", f=1
    )
    cmds.connectAttr(
        controlList[0] + "_remap.outValue", controlList[0] + "_multi.input2Y", f=1
    )
    cmds.connectAttr(
        controlList[0] + "_remap.outValue", controlList[0] + "_multi.input2Z", f=1
    )

    cmds.connectAttr(
        controlList[0] + "_multi.output", controlList[0] + "_driver.rotate", f=1
    )

    if len(controlList) > 1:
        cmds.connectAttr(
            controlList[0] + "_multi.output", controlList[1] + "_driver.rotate", f=1
        )


def offsetGroupMaker(thingToOffset):
    cmds.parent(thingToOffset, world=True)
    emptyGroup = cmds.group(empty=True)
    snapTo(emptyGroup, thingToOffset)
    cmds.parent(thingToOffset, emptyGroup)
    return emptyGroup


# mypy: disable-error-code="call-arg,arg-type"


def parentChain(chainList):
    i = 1
    while i < (len(chainList)):
        cmds.parent(chainList[i], chainList[i - 1])
        i += 1


def parentAll(list):
    try:
        for each in list:
            cmds.parent(each, list[0])
    except Exception:
        print("oopsies")


def locToJoint(headLocator):
    cmds.select(cl=True)

    def recursiveHelper(callOn, parentJointName):
        if cmds.listRelatives(callOn, c=True, type="transform") is not None:
            for each in cmds.listRelatives(str(callOn), c=True, type="transform"):
                translate = cmds.xform(each, query=True, ws=True, rotatePivot=True)

                cmds.select(cl=True)

                cmds.joint(p=(translate[0], translate[1], translate[2]))

                currentJointName = cmds.rename(
                    cmds.ls(selection=True), str(each)[: (len(str(each)) - 5)]
                )

                # HEY DUMDUM YOU NEED TO GIVE THE PARENT COMMAND THE NAME OF THE JOINTS NOT THE LOCATORS.
                # YOU SHOULD ALSO CREATE THIS AS A PARAMETER TO BE FED INTO THE RECURSIVE FUNCTION

                cmds.parent(currentJointName, parentJointName)

                recursiveHelper(each, currentJointName)

    translate = cmds.xform(str(headLocator), query=True, ws=True, rotatePivot=True)
    cmds.joint(p=(translate[0], translate[1], translate[2]))
    cmds.rename(
        cmds.ls(selection=True), str(headLocator)[: (len(str(headLocator)) - 5)]
    )

    rootJointName = str(headLocator)[: (len(str(headLocator)) - 5)]

    if cmds.listRelatives(headLocator):
        recursiveHelper(headLocator, rootJointName)


# if cmds.listRelatives("head_JNT_temp"):
#    print(cmds.listRelatives("head_JNT_temp", c = True, type = "transform"))


tempList = []

cmds.spaceLocator(n="head_JNT_temp")
cmds.xform(t=(0, 151.177, -4.038))
tempList.append(cmds.ls(selection=True)[0])

cmds.spaceLocator(n="jaw_JNT_temp")
cmds.xform(t=(0, 148.835, -0.835))
tempList.append(cmds.ls(selection=True)[0])

cmds.spaceLocator(n="upperTeeth_JNT_temp")
cmds.xform(t=(0, 149.432, 5.857))
tempList.append(cmds.ls(selection=True)[0])

cmds.spaceLocator(n="lowerTeeth_JNT_temp")
cmds.xform(t=(0, 147.52, 5.738))
tempList.append(cmds.ls(selection=True)[0])

cmds.parent("upperTeeth_JNT_temp", "jaw_JNT_temp")
cmds.parent("lowerTeeth_JNT_temp", "jaw_JNT_temp")
cmds.parent("jaw_JNT_temp", "head_JNT_temp")


locToJoint("head_JNT_temp")


if cmds.about(nt=True):
    cmds.file(
        "G:\dungeons\character\Rigging\Rigs\RobinFace\Controls\RobinGlobalMouthControls.ma",
        i=True,
    )
if cmds.about(os=True) == "linux64":
    cmds.file(
        "/groups/dungeons/character/Rigging/Rigs/RobinFace/Controls/RobinGlobalMouthControls.ma",
        i=True,
    )


cmds.addAttr("jaw_ctrl", ln="LipInfluence", k=True, dv=1, min=0, max=2, at="double")

cmds.parentConstraint("jaw_ctrl", "jaw_JNT")


#
selected_objects = []


def add_to_selection_list():
    global selected_objects
    clear_selection_list()  # Clear the list before adding new objects
    selected_objects.extend(cmds.ls(selection=True, long=True))


def clear_selection_list():
    global selected_objects
    selected_objects = []


# Function to select all descendants of a group
def select_all_in_group(group_name):
    descendants = (
        cmds.listRelatives(group_name, allDescendents=True, fullPath=True) or []
    )
    if descendants:
        cmds.select(descendants, replace=True)


def select_children_in_group(group_name):
    children = cmds.listRelatives(group_name, children=True, fullPath=True) or []
    if children:
        cmds.select(children, replace=True)
    else:
        cmds.warning("No direct descendants found for {}.".format(group_name))


# Function to select descendants matching a name pattern in a group
def select_from_group(group_name, name_pattern):
    descendants = (
        cmds.listRelatives(group_name, allDescendents=True, fullPath=True) or []
    )
    if descendants:
        matching_descendants = [
            descendant
            for descendant in descendants
            if cmds.objectType(descendant) == "transform" and name_pattern in descendant
        ]
        if matching_descendants:
            cmds.select(matching_descendants, replace=True)


# Function to delete selected objects
def delete_selected():
    cmds.delete(cmds.ls(selection=True))


# Function to select a specific numerical child of a group
def select_numerical_child_of_group(group_name, specificChild):
    children = cmds.listRelatives(group_name, children=True, fullPath=True) or []
    if not children:
        print(f"No children found under group '{group_name}'.")
        return

    selected_child = children[specificChild]
    cmds.select(selected_child, replace=True)
    return selected_child


def create_joints_from_list(joint_radius, name_for_joint):
    selected_objects = cmds.ls(selection=True)  # Get currently selected objects
    index = 1  # Initialize index for numbering

    for obj in selected_objects:
        joint_name = f"{name_for_joint}_{index:02}"  # Append index to the joint name
        cmds.select(obj)
        cmds.joint(radius=joint_radius, name=joint_name)
        index += 1
        selected_objects.remove(obj)


def find_suffix(node_name):
    last_underscore_index = node_name.rfind("_")
    if last_underscore_index != -1:
        result = node_name[last_underscore_index + 1 :]
        return result
    else:
        return node_name


def find_prefix(node_name):
    parts = node_name.split("_", 1)

    if len(parts) > 1:
        prefix = parts[0] + "_"
        return prefix
    else:
        return ""


def delete_existing_nodes(node_type, node_name):
    existing_nodes = cmds.ls(type=node_type)
    for node in existing_nodes:
        if node_name in node:
            cmds.delete(node)


def create_square_control(control_name, length1, length2, normalDirection):
    if normalDirection == "x":
        normal_value = (1, 0, 0)
    elif normalDirection == "y":
        normal_value = (0, 1, 0)
    elif normalDirection == "z":
        normal_value = (0, 0, 1)

    square_Control = cmds.nurbsSquare(
        center=(0, 0, 0),
        name=control_name,
        normal=normal_value,
        sideLength1=length1,
        sideLength2=length2,
        spansPerSide=1,
        degree=3,
        constructionHistory=1,
    )

    cmds.select("right" + control_name + "Shape", r=True)
    cmds.select("bottom" + control_name + "Shape", add=True)
    cmds.select("left" + control_name + "Shape", add=True)
    cmds.select("top" + control_name + "Shape", add=True)
    cmds.select(control_name, add=True)

    cmds.parent(relative=True, shape=True)

    cmds.select("top" + control_name, r=True)
    cmds.select("left" + control_name, add=True)
    cmds.select("bottom" + control_name, add=True)
    cmds.select("right" + control_name, add=True)
    cmds.delete()

    cmds.group(square_Control, name=control_name + "_OFST")


def eyesocket():
    def loft_curves(curveOne, curveTwo, loftSurfaceName):
        surface = cmds.loft(
            curveOne,
            curveTwo,
            name=loftSurfaceName,
            constructionHistory=False,
            uniform=True,
            degree=3,
            sectionSpans=1,
            range=False,
            polygon=False,
            reverseSurfaceNormals=True,
        )[0]  # loft command returns a list, so we take the first item
        return surface

    loft_curves(
        "l_eyesocket_outer_CRV", "l_eyesocket_inner_CRV", "l_eyesocket_ribbon_surface"
    )
    loft_curves(
        "r_eyesocket_outer_CRV", "r_eyesocet_inner_CRV", "r_eyesocket_ribbon_surface"
    )

    def add_follicles_to_surface(Loft_Surface):
        cmds.select(Loft_Surface)
        mel.eval("createHair 29 1 10 0 0 1 0 5 0 1 2 1;")

    add_follicles_to_surface("l_eyesocket_ribbon_surface")
    add_follicles_to_surface("r_eyesocket_ribbon_surface")

    def Two_CleanupFollicles():
        cmds.rename("hairSystem1Follicles", "l_eyesocketFollicles")
        cmds.rename("hairSystem2Follicles", "r_eyesocketFollicles")
        cmds.delete("hairSystem1")
        cmds.delete("hairSystem2")
        cmds.delete("pfxHair1")
        cmds.delete("pfxHair2")
        cmds.delete("nucleus1")

        select_from_group("l_eyesocketFollicles", "curve")
        delete_selected()
        select_from_group("r_eyesocketFollicles", "curve")
        delete_selected()

        select_numerical_child_of_group("l_eyesocketFollicles", -1)
        delete_selected()

        select_numerical_child_of_group("r_eyesocketFollicles", -1)
        delete_selected()

        clear_selection_list()  # Ensure selected_objects list is cleared before reusing it

        select_all_in_group("l_eyesocketFollicles")
        add_to_selection_list()

        create_joints_from_list(0.1, "l_eyesocket_JNT")
        clear_selection_list()

        select_all_in_group("r_eyesocketFollicles")
        add_to_selection_list()

        create_joints_from_list(0.1, "r_eyesocket_JNT")
        clear_selection_list()

    Two_CleanupFollicles()

    def Two_eyesocket_controls():
        l_eyesocket_control_placement = [
            "l_eyesocket_JNT_01",
            "l_eyesocket_JNT_03",
            "l_eyesocket_JNT_05",
            "l_eyesocket_JNT_07",
            "l_eyesocket_JNT_09",
            "l_eyesocket_JNT_11",
            "l_eyesocket_JNT_13",
            "l_eyesocket_JNT_15",
            "l_eyesocket_JNT_17",
            "l_eyesocket_JNT_19",
            "l_eyesocket_JNT_21",
            "l_eyesocket_JNT_23",
            "l_eyesocket_JNT_25",
            "l_eyesocket_JNT_27",
        ]

        r_eyesocket_control_placement = [
            "r_eyesocket_JNT_01",
            "r_eyesocket_JNT_03",
            "r_eyesocket_JNT_05",
            "r_eyesocket_JNT_07",
            "r_eyesocket_JNT_09",
            "r_eyesocket_JNT_11",
            "r_eyesocket_JNT_13",
            "r_eyesocket_JNT_15",
            "r_eyesocket_JNT_17",
            "r_eyesocket_JNT_19",
            "r_eyesocket_JNT_21",
            "r_eyesocket_JNT_23",
            "r_eyesocket_JNT_25",
            "r_eyesocket_JNT_27",
        ]

        cmds.group(empty=True, name="l_socket_ctrl_jnts_GRP")
        cmds.select(l_eyesocket_control_placement)
        cmds.duplicate()
        cmds.select("l_socket_ctrl_jnts_GRP", add=True)
        cmds.parent()

        cmds.group(empty=True, name="r_socket_ctrl_jnts_GRP")
        cmds.select(r_eyesocket_control_placement)
        cmds.duplicate()
        cmds.select("r_socket_ctrl_jnts_GRP", add=True)
        cmds.parent()

    Two_eyesocket_controls()  # Call the function here (correct indentation)

    def eyesocket_control_placement(
        control_joint_group, sorting_group, eyeball_center_joint
    ):
        select_all_in_group(control_joint_group)
        add_to_selection_list()
        for index, obj in enumerate(selected_objects):
            cmds.setAttr(obj + ".radius", 0.15)
            if control_joint_group.startswith("l_"):
                prefix = "l_"
            elif control_joint_group.startswith("r_"):
                prefix = "r_"
            else:
                prefix = ""

            # Offset
            offset_name = "{}eyesocket_OFST_{:02d}".format(prefix, index + 1)
            cmds.group(empty=True, name=offset_name)
            offset_placement = cmds.parentConstraint(obj, offset_name)
            cmds.delete(offset_placement)

            # Control
            eyesocket_control_name = "{}eyesocket_CTRL_{:02d}".format(prefix, index + 1)
            cmds.circle(radius=0.2, name=eyesocket_control_name)
            control_placement = cmds.parentConstraint(obj, eyesocket_control_name)
            cmds.delete(control_placement)

            clear_selection_list
            cv_list = cmds.ls(eyesocket_control_name + ".cv[0:7]")
            cmds.select(cv_list)
            cmds.move(0, 0, 0.25, relative=True)
            clear_selection_list

            cmds.select(eyesocket_control_name)
            cmds.CenterPivot()

            cmds.parent(eyesocket_control_name, offset_name)

            cmds.parentConstraint(eyesocket_control_name, obj, maintainOffset=True)
            cmds.parent(offset_name, sorting_group)

    cmds.group(empty=True, name="l_eyesocket_ctrl_GRP")
    cmds.group(empty=True, name="r_eyesocket_ctrl_GRP")

    eyesocket_control_placement(
        "l_socket_ctrl_jnts_GRP", "l_eyesocket_ctrl_GRP", "L_eye_JNT"
    )
    eyesocket_control_placement(
        "r_socket_ctrl_jnts_GRP", "r_eyesocket_ctrl_GRP", "R_eye_JNT"
    )

    select_all_in_group("l_socket_ctrl_jnts_GRP")
    cmds.select("l_eyesocket_ribbon_surface", add=True)
    cmds.skinCluster(tsb=True)

    select_all_in_group("r_socket_ctrl_jnts_GRP")
    cmds.select("r_eyesocket_ribbon_surface", add=True)
    cmds.skinCluster(tsb=True)


def grab_face_bind_joints(*args):
    face_bind_selection()


def mark_face_bind_joints(*args):
    add_joints()


def Button_updateLocators(*args):
    create_gui()


def Button_eyelids(*args):
    createUI()


def Button_eyesockets(*args):
    eyesocket()


def createUI():
    reload_pipe()

    if cmds.window(
        "Katies_Toolbox", exists=True
    ):  # Check if the window already exists and delete it if true
        cmds.deleteUI("Katies_Toolbox")

    window = cmds.window(
        "Katies_Toolbox", title="Katies_Toolbox", widthHeight=(200, 100)
    )  # Create a new window

    cmds.columnLayout(adj=True)  # Create a layout for UI elements

    cmds.button(label="Mark as face bind joint", command=mark_face_bind_joints)
    cmds.button(label="Select face bind joints", command=grab_face_bind_joints)
    cmds.separator(height=10, style="none")  # Separate
    cmds.button(label="Base Locators", command=Button_updateLocators)
    cmds.button(label="Eyeslids", command=Button_eyelids)
    cmds.button(label="Eyesockets", command=Button_eyesockets)

    cmds.showWindow(window)  # Show the window


createUI()


# Function to create a locator at a specific position
def create_locator(name, x, y, z):
    locator = cmds.spaceLocator(name=name)[0]
    cmds.move(x, y, z, locator)


# Function to get the current position of the locator
def get_locator_position(locator_name):
    pos = cmds.xform(locator_name, query=True, translation=True, worldSpace=True)
    return pos


# Function to update the script with the new locator positions
def update_script():
    script_path = "Robin_Face_Locators.py"
    with open(script_path, "w") as file:
        file.write("# Building the Face\n# Locators\n\n")
        file.write("import maya.cmds as cmds\n\n")
        file.write('cmds.group(em=True, name="Locators")\n\n')

        file.write("def create_locator(name, x, y, z):\n")
        file.write("    locator = cmds.spaceLocator(name=name)[0]\n")
        file.write("    cmds.move(x, y, z, locator)\n")
        for locator_name in locator_names:
            pos = get_locator_position(locator_name)
            file.write(
                f'create_locator("{locator_name}", {pos[0]}, {pos[1]}, {pos[2]})\n'
            )
            file.write(f'cmds.parent("{locator_name}", "Locators")\n\n')


# Function to create all locators at their specific positions
def create_all_locators():
    cmds.group(em=True, name="Locators")

    locator_positions = {
        "skull_bind_LOC": (0, 148.946, -1.415),
        "face_upper_bind_LOC": (0, 148.535, -0.646),
        "head_tip_bind_LOC": (0, 156.237, 0.066),
        "brow_inner_l_bind_LOC": (1.532247, 157.231934, 8.437251),
        "brow_main_l_bind_LOC": (4.194504, 157.582428, 7.474292),
        "brow_peak_l_bind_LOC": (6.571188, 157.360886, 5.917207),
        "brow_inner_r_bind_LOC": (-1.532247, 157.231934, 8.437251),
        "brow_main_r_bind_LOC": (-4.194504, 157.582428, 7.474292),
        "brow_peak_r_bind_LOC": (-6.571189, 157.360886, 5.917207),
        "eyeSocket_r_bind_LOC": (-3.842108, 154.854385, 4.520485),
        "eye_r_bind_LOC": (-3.842108, 154.854385, 4.520485),
        "iris_r_bind_LOC": (-3.986634, 154.847443, 7.280398),
        "pupil_r_bind_LOC": (-3.986634, 154.847443, 7.280398),
        "eyeSocket_l_bind_LOC": (3.842108, 154.854385, 4.520485),
        "eye_l_bind_LOC": (3.842108, 154.854385, 4.520485),
        "iris_l_bind_LOC": (3.986634, 154.847443, 7.280398),
        "pupil_l_bind_LOC": (3.986634, 154.847443, 7.280398),
        "face_lower_bind_LOC": (0, 154.289, -0.867),
        "face_mid_bind_LOC": (0, 147.761, -0.203),
        "nose_bridge_bind_LOC": (0, 155.019, 7.697),
        "nose_bind_LOC": (0, 151.722, 9.133),
        "jaw_bind_LOC": (0, 150.539, -4.177),
        "jaw_end_bind_LOC": (0, 144.651, 7.095),
        "nose_l_nostril_bind_LOC": (0.495, 150.669, 8.234),
        "nose_r_nostril_bind_LOC": (-0.495, 150.669, 8.234),
        "nose_bottom_bind_LOC": (0, 150.425, 8.533),
        "nose_l_outer_nostril_bind_LOC": (1.451, 150.847, 7.997),
        "nose_r_outer_nostril_bind_LOC": (-1.451, 150.847, 7.997),
    }

    for locator_name, position in locator_positions.items():
        create_locator(locator_name, *position)
        cmds.parent(locator_name, "Locators")


# Function to create the GUI window
def create_gui():
    if cmds.window("locatorToolWindow", exists=True):
        cmds.deleteUI("locatorToolWindow", window=True)

    window = cmds.window(
        "locatorToolWindow", title="Locator Tool", widthHeight=(200, 100)
    )

    cmds.columnLayout(adjustableColumn=True)
    cmds.text(label="Create Locators:")
    cmds.button(
        label="Create Generic Locators", command=lambda *args: create_all_locators()
    )

    cmds.text(label="Update Script:")
    cmds.button(label="Update Robins Locator Positions", command=update_script_button)

    cmds.showWindow(window)


# Function to update the script with the new locator positions
def update_script_button(*args):
    update_script()


# Global variable to store locator names
locator_names = [
    "skull_bind_LOC",
    "face_upper_bind_LOC",
    "head_tip_bind_LOC",
    "brow_inner_l_bind_LOC",
    "brow_main_l_bind_LOC",
    "brow_peak_l_bind_LOC",
    "brow_inner_r_bind_LOC",
    "brow_main_r_bind_LOC",
    "brow_peak_r_bind_LOC",
    "eyeSocket_r_bind_LOC",
    "eye_r_bind_LOC",
    "iris_r_bind_LOC",
    "pupil_r_bind_LOC",
    "eyeSocket_l_bind_LOC",
    "eye_l_bind_LOC",
    "iris_l_bind_LOC",
    "pupil_l_bind_LOC",
    "face_lower_bind_LOC",
    "face_mid_bind_LOC",
    "nose_bridge_bind_LOC",
    "nose_bind_LOC",
    "jaw_bind_LOC",
    "jaw_end_bind_LOC",
    "nose_l_nostril_bind_LOC",
    "nose_r_nostril_bind_LOC",
    "nose_bottom_bind_LOC",
    "nose_l_outer_nostril_bind_LOC",
    "nose_r_outer_nostril_bind_LOC",
]

# Create the GUI
create_gui()


#    print("Check........................")
#    for obj in selected_objects:
#        print(obj)
#    print("End..........................")
selected_objects = []


def add_to_selection_list():
    global selected_objects
    clear_selection_list()  # Clear the list before adding new objects
    selected_objects.extend(cmds.ls(selection=True, long=True))


def clear_selection_list():
    global selected_objects
    selected_objects = []


# Function to select all descendants of a group
def select_all_in_group(group_name):
    descendants = (
        cmds.listRelatives(group_name, allDescendents=True, fullPath=True) or []
    )
    if descendants:
        cmds.select(descendants, replace=True)


def select_children_in_group(group_name):
    children = cmds.listRelatives(group_name, children=True, fullPath=True) or []
    if children:
        cmds.select(children, replace=True)
    else:
        cmds.warning("No direct descendants found for {}.".format(group_name))


# Function to select descendants matching a name pattern in a group
def select_from_group(group_name, name_pattern):
    descendants = (
        cmds.listRelatives(group_name, allDescendents=True, fullPath=True) or []
    )
    if descendants:
        matching_descendants = [
            descendant
            for descendant in descendants
            if cmds.objectType(descendant) == "transform" and name_pattern in descendant
        ]
        if matching_descendants:
            cmds.select(matching_descendants, replace=True)


# Function to delete selected objects
def delete_selected():
    cmds.delete(cmds.ls(selection=True))


# Function to select a specific numerical child of a group
def select_numerical_child_of_group(group_name, specificChild):
    children = cmds.listRelatives(group_name, children=True, fullPath=True) or []
    if not children:
        print(f"No children found under group '{group_name}'.")
        return

    selected_child = children[specificChild]
    cmds.select(selected_child, replace=True)
    return selected_child


def create_joints_from_list(joint_radius, name_for_joint):
    selected_objects = cmds.ls(selection=True)  # Get currently selected objects
    index = 1  # Initialize index for numbering

    for obj in selected_objects:
        joint_name = f"{name_for_joint}_{index:02}"  # Append index to the joint name
        cmds.select(obj)
        cmds.joint(radius=joint_radius, name=joint_name)
        index += 1
        selected_objects.remove(obj)


def find_suffix(node_name):
    last_underscore_index = node_name.rfind("_")
    if last_underscore_index != -1:
        result = node_name[last_underscore_index + 1 :]
        return result
    else:
        return node_name


def find_prefix(node_name):
    parts = node_name.split("_", 1)

    if len(parts) > 1:
        prefix = parts[0] + "_"
        return prefix
    else:
        return ""


def delete_existing_nodes(node_type, node_name):
    existing_nodes = cmds.ls(type=node_type)
    for node in existing_nodes:
        if node_name in node:
            cmds.delete(node)


def create_square_control(control_name, length1, length2, normalDirection):
    if normalDirection == "x":
        normal_value = (1, 0, 0)

    elif normalDirection == "y":
        normal_value = (0, 1, 0)

    elif normalDirection == "z":
        normal_value = (0, 0, 1)

    square_Control = cmds.nurbsSquare(
        center=(0, 0, 0),
        name=control_name,
        normal=normal_value,
        sideLength1=length1,
        sideLength2=length2,
        spansPerSide=1,
        degree=3,
        constructionHistory=1,
    )

    cmds.select("right" + control_name + "Shape", r=True)
    cmds.select("bottom" + control_name + "Shape", add=True)
    cmds.select("left" + control_name + "Shape", add=True)
    cmds.select("top" + control_name + "Shape", add=True)
    cmds.select(control_name, add=True)

    cmds.parent(relative=True, shape=True)

    cmds.select("top" + control_name, r=True)
    cmds.select("left" + control_name, add=True)
    cmds.select("bottom" + control_name, add=True)
    cmds.select("right" + control_name, add=True)
    cmds.delete()

    cmds.group(square_Control, name=control_name + "_OFST")


def One_rayden_eyelidCurves(*args):
    print("Executing One_rayden_eyelidCurves function...")
    cmds.group(empty=True, name="eyelid_rayden_Curves")

    def turn_edges_to_curve(edgelist, curveName):
        if not edgelist:
            print("Edge list is empty. Please provide valid edges.")
            return

        cmds.select(edgelist, replace=True)  # Select the edges
        curve = cmds.polyToCurve(
            form=2,
            degree=1,
            conformToSmoothMeshPreview=0,
            constructionHistory=False,
            name=curveName,
        )[0]
        cmds.parent(curve, "eyelid_rayden_Curves")

    def loft_curves(curveOne, curveTwo, loftSurfaceName):
        surface = cmds.loft(curveOne, curveTwo, name=loftSurfaceName)[
            0
        ]  # loft command returns a list, so we take the first item
        return surface

    l_rayden_outer_edges = [
        "FaceAtOrigin.e[18619]",
        "FaceAtOrigin.e[18580]",
        "FaceAtOrigin.e[18583]",
        "FaceAtOrigin.e[18586]",
        "FaceAtOrigin.e[18589]",
        "FaceAtOrigin.e[18592]",
        "FaceAtOrigin.e[18595]",
        "FaceAtOrigin.e[18598]",
        "FaceAtOrigin.e[18601]",
        "FaceAtOrigin.e[18604]",
        "FaceAtOrigin.e[18607]",
        "FaceAtOrigin.e[18610]",
        "FaceAtOrigin.e[18613]",
        "FaceAtOrigin.e[18616]",
        "FaceAtOrigin.e[18619]",
        "FaceAtOrigin.e[18622]",
        "FaceAtOrigin.e[18625]",
        "FaceAtOrigin.e[18628]",
        "FaceAtOrigin.e[18631]",
        "FaceAtOrigin.e[18634]",
        "FaceAtOrigin.e[18637]",
        "FaceAtOrigin.e[18640]",
        "FaceAtOrigin.e[18643]",
        "FaceAtOrigin.e[18646]",
        "FaceAtOrigin.e[18649]",
        "FaceAtOrigin.e[18652]",
        "FaceAtOrigin.e[18655]",
        "FaceAtOrigin.e[18658]",
        "FaceAtOrigin.e[18661]",
    ]

    l_rayden_inner_edges = [
        "FaceAtOrigin.e[18615]",
        "FaceAtOrigin.e[18578]",
        "FaceAtOrigin.e[18582]",
        "FaceAtOrigin.e[18585]",
        "FaceAtOrigin.e[18588]",
        "FaceAtOrigin.e[18591]",
        "FaceAtOrigin.e[18594]",
        "FaceAtOrigin.e[18597]",
        "FaceAtOrigin.e[18600]",
        "FaceAtOrigin.e[18603]",
        "FaceAtOrigin.e[18606]",
        "FaceAtOrigin.e[18609]",
        "FaceAtOrigin.e[18612]",
        "FaceAtOrigin.e[18615]",
        "FaceAtOrigin.e[18618]",
        "FaceAtOrigin.e[18621]",
        "FaceAtOrigin.e[18624]",
        "FaceAtOrigin.e[18627]",
        "FaceAtOrigin.e[18630]",
        "FaceAtOrigin.e[18633]",
        "FaceAtOrigin.e[18636]",
        "FaceAtOrigin.e[18639]",
        "FaceAtOrigin.e[18642]",
        "FaceAtOrigin.e[18645]",
        "FaceAtOrigin.e[18648]",
        "FaceAtOrigin.e[18651]",
        "FaceAtOrigin.e[18654]",
        "FaceAtOrigin.e[18657]",
        "FaceAtOrigin.e[18660]",
    ]

    r_rayden_outer_edges = [
        "FaceAtOrigin.e[3962]",
        "FaceAtOrigin.e[3919]",
        "FaceAtOrigin.e[3923]",
        "FaceAtOrigin.e[3926]",
        "FaceAtOrigin.e[3929]",
        "FaceAtOrigin.e[3932]",
        "FaceAtOrigin.e[3935]",
        "FaceAtOrigin.e[3938]",
        "FaceAtOrigin.e[3941]",
        "FaceAtOrigin.e[3944]",
        "FaceAtOrigin.e[3947]",
        "FaceAtOrigin.e[3950]",
        "FaceAtOrigin.e[3953]",
        "FaceAtOrigin.e[3956]",
        "FaceAtOrigin.e[3959]",
        "FaceAtOrigin.e[3962]",
        "FaceAtOrigin.e[3965]",
        "FaceAtOrigin.e[3968]",
        "FaceAtOrigin.e[3971]",
        "FaceAtOrigin.e[3974]",
        "FaceAtOrigin.e[3977]",
        "FaceAtOrigin.e[3980]",
        "FaceAtOrigin.e[3983]",
        "FaceAtOrigin.e[3986]",
        "FaceAtOrigin.e[3989]",
        "FaceAtOrigin.e[3992]",
        "FaceAtOrigin.e[3995]",
        "FaceAtOrigin.e[3998]",
        "FaceAtOrigin.e[4000]",
    ]

    r_rayden_inner_edges = [
        "FaceAtOrigin.e[3960]",
        "FaceAtOrigin.e[3921]",
        "FaceAtOrigin.e[3924]",
        "FaceAtOrigin.e[3927]",
        "FaceAtOrigin.e[3930]",
        "FaceAtOrigin.e[3933]",
        "FaceAtOrigin.e[3936]",
        "FaceAtOrigin.e[3939]",
        "FaceAtOrigin.e[3942]",
        "FaceAtOrigin.e[3945]",
        "FaceAtOrigin.e[3948]",
        "FaceAtOrigin.e[3951]",
        "FaceAtOrigin.e[3954]",
        "FaceAtOrigin.e[3957]",
        "FaceAtOrigin.e[3960]",
        "FaceAtOrigin.e[3963]",
        "FaceAtOrigin.e[3966]",
        "FaceAtOrigin.e[3969]",
        "FaceAtOrigin.e[3972]",
        "FaceAtOrigin.e[3975]",
        "FaceAtOrigin.e[3978]",
        "FaceAtOrigin.e[3981]",
        "FaceAtOrigin.e[3984]",
        "FaceAtOrigin.e[3987]",
        "FaceAtOrigin.e[3990]",
        "FaceAtOrigin.e[3993]",
        "FaceAtOrigin.e[3996]",
        "FaceAtOrigin.e[3999]",
        "FaceAtOrigin.e[4001]",
    ]

    cmds.select(clear=True)

    # Convert edges to curves
    turn_edges_to_curve(l_rayden_outer_edges, "l_eyelid_outer_CRV")
    turn_edges_to_curve(l_rayden_inner_edges, "l_eyelid_inner_CRV")
    turn_edges_to_curve(r_rayden_outer_edges, "r_eyelid_outer_CRV")
    turn_edges_to_curve(r_rayden_inner_edges, "r_eyelid_inner_CRV")


def Two(*args):
    def look_controls(eyeball_jnt_name):
        print("look Control build")

        if eyeball_jnt_name.startswith("L_"):
            prefix = "l_"
        elif eyeball_jnt_name.startswith("R_"):
            prefix = "r_"
        else:
            prefix = ""
        old_suffix = "_JNT"
        new_suffix = "CTRL"
        control_name = eyeball_jnt_name.rsplit(old_suffix, 1)[0] + new_suffix
        cmds.circle(radius=1, name=control_name)

        center_offset_group = cmds.group(control_name, name=prefix + "eyelook_OFST")
        placement_Constraint = cmds.parentConstraint(
            eyeball_jnt_name, center_offset_group, maintainOffset=False
        )
        cmds.delete(placement_Constraint)

        cv_list = cmds.ls(control_name + ".cv[0:7]")
        cmds.select(cv_list)
        cmds.move(0, 0, 20, relative=True)
        clear_selection_list

        cmds.select(control_name)
        cmds.CenterPivot()

    look_controls("L_eye_JNT")
    look_controls("R_eye_JNT")
    cmds.aimConstraint(
        "L_eyeCTRL",
        "L_eye_JNT",
        maintainOffset=True,
        weight=1,
        aimVector=(0, 0, 1),
        upVector=(0, 1, 0),
        worldUpType="scene",
    )
    cmds.aimConstraint(
        "R_eyeCTRL",
        "R_eye_JNT",
        maintainOffset=True,
        weight=1,
        aimVector=(0, 0, 1),
        upVector=(0, 1, 0),
        worldUpType="scene",
    )

    def main_look_control():
        eye_Center_LOC = cmds.spaceLocator(name="eye_center_placement_LOC")[0]

        cmds.parentConstraint("R_eyeCTRL", eye_Center_LOC)
        cmds.parentConstraint("L_eyeCTRL", eye_Center_LOC)

        create_square_control("Look_Control", 4, 12, "z")

        placementConstraint = cmds.parentConstraint(
            "eye_center_placement_LOC", "Look_Control_OFST"
        )
        cmds.delete(placementConstraint)
        cv_list = cmds.ls(
            "topLook_ControlShape.cv[0:3]",
            "bottomLook_ControlShape.cv[0:3]",
            "leftLook_ControlShape.cv[0:3]",
            "rightLook_ControlShape.cv[0:3]",
        )
        cmds.select(cv_list)

        cmds.parent("l_eyelook_OFST", "Look_Control")
        cmds.parent("r_eyelook_OFST", "Look_Control")

        cmds.delete(eye_Center_LOC)

    main_look_control()

    def loft_curves(curveOne, curveTwo, loftSurfaceName):
        surface = cmds.loft(
            curveOne,
            curveTwo,
            name=loftSurfaceName,
            constructionHistory=False,
            uniform=True,
            degree=3,
            sectionSpans=1,
            range=False,
            polygon=False,
            reverseSurfaceNormals=True,
        )[0]  # loft command returns a list, so we take the first item
        return surface

    loft_curves("l_eyelid_outer_CRV", "l_eyelid_inner_CRV", "l_eye_ribbon_surface")
    loft_curves("r_eyelid_outer_CRV", "r_eyelid_inner_CRV", "r_eye_ribbon_surface")

    def add_follicles_to_surface(Loft_Surface):
        cmds.select(Loft_Surface)
        mel.eval("createHair 29 1 10 0 0 1 0 5 0 1 2 1;")

    add_follicles_to_surface("l_eye_ribbon_surface")
    add_follicles_to_surface("r_eye_ribbon_surface")

    def Two_CleanupFollicles():
        cmds.rename("hairSystem1Follicles", "l_eyelidFollicles")
        cmds.rename("hairSystem2Follicles", "r_eyelidFollicles")
        cmds.delete("hairSystem1")
        cmds.delete("hairSystem2")
        cmds.delete("pfxHair1")
        cmds.delete("pfxHair2")
        cmds.delete("nucleus1")

        select_from_group("l_eyelidFollicles", "curve")
        delete_selected()
        select_from_group("r_eyelidFollicles", "curve")
        delete_selected()

        select_numerical_child_of_group("l_eyelidFollicles", -1)
        delete_selected()

        select_numerical_child_of_group("r_eyelidFollicles", -1)
        delete_selected()

        clear_selection_list()  # Ensure selected_objects list is cleared before reusing it

        select_all_in_group("l_eyelidFollicles")
        add_to_selection_list()

        create_joints_from_list(0.1, "l_eyelid_JNT")
        clear_selection_list()

        select_all_in_group("r_eyelidFollicles")
        add_to_selection_list()

        create_joints_from_list(0.1, "r_eyelid_JNT")
        clear_selection_list()

    Two_CleanupFollicles()

    def Two_eyelid_controls():
        l_eye_control_placement = [
            "l_eyelid_JNT_01",
            "l_eyelid_JNT_03",
            "l_eyelid_JNT_05",
            "l_eyelid_JNT_07",
            "l_eyelid_JNT_09",
            "l_eyelid_JNT_11",
            "l_eyelid_JNT_13",
            "l_eyelid_JNT_15",
            "l_eyelid_JNT_17",
            "l_eyelid_JNT_19",
            "l_eyelid_JNT_21",
            "l_eyelid_JNT_23",
            "l_eyelid_JNT_25",
            "l_eyelid_JNT_27",
        ]

        r_eye_control_placement = [
            "r_eyelid_JNT_01",
            "r_eyelid_JNT_03",
            "r_eyelid_JNT_05",
            "r_eyelid_JNT_07",
            "r_eyelid_JNT_09",
            "r_eyelid_JNT_11",
            "r_eyelid_JNT_13",
            "r_eyelid_JNT_15",
            "r_eyelid_JNT_17",
            "r_eyelid_JNT_19",
            "r_eyelid_JNT_21",
            "r_eyelid_JNT_23",
            "r_eyelid_JNT_25",
            "r_eyelid_JNT_27",
        ]

        cmds.group(empty=True, name="l_ctrl_jnts_GRP")
        cmds.select(l_eye_control_placement)
        cmds.duplicate()
        cmds.select("l_ctrl_jnts_GRP", add=True)
        cmds.parent()

        cmds.group(empty=True, name="r_ctrl_jnts_GRP")
        cmds.select(r_eye_control_placement)
        cmds.duplicate()
        cmds.select("r_ctrl_jnts_GRP", add=True)
        cmds.parent()

        def eyelid_control_placement(
            control_joint_group, sorting_group, eyeball_center_joint
        ):
            cmds.setAttr("L_eye_JNT.rotateZ", 0)
            cmds.setAttr("L_eye_JNT.rotateX", 0)
            cmds.setAttr("L_eye_JNT.rotateY", 0)
            # cmds.makeIdentity("L_eye_JNT", apply=True, translate=True, rotate=True, scale=False, normal=False)

            cmds.setAttr("R_eye_JNT.rotateZ", 0)
            cmds.setAttr("R_eye_JNT.rotateX", 0)
            cmds.setAttr("R_eye_JNT.rotateY", 0)
            # cmds.makeIdentity("R_eye_JNT", apply=True, translate=True, rotate=True, scale=False, normal=False)

            select_all_in_group(control_joint_group)
            add_to_selection_list()
            for index, obj in enumerate(selected_objects):
                cmds.setAttr(obj + ".radius", 0.15)
                if control_joint_group.startswith("l_"):
                    prefix = "l_"
                elif control_joint_group.startswith("r_"):
                    prefix = "r_"
                else:
                    prefix = ""

                # Driver
                driver_name = "{}eyelid_{:02d}_driver".format(prefix, index + 1)
                cmds.group(empty=True, name=driver_name)
                driver_placement = cmds.parentConstraint(
                    eyeball_center_joint, driver_name
                )
                cmds.delete(driver_placement)
                cmds.parent(driver_name, sorting_group)

                # Offset
                offset_name = "{}eyelid_OFST_{:02d}".format(prefix, index + 1)
                cmds.group(empty=True, name=offset_name)
                offset_placement = cmds.parentConstraint(obj, offset_name)
                cmds.delete(offset_placement)
                cmds.parent(offset_name, driver_name)

                # Control
                eyelid_control_name = "{}eyelid_CTRL_{:02d}".format(prefix, index + 1)
                cmds.circle(radius=0.2, name=eyelid_control_name)
                control_placement = cmds.parentConstraint(obj, eyelid_control_name)
                cmds.delete(control_placement)
                cmds.parent(eyelid_control_name, offset_name)
                cmds.parentConstraint(eyelid_control_name, obj)

        cmds.group(empty=True, name="l_eyelid_ctrl_GRP")
        cmds.group(empty=True, name="r_eyelid_ctrl_GRP")

        eyelid_control_placement("l_ctrl_jnts_GRP", "l_eyelid_ctrl_GRP", "L_eye_JNT")
        eyelid_control_placement("r_ctrl_jnts_GRP", "r_eyelid_ctrl_GRP", "R_eye_JNT")

        select_all_in_group("l_ctrl_jnts_GRP")
        cmds.select("l_eye_ribbon_surface", add=True)
        cmds.skinCluster(tsb=True)

        select_all_in_group("r_ctrl_jnts_GRP")
        cmds.select("r_eye_ribbon_surface", add=True)
        cmds.skinCluster(tsb=True)

        def adding_blink_attributes(control_name):
            cmds.addAttr(
                control_name,
                longName="Blink",
                attributeType="double",
                minValue=-1,
                maxValue=1,
                defaultValue=0,
            )
            cmds.setAttr(control_name + "." + "Blink", keyable=True)

            cmds.addAttr(
                control_name,
                longName="Blink_Height",
                attributeType="double",
                minValue=-25,
                maxValue=25,
                defaultValue=0.2,
            )
            cmds.setAttr(control_name + "." + "Blink_Height", keyable=True)

            cmds.addAttr(
                control_name,
                longName="Blink_Influence",
                attributeType="double",
                minValue=0,
                maxValue=2,
                defaultValue=1,
            )
            cmds.setAttr(control_name + "." + "Blink_Influence", keyable=True)

            cmds.addAttr(
                control_name,
                longName="Eyelid_Follow",
                attributeType="double",
                minValue=0,
                maxValue=1,
                defaultValue=0.05,
            )
            cmds.setAttr(control_name + "." + "Eyelid_Follow", keyable=True)

        adding_blink_attributes("L_eyeCTRL")
        adding_blink_attributes("R_eyeCTRL")

        def setting_up_the_node_network(
            control_driver, eyelid_control, eye_center_joint
        ):
            suffix = find_suffix(control_driver)
            prefix = find_prefix(control_driver)
            print(
                "Driver: {}, Suffix: {}, Prefix: {}".format(
                    control_driver, suffix, prefix
                )
            )

            # Delete existing nodes if they exist
            delete_existing_nodes(
                "remapValue", prefix + "eyelid_control_remap_"
            )  # + suffix)
            delete_existing_nodes(
                "multiplyDivide", prefix + "eyelid_control_multi_"
            )  # + suffix)
            delete_existing_nodes(
                "plusMinusAverage", prefix + "blink_height_plusminus_"
            )  # + suffix)
            delete_existing_nodes(
                "plusMinusAverage", prefix + "eyelidFollow_plusminus_"
            )  # + suffix)
            delete_existing_nodes(
                "multiplyDivide", prefix + "eyelid_influence_multi_"
            )  # + suffix)

            # Create nodes
            remap_node = cmds.shadingNode(
                "remapValue", asUtility=True, name=prefix + "eyelid_control_remap_01"
            )  # + suffix)
            multiply_node = cmds.shadingNode(
                "multiplyDivide",
                asUtility=True,
                name=prefix + "eyelid_control_multi_01",
            )  # + suffix)
            heightAdd_node = cmds.shadingNode(
                "plusMinusAverage",
                asUtility=True,
                name=prefix + "blink_height_plusminus_01",
            )  # + suffix)
            eyelidFollow_node = cmds.shadingNode(
                "plusMinusAverage",
                asUtility=True,
                name=prefix + "eyelidFollow_plusminus_01",
            )  # + suffix)
            eyelidFollowInfluence_multi_node = cmds.shadingNode(
                "multiplyDivide",
                asUtility=True,
                name=prefix + "eyelid_influence_multi_01",
            )  # + suffix)

            # Connect nodes
            cmds.connectAttr(
                "{}.outValue".format(remap_node),
                "{}.input2X".format(multiply_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.outValue".format(remap_node),
                "{}.input2Y".format(multiply_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.outValue".format(remap_node),
                "{}.input2Z".format(multiply_node),
                force=True,
            )
            # .............cmds.connectAttr(eye_center_joint + '.rotate', '{}.input1'.format(multiply_node), force=True)
            cmds.connectAttr(
                "{}.output".format(multiply_node),
                control_driver + ".rotate",
                force=True,
            )
            cmds.connectAttr(
                "{}.Blink_Influence".format(eyelid_control),
                "{}.inputValue".format(remap_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.Blink".format(eyelid_control),
                "{}.input1X".format(multiply_node),
                force=True,
            )

            cmds.connectAttr(
                "{}.Blink_Height".format(eyelid_control),
                "{}.input1D[0]".format(heightAdd_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.Blink_Height".format(eyelid_control),
                "{}.input1D[1]".format(heightAdd_node),
                force=True,
            )
            cmds.disconnectAttr(
                "{}.Blink_Height".format(eyelid_control),
                "{}.input1D[1]".format(heightAdd_node),
            )

            # eyelidsFollow
            cmds.connectAttr(
                "{}.rotate".format(eye_center_joint),
                "{}.input3D[0]".format(eyelidFollow_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.output".format(multiply_node),
                "{}.input3D[1]".format(eyelidFollow_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.output3D".format(eyelidFollow_node),
                "{}.rotate".format(control_driver),
                force=True,
            )

            # follow influence
            cmds.connectAttr(
                "{}.rotate".format(eye_center_joint),
                "{}.input1".format(eyelidFollowInfluence_multi_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.output".format(eyelidFollowInfluence_multi_node),
                "{}.input3D[0]".format(eyelidFollow_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.Eyelid_Follow".format(eyelid_control),
                "{}.input2X".format(eyelidFollowInfluence_multi_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.Eyelid_Follow".format(eyelid_control),
                "{}.input2Y".format(eyelidFollowInfluence_multi_node),
                force=True,
            )
            cmds.connectAttr(
                "{}.Eyelid_Follow".format(eyelid_control),
                "{}.input2Z".format(eyelidFollowInfluence_multi_node),
                force=True,
            )

            # ......................................................................
            # setting the positions of each control for the blink
            # Tops/Corners
            def setRemap(remapNode, plusMinusNode):
                # Corners Outer
                if (
                    remapNode == "l_eyelid_control_remap_08"
                    or remapNode == "r_eyelid_control_remap_08"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 0
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)
                if (
                    remapNode == "l_eyelid_control_remap_07"
                    or remapNode == "r_eyelid_control_remap_07"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 10
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_06"
                    or remapNode == "r_eyelid_control_remap_06"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 15
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_05"
                    or remapNode == "r_eyelid_control_remap_05"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 23
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_04"
                    or remapNode == "r_eyelid_control_remap_04"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = 25
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_03"
                    or remapNode == "r_eyelid_control_remap_03"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 23
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_02"
                    or remapNode == "r_eyelid_control_remap_02"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 15
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)
                    # Corners Inner
                if (
                    remapNode == "l_eyelid_control_remap_01"
                    or remapNode == "r_eyelid_control_remap_01"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0.25)
                    cmds.setAttr(remapNode + ".inputMax", 0.75)
                    displacement_value = 0
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                # Bottoms
                if (
                    remapNode == "l_eyelid_control_remap_09"
                    or remapNode == "r_eyelid_control_remap_09"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -10
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_10"
                    or remapNode == "r_eyelid_control_remap_10"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -15
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_11"
                    or remapNode == "r_eyelid_control_remap_11"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -17
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_12"
                    or remapNode == "r_eyelid_control_remap_12"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -15
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_13"
                    or remapNode == "r_eyelid_control_remap_13"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -10
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                if (
                    remapNode == "l_eyelid_control_remap_14"
                    or remapNode == "r_eyelid_control_remap_14"
                ):
                    cmds.setAttr(remapNode + ".inputMin", 0)
                    cmds.setAttr(remapNode + ".inputMax", 1)
                    displacement_value = -5
                    cmds.setAttr(remapNode + ".outputMax", displacement_value)
                    cmds.setAttr(plusMinusNode + ".input1D[1]", displacement_value)

                cmds.connectAttr(
                    "{}.output1D".format(heightAdd_node),
                    "{}.outputMax".format(remap_node),
                    force=True,
                )

            setRemap(remap_node, heightAdd_node)

        # ......................................................................
        select_children_in_group("l_eyelid_ctrl_GRP")
        add_to_selection_list()
        for driver in selected_objects:
            setting_up_the_node_network(driver, "L_eyeCTRL", "L_eye_JNT")

        select_children_in_group("r_eyelid_ctrl_GRP")
        add_to_selection_list()
        for driver in selected_objects:
            setting_up_the_node_network(driver, "R_eyeCTRL", "R_eye_JNT")

    Two_eyelid_controls()


def createUI():
    # Check if the window already exists and delete it if true
    if cmds.window("eyesWindow", exists=True):
        cmds.deleteUI("eyesWindow")

    # Create a new window
    window = cmds.window("eyesWindow", title="Eyes", widthHeight=(200, 100))

    # Create a layout for UI elements
    cmds.columnLayout(adj=True)

    # Create a button to build curves
    cmds.button(label="1. Build Curves", command=One_rayden_eyelidCurves)
    cmds.button(label="2. Eyelid Ribbon", command=Two)

    # Show the window
    cmds.showWindow(window)


createUI()


def add_joints(*args):
    # Get a list of selected objects
    selection = cmds.ls(selection=True)

    # Iterate over each selected object and add the boolean attribute
    for obj in selection:
        cmds.addAttr(
            obj,
            longName="face_bind_joint",
            attributeType="bool",
            defaultValue=True,
            keyable=False,
        )


def face_bind_selection(*args):
    # Get a list of all objects in the scene
    all_objects = cmds.ls(type="transform", visible=True)

    # Initialize an empty list to store objects with the attribute set to True
    selected_objects = []

    # Iterate over each object to check if it has the attribute "face_bind_joint" set to True
    for obj in all_objects:
        if cmds.attributeQuery("face_bind_joint", node=obj, exists=True):
            value = cmds.getAttr(obj + ".face_bind_joint")
            if value:
                selected_objects.append(obj)

    # Select the objects that have the attribute set to True
    if selected_objects:
        cmds.select(selected_objects)
    else:
        print("No objects found with 'face_bind_joint' attribute set to True.")


def reload_pipe() -> None:
    # wrap this in a try block because it will fail in headless mode
    try:
        import mayaUsd.lib as mayaUsdLib  # type: ignore[import-not-found]

        mayaUsdLib.ExportChaser.Unregister(ExportChaser, ExportChaser.ID)
        mayaUsdLib.ExportChaser.Register(ExportChaser, ExportChaser.ID)
    except Exception:
        pass


def timeline_generator(
    pre_roll: list[tuple[str, tuple[int, int, int], int]],
    roll: list[tuple[str, tuple[int, int, int], int]],
    /,
    start_frame: int = 1001,
) -> tuple[list[int], list[tuple[int, int, int]], list[str]]:
    colors = []
    comments = []
    pre_duration = 0
    post_duration = 0

    for comment, color, duration in pre_roll:
        comments += [comment] * duration
        colors += [color] * duration
        pre_duration += duration
    for comment, color, duration in roll:
        comments += [comment] * duration
        colors += [color] * duration
        post_duration += duration

    frames = list(range(start_frame - pre_duration, start_frame + post_duration))
    return frames, colors, comments


def shot_timeline_generator(
    shot_duration: int,
    shot_start_frame: int = 1001,
) -> tuple[list[int], list[tuple[int, int, int]], list[str]]:
    return timeline_generator(
        [
            ("Rest Pose @Origin", (70, 0, 0), 15),
            ("Rest Pose -> Windup", (150, 0, 0), 15),
            ("Hold Windup", (255, 0, 0), 10),
            ("Windup", (128, 128, 0), 15),
            ("Head", (128, 255, 128), 5),
        ],
        [
            ("Animate!", (0, 255, 0), shot_duration),
            ("Tail", (100, 160, 255), 5),
        ],
        start_frame=shot_start_frame,
    )


def createSpaceSwitch():
    sel = mc.ls(sl=True)
    sources = sel

    target = sel[-1]
    sources.remove(target)
    sourceNames = []

    colonSourceStr = ""
    for source in sources:
        name = source.replace("_CTRL", "")
        if ":" in source:
            c = source.index(":")
            name = source[c + 1 :]
        colonSourceStr += name + ":"
        sourceNames.append(name)

    if mc.attributeQuery("spaceSwitch", node=target, exists=True):
        mc.deleteAttr(target, at="spaceSwitch")

    mc.addAttr(
        target,
        ln="spaceSwitch",
        at="enum",
        en="default:" + colonSourceStr,
        keyable=True,
    )

    mc.select(target)
    grp = target + "_space_switch_GRP"

    parent = (mc.listRelatives(target, parent=True)[0],)

    if not mc.objExists(grp):
        grp = mc.group(
            name=target + "_space_switch_GRP",
            em=True,
        )
        fix = mc.group(em=True, name=target + "_space_switch_TARG")
        mc.matchTransform(fix, target)
        mc.parent(fix, grp)
        pc = mc.parentConstraint(fix, parent, mo=True)

    if mc.listRelatives(grp, type="constraint") is not None:
        constraint = mc.listRelatives(grp, type="constraint")[0]
        mc.delete(constraint)
    pc = mc.parentConstraint(sources, grp, mo=True)[0]

    pcTrgs = mc.parentConstraint(pc, wal=True, q=True, mo=True)

    defaultCond = mc.createNode("condition", n="default_COND")
    mc.connectAttr(target + ".spaceSwitch", defaultCond + ".firstTerm")
    mc.setAttr(defaultCond + ".colorIfTrueR", 0)
    mc.setAttr(defaultCond + ".colorIfFalseR", 1)
    mc.setAttr(defaultCond + ".operation", 0)

    for count, source in enumerate(sources):
        print(source)
        print(pcTrgs[count])
        cond = mc.createNode("condition", n=pcTrgs[count] + "_COND")
        mc.connectAttr(target + ".spaceSwitch", cond + ".firstTerm")
        mc.setAttr(cond + ".secondTerm", count + 1)
        mc.setAttr(cond + ".colorIfTrueR", 1)
        mc.setAttr(cond + ".colorIfFalseR", 0)
        mc.connectAttr(defaultCond + ".outColorR", cond + ".colorIfTrueR")
        mc.connectAttr(cond + ".outColorR", pc + "." + pcTrgs[count])

    mc.select(target)


def run():
    createSpaceSwitch()


if TYPE_CHECKING:
    from typing import Generator


@contextmanager
def maintain_selection() -> Generator[None, None, None]:
    selection = mc.ls(selection=True, long=True, ufeObjects=True, absoluteName=True)

    try:
        yield
    finally:
        mc.select(*selection, replace=True)


_S = TypeVar("_S")


@attrs.define
class JsonSerializable:
    """Dataclass with methods to (de)serialize JSON"""

    @classmethod
    def from_json(cls: Type[_S], json_data: Union[str, bytes, bytearray]) -> _S:
        return cattrs.structure(json.loads(json_data), cls)

    def to_json(self) -> str:
        c = cattrs.Converter(unstruct_collection_overrides={set: list})
        return json.dumps(c.unstructure(self))


@attrs.define
class Diffable(JsonSerializable):
    """JsonSerializable dataclass that tracks changes to it since initialization"""

    _initial_state: dict[str, Any] = attrs.field(
        alias="_initial_state",
        eq=False,
        init=False,
        order=False,
        repr=False,
    )

    def __attrs_post_init__(self) -> None:
        # don't store initial state if frozen
        if type(self.__class__.__setattr__) is _frozen_setattrs:
            object.__setattr__(self, "_initial_state", {})

        # get a deepcopy of each slot
        name: str
        state: dict[str, Any] = {}
        for name in (f.name for f in attrs.fields(self.__class__)):
            if name == "_initial_state":
                continue
            state[name] = deepcopy(getattr(self, name))

        # save the initial state
        object.__setattr__(self, "_initial_state", state)

    def diff(self) -> dict[str, Any]:
        if self._initial_state == {}:
            return {}

        # loop through keys and find changes
        diff: dict[str, Any] = {}
        name: str
        for name in (f.name for f in attrs.fields(self.__class__)):
            if name == "_initial_state":
                # prevent infinite loop
                continue
            if (val := getattr(self, name)) != self._initial_state[name]:
                diff[name] = val
        return diff


if TYPE_CHECKING:
    from typing import Any

    from typing_extensions import Self


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FFMpegPreset:
    ext: str
    out_kwargs: dict[str, Any]

    def __hash__(self):
        return hash(frozenset(self.out_kwargs.items()))


class Playblaster(metaclass=ABCMeta):
    """Parent class for creating playblasters. Uses FFmpeg to encode videos"""

    _shot: Shot
    _in_context: bool

    FR = 24

    class PRESET(FFMpegPreset, Enum):
        EDIT_SQ = (
            "mov",
            {
                "vcodec": "dnxhd",
                "pix_fmt": "yuv422p",
                "vprofile": "dnxhr_sq",
                # this number comes from Avid's table in the DNxHD whitepaper
                "video_bitrate": "124M",
            },
        )
        EDIT_HQX = (
            "mov",
            {
                "vcodec": "dnxhd",
                "pix_fmt": "yuv422p10le",
                "vprofile": "dnxhr_hqx",
                "video_bitrate": "188M",
            },
        )
        WEB = (
            "mp4",
            {
                "vcodec": "libx264",
                "preset": "veryslow",
                "tune": "animation",
                "crf": 20,
            },
        )

    def __init__(self) -> None:
        pass

    @abstractmethod
    def _write_images(self, path: str) -> None:
        pass

    def __enter__(self) -> Self:
        self._in_context = True
        return self

    def __call__(self, shot: Shot, *args):
        self._shot = shot
        return self

    def __exit__(self, *args) -> None:
        self._in_context = False

    def _do_playblast(
        self,
        out_paths: dict[PRESET, list[Path | str]] | None = None,
        tails: tuple[int, int] = (0, 0),
    ) -> None:
        if not self._in_context:
            raise RuntimeError("_do_playblast not called from within context self")

        if not out_paths:
            out_paths = {}

        tempdir = Path(os.getenv("TMPDIR", os.getenv("TEMP", "tmp"))).resolve()

        FILENAME = "lnd_pb_temp." + self._shot.code

        # remove any old playblasts
        for p in tempdir.glob(FILENAME + "*"):
            p.unlink()

        # do the playblast
        self._write_images(str(tempdir / FILENAME))

        # use ffmpeg to encode the video
        start_frame = int(self._shot.cut_in) - tails[0]
        images = ffmpeg.input(
            str(tempdir / FILENAME) + ".%04d.png",
            start_number=start_frame,
            r=self.FR,
            # precisely define input colorspace
            colorspace="bt709",
            color_trc="iec61966-2-1",
        )
        for preset, paths in out_paths.items():
            out_filename = str(tempdir / FILENAME) + "." + preset.ext
            ffmpeg.output(
                images,
                out_filename,
                **preset.out_kwargs,
                timecode="00:00:{:02}:{:02}".format(
                    start_frame // self.FR,
                    start_frame % self.FR,
                ),
                r=self.FR,
            ).overwrite_output().run()

            # copy video out of tempdir
            for path in (Path(str(p) + "." + preset.ext) for p in paths):
                if not path.parent.exists():
                    path.parent.mkdir(mode=0o770, parents=True)
                shutil.copyfile(out_filename, path)

        # clean up if not in debug mode
        if not log.isEnabledFor(logging.DEBUG):
            for p in tempdir.glob(FILENAME + "*"):
                p.unlink()

    @abstractmethod
    def playblast(self) -> None:
        """Function to be called by the user to trigger a playblast.
        This should call `_do_playblast` from within a `with self(...)`
        block.
        Looks something like:
            >>> def playblast(self) -> None:
            >>>     with self(shot):
            >>>         super()._do_playblast([filepath])
        """
        pass


if TYPE_CHECKING:
    from typing import Any, ClassVar, Protocol, TypeVar

    KT = TypeVar("KT")
    VT = TypeVar("VT")

    class IsDataclass(Protocol):
        __dataclass_fields__: ClassVar[dict[str, Any]]
        __match_args__: ClassVar[tuple[str]]


log = logging.getLogger(__name__)


class dotdict(dict):
    """dot notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__  # type: ignore[assignment]
    __delattr__ = dict.__delitem__  # type: ignore[assignment]


def dataclass_as_tuple(dc: IsDataclass) -> tuple[Any]:
    return tuple((getattr(dc, a) for a in dc.__match_args__))


def dict_index(d: dict[KT, VT], v: VT) -> KT:
    """List index function for dicts"""
    return list(d.keys())[list(d.values()).index(v)]


def find_implementation(cls: type, module: str, package: str | None = None) -> type:
    """Find an implementation of the class in the specified module."""
    # Check if the specified module exists
    if importlib.util.find_spec(module, package):
        # Import the module
        imported_module = importlib.import_module(module, package)

        # Check if the submodule contains an implementation of the class
        classes = getmembers(
            imported_module,
            lambda obj: isclass(obj) and not isabstract(obj) and issubclass(obj, cls),
        )

        # Check if more or less than one implementation was found
        if len(classes) < 1:
            raise AssertionError(
                f"module '{module}' does not contain an "
                f"implementation of class '{cls.__name__}'"
            )
        elif len(classes) > 1:
            raise AssertionError(
                f"module '{module}' contains multiple "
                f"implementations of class '{cls.__name__}'"
            )

        # Return the implementing class
        return classes[0][1]

    else:
        raise ValueError(f"could not find module '{module}'")


def fix_launcher_metadata() -> None:
    if platform.system() != "Linux":
        return
    try:
        procs = [
            subprocess.Popen(
                [
                    "gio",
                    "set",
                    str(item),
                    "metadata::caja-trusted-launcher",
                    "true",
                ]
            )
            for item in get_pipe_path().parent.iterdir()
            if item.suffix == ".desktop"
        ]
        for p in procs:
            p.wait()

    except Exception:
        pass


def get_anim_path() -> Path:
    return get_production_path().parent / "anim"


def get_asset_path() -> Path:
    return get_production_path() / "asset"


def get_character_path() -> Path:
    return get_production_path().parent / "character"


def get_edit_path() -> Path:
    return get_production_path().parent / "edit/shots"


def get_pipe_path() -> Path:
    return Path(__file__).resolve().parents[1]


def get_previs_path() -> Path:
    return get_production_path().parent / "previs"


def get_production_path() -> Path:
    return _prp


def get_rigging_path() -> Path:
    return get_character_path() / "Rigging"


def resolve_mapped_path(path: str | Path) -> Path:
    """Windows mapped drive workaround. Adapated from: https://bugs.python.org/msg309160"""
    path = Path(path).resolve()

    if platform.system() != "Windows":
        return path

    mapped_paths = []
    for drive in "ZYXWVUTSRQPONMLKJIHGFEDCBA":
        root = Path("{}:/".format(drive))
        try:
            mapped_paths.append(root / path.relative_to(root.resolve()))
        except (ValueError, OSError):
            pass
    return min(mapped_paths, key=lambda x: len(str(x)), default=path)


ROOT = Path(__file__).parents[1]
venv_version: str

with open(ROOT / ".venv/pyvenv.cfg", "r") as cfg:
    for line in cfg:
        if not line.startswith("version_info"):
            continue
        version_str = line.split(" = ")[1]
        venv_version = "python" + ".".join(version_str.split(".", 2)[:2])
        break

SITEDIR = ROOT / ".venv/lib" / venv_version / "site-packages"
site.addsitedir(str(SITEDIR))


__all__ = [
    "houdini",
    "maya",
    "nuke",
    "substance_designer",
    "substance_painter",
    "unreal",
]


# allow embedded variables to update
hou.allowEnvironmentToOverwriteVariable("HOUDINI_ASSETGALLERY_DB_FILE", True)
hou.allowEnvironmentToOverwriteVariable("JOB", True)


# set the default flipbook resolution
scene = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
fb_settings = scene.flipbookSettings()  # type: ignore[union-attr]
fb_settings.resolution((1920, 816))


try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    resolutionx = me.parm("resolutionx")
    resolutiony = me.parm("resolutiony")
    aspectRatioConformPolicy = me.parm("aspectRatioConformPolicy")
    assert resolutionx is not None
    assert resolutiony is not None
    assert aspectRatioConformPolicy is not None
    resolutionx.set(1920)
    resolutiony.set(816)
    aspectRatioConformPolicy.set("cropAperture")
except Exception:  # in case this is created as a locked node
    pass


try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    primpath = me.parm("primpath")
    assert primpath is not None
    primpath.set("`@PATH`/$OS")
except Exception:  # in case this is created as a locked node
    pass


try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    tabmenumask = me.parm("tabmenumask")
    assert tabmenumask is not None
    tabmenumask.set("risnet USD  ^hmtlx* MaterialX collect parameter subnet")
except Exception:  # in case this is created as a locked node
    pass


try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    res_mode = me.parm("res_mode")
    resolution1 = me.parm("resolution1")
    resolution2 = me.parm("resolution2")
    aspectRatioConformPolicy = me.parm("aspectRatioConformPolicy")
    assert res_mode is not None
    assert resolution1 is not None
    assert resolution2 is not None
    assert aspectRatioConformPolicy is not None
    res_mode.set("manual")
    resolution1.set(1920)
    resolution2.set(816)
    aspectRatioConformPolicy.set("cropAperture")
except Exception:  # in case this is created as a locked node
    pass


try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    overscan = me.parm("overscan")
    renderer = me.parm("renderer")
    assert overscan is not None
    assert renderer is not None
    overscan.set(6.0)
    renderer.set("HdPrmanLoaderRendererPlugin")
except Exception:  # in case this is created as a locked node
    pass


try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    resx = me.parm("resx")
    resy = me.parm("resy")
    assert resx is not None
    assert resy is not None
    # set the default resolution
    resx.set(1920)
    resy.deleteAllKeyframes()  # remove the expression
    resy.set(816)
except Exception:  # in case this is created as a locked node
    pass


try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    basename = me.parm("basename")
    assert basename is not None
    basename.set("$OS")
except Exception:  # in case this is created as a locked node
    pass


if TYPE_CHECKING:
    import typing

"""Interfaces for interacting with DCCs"""


class DCCInterface(metaclass=ABCMeta):
    """interface for DCCs"""

    @abstractmethod
    def __init__(self):
        """Initialize the DCC"""
        raise NotImplementedError

    @abstractmethod
    def launch(self) -> None:
        """Launch the software"""
        raise NotImplementedError


class DCCLocalizerInterface(metaclass=ABCMeta):
    """interface for functions that need to be localized to the DCC"""

    @abstractmethod
    def __init__(self) -> None:
        """Initialize the pipe instance"""
        raise NotImplementedError

    @abstractmethod
    def get_main_qt_window(self) -> typing.Any:
        """Get the QT object representing the main application window.
        Use for the parent of other QT popups"""
        raise NotImplementedError

    @abstractmethod
    def is_headless(self) -> bool:
        """Check if this is a headless environment (no GUI)"""
        raise NotImplementedError


"""Initialize Maya environment on startup"""


def main():
    # Enable required plugins
    plugins = [
        "mayaUsdPlugin",
    ]
    pluginInfo = mc.pluginInfo(q=True, listPlugins=True)
    for plugin in plugins:
        if plugin not in pluginInfo:
            mc.loadPlugin(plugin)

    # set workspace
    mc.workspace(str(get_production_path().parent), openWorkspace=True)

    if not mc.about(batch=True):
        # enable timeline-marker plugin
        from timeline_marker import install  # type: ignore[import-not-found]

        install.execute()

    # register USD Export chaser
    import mayaUsd.lib as mayaUsdLib  # type: ignore[import-not-found]

    mayaUsdLib.ExportChaser.Register(ExportChaser, ExportChaser.ID)


mc.evalDeferred(main)


class MyWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MyWindow, self).__init__(parent)

        # Initialize shot lists
        self.a_shots = []
        self.b_shots = []
        self.c_shots = []
        self.d_shots = []
        self.e_shots = []
        self.f_shots = []
        self.g_shots = []

        # Get and parse shots
        shots_all = self.get_shots()
        self.parse_list(shots_all)

        self.setWindowTitle("L&D Comp Open Shot")
        self.setWindowFlags(
            self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint
        )  # Keep on top

        # Create sequence dropdown
        sequence_dropdown_vlayout = QtWidgets.QVBoxLayout()
        label1 = QtWidgets.QLabel("Sequence")
        self.sequence_combobox = QComboBox()
        self.sequence_combobox.addItems(["A", "B", "C", "D", "E", "F", "G"])
        sequence_dropdown_vlayout.addWidget(label1)
        sequence_dropdown_vlayout.addWidget(self.sequence_combobox)

        # Create shot numbers dropdown
        shotnum_dropdown_vlayout = QtWidgets.QVBoxLayout()
        label2 = QtWidgets.QLabel("Shot Number")
        self.shotnum_combobox = QComboBox()
        shotnum_dropdown_vlayout.addWidget(label2)
        shotnum_dropdown_vlayout.addWidget(self.shotnum_combobox)

        # Initially populate with shots for sequence A
        self.populate_shotnum("A")

        # Both dropdowns horizontal layout
        dropdowns = QtWidgets.QHBoxLayout()
        dropdowns.addLayout(sequence_dropdown_vlayout)
        dropdowns.addLayout(shotnum_dropdown_vlayout)

        # button
        button = QtWidgets.QPushButton("Open Shot")
        # selected_shot = self.shotnum_combobox.currentText()
        button.clicked.connect(
            lambda: (
                self.open_nk_shot(self.shotnum_combobox.currentText()),
                self.close(),
            )
        )

        # Main layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(dropdowns)
        main_layout.addWidget(button)
        self.setLayout(main_layout)

        # Update shotnum_combobox when the sequence changes
        self.sequence_combobox.currentTextChanged.connect(self.populate_shotnum)

    def populate_shotnum(self, sequence):
        """Update shotnum_combobox with shots corresponding to the selected sequence."""
        self.shotnum_combobox.clear()
        if sequence == "A":
            for shot in self.a_shots:
                self.shotnum_combobox.addItem(shot)
        elif sequence == "B":
            for shot in self.b_shots:
                self.shotnum_combobox.addItem(shot)
        elif sequence == "C":
            for shot in self.c_shots:
                self.shotnum_combobox.addItem(shot)
        elif sequence == "D":
            for shot in self.d_shots:
                self.shotnum_combobox.addItem(shot)
        elif sequence == "E":
            for shot in self.e_shots:
                self.shotnum_combobox.addItem(shot)
        elif sequence == "F":
            for shot in self.f_shots:
                self.shotnum_combobox.addItem(shot)
        elif sequence == "G":
            for shot in self.g_shots:
                self.shotnum_combobox.addItem(shot)

    def get_shots(self):
        from env_sg import DB_Config

        conn = DB.Get(DB_Config)

        # force refresh cache
        conn.expire_cache()
        conn.get_shot_code_list()

        shots = conn.get_shot_code_list()
        return shots

    def parse_list(self, shots):
        for shot in shots:
            if len(shot) < 2 or shot[1] != "_" or not shot[0].isalpha():
                continue
            letter = shot[0].upper()
            if letter == "A":
                self.a_shots.append(shot)
            elif letter == "B":
                self.b_shots.append(shot)
            elif letter == "C":
                self.c_shots.append(shot)
            elif letter == "D":
                self.d_shots.append(shot)
            elif letter == "E":
                self.e_shots.append(shot)
            elif letter == "F":
                self.f_shots.append(shot)
            elif letter == "G":
                self.g_shots.append(shot)

        # Sort each list alphabetically
        self.a_shots.sort()
        self.b_shots.sort()
        self.c_shots.sort()
        self.d_shots.sort()
        self.e_shots.sort()
        self.f_shots.sort()
        self.g_shots.sort()

    def check_file_exists(self, shot_num):
        file_path_os = (
            "/groups/dungeons/production/shot/" + shot_num + "/comp/" + shot_num + ".nk"
        )
        if os.path.exists(file_path_os):
            print(f"File '{file_path_os}' exists.")
            return
        else:
            print(f"File '{file_path_os}' does not exist. Creating now.")

            shot_folder = "/groups/dungeons/production/shot/" + shot_num
            comp_folder = "/groups/dungeons/production/shot/" + shot_num + "/comp/"

            if not os.path.exists(shot_folder):
                os.mkdir(shot_folder)  # create the shot folder
            if not os.path.exists(comp_folder):
                os.mkdir(comp_folder)  # create the comp folder
            nuke.scriptSaveAs(file_path_os)  # create the .nk file
            return

    def open_nk_shot(self, shot_num):
        self.check_file_exists(shot_num)
        nk_file_path = (
            "/groups/dungeons/production/shot/" + shot_num + "/comp/" + shot_num + ".nk"
        )
        try:
            nuke.scriptOpen(nk_file_path)
            print(f"Successfully opened script: {nk_file_path}")
        except RuntimeError as e:
            print(f"Error opening script: {e}")


def run():
    global window  # Prevent garbage collection
    window = MyWindow()
    window.show()


# run()


nuke.pluginAddPath("./NukeSurvivalToolkit_publicRelease/NukeSurvivalToolkit")
nuke.pluginAddPath("./NungeonTools")


# We need to always import typing for defining the structs
# attrs doesn't support `|` syntax in 3.9


_S = TypeVar("_S")

_SG_NAME = "sg_name"
_STRUCT_HOOK = "struct_hook"
_UNSTRUCT_HOOK = "unstruct_hook"
_con = cattrs.Converter()

_con.register_structure_hook_factory(
    attrs.has,
    lambda cls: cattrs.gen.make_dict_structure_fn(
        cls,
        _con,
        **{  # type: ignore[arg-type]
            f.name: cattrs.gen.override(
                rename=f.metadata.get(_SG_NAME, None),
                struct_hook=f.metadata.get(_STRUCT_HOOK, None),
                unstruct_hook=f.metadata.get(_UNSTRUCT_HOOK, None),
            )
            for f in attrs.fields(cls)
        },
    ),
)


@attrs.define
class SGDiffable(Diffable):
    @classmethod
    def from_sg(cls: Type[_S], sg_dict: Optional[dict]) -> _S:
        if not sg_dict:
            raise TypeError(f"Cannot create {cls.__name__} from empty dict")
        return _con.structure(sg_dict, cls)

    @classmethod
    def map_sg_field_names(cls: Type[attrs.AttrsInstance], name: str) -> str:
        """take SG name and map it to the field name on this class"""
        return next(
            (
                f.metadata.get(_SG_NAME, None) or f.name
                for f in attrs.fields(cls)
                if f.name == name
            ),
            "",
        )

    def sg_diff(self) -> dict[str, Any]:
        """Return a dict with changes made to the asset since it was
        initialized, in the form that ShotGrid expects"""
        sg_diff: dict[str, Any] = self.diff()
        for f in attrs.fields(self.__class__):
            if f.name in sg_diff:
                if hk := f.metadata.get(_UNSTRUCT_HOOK, None):
                    sg_diff[f.name] = hk(sg_diff[f.name], None)
                if nname := f.metadata.get(_SG_NAME, None):
                    sg_diff[nname] = sg_diff[f.name]
                    del sg_diff[f.name]
        return sg_diff


@attrs.define
class SGEntity(SGDiffable):
    code: str
    id: int = field(on_setattr=attrs.setters.frozen)
    path: Optional[str] = field(
        default=None, kw_only=True, metadata={_SG_NAME: "sg_path"}
    )


@attrs.define
class SGEntityStub(SGDiffable):
    id: int


@attrs.frozen
class AssetStub(SGEntityStub):
    """Represent "stubs" that come from ShotGrid
    Stubs are JSON objects with 3 fields: id, name, and type (which is always Asset in this case)
    """

    disp_name: str = field(metadata={_SG_NAME: "name"})


@attrs.define
class Asset(SGEntity):
    name: str = field(metadata={_SG_NAME: "sg_pipe_name"})
    material_variants: set[str] = field(
        metadata={
            _SG_NAME: "sg_material_variants",
            _STRUCT_HOOK: lambda mv, _: set(mv.split(",") if mv else []),
            _UNSTRUCT_HOOK: lambda mv, _: ",".join(mv) if mv else "",
        }
    )
    parent: Optional[AssetStub] = field(
        metadata={
            _SG_NAME: "parents",
            _STRUCT_HOOK: lambda p, _: AssetStub.from_sg(p[0]) if len(p) else None,
            _UNSTRUCT_HOOK: lambda p, _: [p] if p else [],
        },
        on_setattr=attrs.setters.frozen,
    )
    variants: list[AssetStub] = field(metadata={_SG_NAME: "assets"})
    version = None

    @property
    def disp_name(self) -> str:
        """Alias for code"""
        return self.code or ""

    @property
    def is_variant(self) -> bool:
        return "_" in self.name

    @property
    def tex_path(self) -> Optional[str]:
        return f"{self.path}/tex/" + (self.variant_name or "main")

    @property
    def variant_name(self) -> Optional[str]:
        if not self.is_variant:
            return None
        return self.name.split("_")[1]


@attrs.define
class Environment(SGEntity):
    name: str = field(metadata={_SG_NAME: "sg_pipe_name"})

    @property
    def disp_name(self) -> str:
        """Alias for code"""
        return self.code or ""


@attrs.define
class EnvironmentStub(AssetStub):
    pass


@attrs.frozen
class SequenceStub(SGEntityStub):
    """Represent sequence "stubs" that come from ShotGrid"""

    code: str = field(metadata={_SG_NAME: "name"})


@attrs.define
class Sequence(SGEntity):
    code: str = field(on_setattr=attrs.setters.frozen)
    shots: list[ShotStub]
    set: Optional[EnvironmentStub] = field(
        metadata={
            _SG_NAME: "sg_set",
            _STRUCT_HOOK: lambda e, _: EnvironmentStub.from_sg(e) if e else None,
        }
    )


@attrs.frozen
class ShotStub(SGEntityStub):
    """Represent shot "stubs" that come from ShotGrid"""

    code: str = field(metadata={_SG_NAME: "name"})


@attrs.define
class Shot(SGEntity):
    assets: list[AssetStub] = field(
        metadata={_STRUCT_HOOK: lambda aa, _: [AssetStub.from_sg(a) for a in aa]}
    )
    code: str = field(on_setattr=attrs.setters.frozen)
    cut_in: int = field(metadata={_SG_NAME: "sg_cut_in"})
    cut_out: int = field(metadata={_SG_NAME: "sg_cut_out"})
    cut_duration: int = field(metadata={_SG_NAME: "sg_cut_duration"})
    sequence: Optional[SequenceStub] = field(
        metadata={
            _SG_NAME: "sg_sequence",
            _STRUCT_HOOK: lambda s, _: SequenceStub.from_sg(s) if s else None,
        }
    )
    set: Optional[EnvironmentStub] = field(
        metadata={
            _SG_NAME: "sg_set",
            _STRUCT_HOOK: lambda e, _: EnvironmentStub.from_sg(e) if e else None,
        }
    )
    substeps: int = field(
        default=1, metadata={_SG_NAME: "sg_substeps", _STRUCT_HOOK: lambda s, _: s or 1}
    )


class DisplacementSource(IntEnum):
    NONE = 0
    HEIGHT = 1
    DISPLACEMENT = 2


class NormalSource(IntEnum):
    NORMAL_HEIGHT = 0
    NORMAL_ONLY = 1


class NormalType(IntEnum):
    STANDARD = 0
    BUMP_ROUGHNESS = 1


@attrs.define
class TexSetInfo(JsonSerializable):
    displacement_source: DisplacementSource = DisplacementSource.NONE
    has_udims: bool = True
    normal_source: NormalSource = NormalSource.NORMAL_HEIGHT
    normal_type: NormalType = NormalType.STANDARD


@attrs.define
class MaterialInfo(JsonSerializable):
    tex_sets: dict[str, TexSetInfo] = dict()


if TYPE_CHECKING:
    from .db import Shot


PREROLL_DURATION = 55


@attrs.define(frozen=True)
class Timeline(JsonSerializable):
    start: int
    end: int
    head_duration: int = attrs.field(default=5)
    tail_duration: int = attrs.field(default=5)
    preroll_duration: int = attrs.field(default=PREROLL_DURATION)
    head: int = attrs.field(
        init=False,
        default=attrs.Factory(lambda s: s.start - s.head_duration, takes_self=True),
    )
    tail: int = attrs.field(
        init=False,
        default=attrs.Factory(lambda s: s.end + s.tail_duration, takes_self=True),
    )
    preroll: int = attrs.field(
        init=False,
        default=attrs.Factory(lambda s: s.head - s.preroll_duration, takes_self=True),
    )

    @classmethod
    def from_shot(
        cls: type[Timeline], shot: Shot, preroll_duration: int = PREROLL_DURATION
    ) -> Timeline:
        return cls(
            start=shot.cut_in,
            end=shot.cut_out,
            preroll_duration=preroll_duration,
            head_duration=5,
            tail_duration=5,
        )


def run():
    picker_folder_path = get_rigging_path() / "Pickers"

    picker_filepaths = [
        str(p) for p in picker_folder_path.iterdir() if p.suffix == ".json"
    ]
    print("Picker filepaths", picker_filepaths)

    dwpicker.show(pickers=picker_filepaths)


def run():
    libraries = [
        {
            "name": "LnD Poses",
            "path": str(get_anim_path() / "studiolibrary/lnd-poses"),
            "default": True,
            "theme": {
                "accentColor": "rgb(97, 30, 10)",
            },
        },
    ]
    studiolibrary.setLibraries(libraries)
    studiolibrary.main()


# create embedded $ASSET variable if needed
hip_path = resolve_mapped_path(hou.hscriptStringExpression("$HIP"))
if any(get_production_path() / p in hip_path.parents for p in ["asset", "character"]):
    if not hou.contextOption("ASSET"):
        hou.setContextOption("ASSET", hip_path.name)

# ensure ASSETGALLERY_DATA_SOURCE is correct
hou.hscript(
    f"setenv ASSETGALLERY_DATA_SOURCE='{os.getenv('HOUDINI_ASSETGALLERY_DATA_SOURCE')}'"
)

# mark any node referencing above vars as dirty
hou.hscript("varchange")


"""This OnCreated hook runs whenever an Asset Reference node is created and
   ensures that the filepath is always relative to $JOB"""


def update_filepath(
    node: hou.Node, parm_tuple: hou.ParmTuple, event_type: hou.nodeEventType, **kwargs
) -> None:
    if parm_tuple.name() != "filepath":
        return
    # this callback only needs to run once
    node.removeEventCallback([event_type], callback=update_filepath)  # type: ignore[list-item]

    path = Path(parm_tuple.evalAsStrings()[0])
    ppth = get_production_path()

    if not path.is_relative_to(ppth):
        if ppth.anchor == "G:\\":
            path = Path("G:/") / path.relative_to("/groups")
        else:
            path = Path("/groups") / path.relative_to("G:/")

    parm_tuple.set(("$JOB/" + str(path.relative_to(ppth)).replace("\\", "/"),))


def update_destination_prim(
    node: hou.Node, parm_tuple: hou.ParmTuple, event_type: hou.nodeEventType, **kwargs
) -> None:
    if parm_tuple.name() != "primpath":
        return
    # this callback only needs to run once
    node.removeEventCallback([event_type], callback=update_destination_prim)  # type: ignore[list-item]

    # don't mess with this if we're inside a Layout node
    if node.parent().name() == "ASSETS":
        return

    primpath = parm_tuple.evalAsStrings()[0]
    parm_tuple.set((f"`@PATH`{primpath}",))


try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    if not me.parent().name() == "ASSETS":
        for callback in (update_filepath, update_destination_prim):
            me.addEventCallback([hou.nodeEventType.ParmTupleChanged], callback=callback)
except Exception:  # in case this is created as a locked node
    pass


try:
    me: hou.Node = kwargs["node"]  # type: ignore[name-defined] # noqa: F821
    rmantree = me.parm("rmantree_override")
    passthrough = me.parm("passthrough")
    assert rmantree is not None
    assert passthrough is not None
    rmantree.set(str(get_production_path() / "opt/pixar/RenderManProServer-26.3"))
    passthrough.set(
        " ".join(
            "/Render/Products/Vars/" + var
            for var in ["__Nworld", "__Pworld", "__st", "normal"]
        )
    )
except Exception:  # in case this is created as a locked node
    pass


nuke.pluginAddPath("./gizmos")
nuke.pluginAddPath("./icons")
nuke.pluginAddPath("./images")
nuke.pluginAddPath("./nk_files")
nuke.pluginAddPath("./toolsets")
nuke.pluginAddPath("./scripts")

# aspect ratio
nuke.addFormat("1920 816 Love_and_Dungeons_aspect_ratio")


def make_ld_write_node():
    import ld_write_node_v2  # type: ignore[import-not-found]

    ld_write_node_v2.main()


def import_render_layers():
    import render_layer_selector  # type: ignore[import-not-found]

    render_layer_selector.run()


def import_USD_cam():
    import import_usd_camera  # type: ignore[import-not-found]

    import_usd_camera.run()


def choose_shot():
    import open_shot  # type: ignore[import-not-found]

    open_shot.run()


def set_frameRange_and_aspectRatio():
    import set_frameRange_and_aspectRatio  # type: ignore[import-not-found]

    set_frameRange_and_aspectRatio.run()


################################### Nungeon buttons (Sidebar) ###################################
toolbar = nuke.menu("Nodes")
m = toolbar.addMenu("Nungeon", icon="nungeonIcon.png")

m.addCommand(
    "Wireframe Breakdown",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/wireframe_breakdown.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Template",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/shotTemplate.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Depth Fog",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/depth_fog.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Deep Fog",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/deep_fog.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Fix Snow Flashes",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/ld_snow_glitter_clamp.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Lightwrap (upper matrix)",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/ld_lightwrap.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Relight",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/relight_template.nk")}")',
    icon="nungeonIcon.png",
)

m.addCommand(
    "Eye Light",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/eyelights.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Sky Dome (Basic)",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/ld_skydome_basic.nk")}")',
    icon="nungeonIcon.png",
)
m.addCommand(
    "Fix Snow Sparkles in fog layer",
    f'nuke.nodePaste("{str(get_pipe_path() / "software/nuke/tools/NungeonTools/toolsets/ld_snow_glitter_clamp.nk")}")',
    icon="nungeonIcon.png",
)

# m.addCommand("FrameBurn", "nuke.createNode('FrameBurn')", icon="nungeonIcon.png")
m.addCommand("Grade_AOV", "nuke.createNode('grade_AOV')", icon="nungeonIcon.png")
m.addCommand("luma Distort", "nuke.createNode('lumaDistort')", icon="nungeonIcon.png")
m.addCommand("Roughen Edges", "nuke.createNode('roughenEdges')", icon="nungeonIcon.png")
# lens node
m.addCommand("Lens", "nuke.createNode('Lens')", icon="nungeonIcon.png")
print(
    f"nuke.nodePaste({str(get_pipe_path() / 'software/nuke/tools/NungeonTools/toolsets/shotTemplate.nk')})"
)
m.addCommand("L&D Write Node", "make_ld_write_node()", icon="nungeonIcon.png")


################################### Nungeon Shelf Tool Buttons ###################################
menu = nuke.menu("Nuke")
menu.addCommand("[Choose Shot]", "choose_shot()")
menu.addCommand("[Import Render Layers]", "import_render_layers()")
menu.addCommand("[Import USD Camera]", "import_USD_cam()")
menu.addCommand("[Set Project Settings]", "set_frameRange_and_aspectRatio()")


_SHELF_NAME = "lnd-resources"


def start_plugin():
    # create the LnD shelf
    sp.resource.Shelves().add(
        _SHELF_NAME, str(get_production_path() / "painter_assets")
    )


def close_plugin():
    sp.resource.Shelves().remove(_SHELF_NAME)


if __name__ == "__main__":
    window = start_plugin()


r"""Launch the BYU 2025 Capstone pipeline ("Love & Dungeons")

With much credit to Matthew Minson and the 2024 Capstone team.

When run as a script, parse the software from the command line
arguments, then run launch().
"""


# Configure logging
log = logging.getLogger(__name__)


def getLevelNamesMapping():
    """Implement the same-named method from the logging module.

    TODO: REPLACE ONCE OUR PYTHON IS >= 3.11
    """
    return logging._nameToLevel.keys()


def launch(
    software_name: str,
    is_python_shell: bool = False,
    extra_args: list[str] | None = None,
) -> None:
    if sys.platform == "linux":
        # raise file descriptor limit for the enclosing Python process
        import resource

        _, max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (max_fd, max_fd))

    software_map: dict[str, type[DCCInterface]] = {
        "houdini": HoudiniDCC,
        "maya": MayaDCC,
        "nuke": NukeDCC,
        "substance_designer": SubstanceDesignerDCC,
        "substance_painter": SubstancePainterDCC,
    }
    if software_name not in software_map:
        raise ValueError(f"unknown software '{software_name}'")
    software_map[software_name](is_python_shell, extra_args).launch()


if __name__ == "__main__":
    parser = ArgumentParser(description="Launch pipeline software")
    parser.add_argument(
        "software",
        help="launch the specified software",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        help="log at the specified level. Possible values are %(choices)s (default: %(default)s)",
        choices=getLevelNamesMapping(),
        default=logging.getLevelName(logging.root.level),
        type=str.upper,
        metavar="LEVEL",
    )
    parser.add_argument(
        "-p",
        "--python",
        help="Open a Python shell in this DCC instead of launching the GUI",
        action="store_true",
    )

    args, extras = parser.parse_known_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(processName)s(%(process)s) %(threadName)s [%(name)s(%(lineno)s)] [%(levelname)s] %(message)s",
    )

    # Windows Python explicitly needs site.main to be called
    site.main()

    launch(args.software, args.python, extras)

    log.info("Exiting")


if TYPE_CHECKING:
    import typing


"""Baseclasses for interacting with DCCs"""

log = logging.getLogger(__name__)


class DCC(DCCInterface):
    command: str
    args: list[str] | None
    env_vars: typing.Mapping[str, int | str | None]
    pre_launch_tasks: typing.Callable[[], None]

    def __init__(
        self,
        command: str,
        args: typing.Sequence[str] | None = None,
        env_vars: typing.Mapping[str, int | str | None] | None = None,
        pre_launch_tasks: typing.Callable[[], None] | None = None,
    ) -> None:
        """Initialize DCC object.

        Keyword arguments:
        - command -- the command to launch the software
        - args    -- the arguments to pass to the command
        """

        if args is None:
            args = []

        self.command = command
        self.args = list(args) if args else None
        self.env_vars = env_vars or {}
        self.pre_launch_tasks = pre_launch_tasks or (lambda: None)

    def _get_env_vars(
        self, env_vars: typing.Mapping[str, int | str | None] | None = None
    ) -> dict[str, str]:
        """(Un)Set environment variables to their associated values.

        All values will be converted to strings. If a value is None,
        that environment variable will be unset.
        """
        BASE_ENVIRON = "BASE_ENVIRON"

        if BASE_ENVIRON not in os.environ:
            venv = os.environ.copy()
            venv[BASE_ENVIRON] = json.dumps(venv)
        else:
            venv = json.loads(os.environ[BASE_ENVIRON])

        if env_vars is None:
            env_vars = self.env_vars

        log.info("(Un)setting environment vars")

        for key, val in env_vars.items():
            if val is None:
                if key in venv:
                    del venv[key]
            else:
                venv[key] = str(val)

        PYTHONPATH = "PYTHONPATH"
        if PYTHONPATH not in venv:
            venv[PYTHONPATH] = ""

        print(venv[PYTHONPATH])
        return venv

    def launch(
        self,
        command: str | None = None,
        args: typing.Sequence[str] | None = None,
        pre_launch_tasks: typing.Callable[[], None] | None = None,
    ) -> None:
        """Launch the software with the specified arguments.

        Passing in optional parameters will override their default
        values.
        """

        if command is None:
            command = self.command
        if args is None:
            args = self.args
        if pre_launch_tasks is None:
            pre_launch_tasks = self.pre_launch_tasks

        fix_launcher_metadata()
        pre_launch_tasks()
        venv = self._get_env_vars()

        log.info("Launching the software")
        log.debug(f"Command: {command}, Args: {args}")
        subprocess.call([command] + list(args or []), env=venv)


class DCCLocalizer(DCCLocalizerInterface):
    id: str

    def __init__(self, id: str) -> None:
        self.id = id


if TYPE_CHECKING:
    import typing


def _check_methods(cls: type, subclass: type) -> bool:
    """Check if a class implements another class's methods."""
    # Get the names of the class's methods
    methods: list = [member[0] for member in getmembers(cls, isfunction)]

    # Get the subclass's method resolution order (MRO)
    mro = subclass.__mro__

    # Check if the subclass's MRO contains every method
    for method in methods:
        for entry in mro:
            if method in entry.__dict__:
                if entry.__dict__[method] is None:
                    return NotImplemented
                break
        else:
            return NotImplemented
    return True


class DBInterface(metaclass=ABCMeta):
    """Interface for database interaction"""

    class ChildQueryMode(Enum):
        # children + assets w/ no children
        LEAVES = 0
        # all
        ALL = 1
        # only assets that have parents
        CHILDREN = 2
        # only assets that have children
        PARENTS = 3
        # top-level assets regardless of if they have children
        ROOTS = 4

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        return _check_methods(cls, subclass)

    @abstractmethod
    def __init__(self) -> None:
        """Initialize the DB"""
        raise NotImplementedError

    @abstractmethod
    def get_entity_by_attr(
        self, entity_type: type[SGEntity], attr: str, attr_val: str | int
    ) -> SGEntity:
        """Get an entity by an attribute"""
        raise NotImplementedError

    @abstractmethod
    def get_entity_by_stub(
        self, entity_type: type[SGEntity], stub: SGEntityStub
    ) -> SGEntity:
        """Get an entity from a stub"""
        raise NotImplementedError

    @abstractmethod
    def get_entities_by_stub(
        self, entity_type: type[SGEntity], stubs: typing.Iterable[SGEntityStub]
    ) -> list[SGEntity]:
        """Get a list of entities from a list of stubs (all stubs must be of
        type `entity_type`)"""
        raise NotImplementedError

    @abstractmethod
    def get_entity_attr_list(
        self, entity_type: type[SGEntity], attr: str, *, sorted: bool
    ) -> list[str]:
        """Get a list of values of a specific attribute on the entities of a
        specified type"""
        raise NotImplementedError

    @abstractmethod
    def get_entity_code_list(
        self,
        entity_type: type[SGEntity],
        *,
        sorted: bool = False,
        child_mode: DBInterface.ChildQueryMode | None = None,
    ) -> list[str]:
        """Get a list of codes/names for the given entity type"""
        raise NotImplementedError

    @abstractmethod
    def get_entity_by_code(self, entity_type: type[SGEntity], code: str) -> SGEntity:
        """Get an entity by its code and type"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_by_attr(self, attr: str, attr_val: str | int) -> Asset:
        """Get an asset that matches a specific attribute"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_by_name(self, attr_val: str | int) -> Asset:
        """Get an asset by its name"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_by_id(self, attr_val: str | int) -> Asset:
        """Get an asset by its id"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_by_stub(self, stubs: AssetStub) -> Asset:
        """Get an asset from a stub"""
        raise NotImplementedError

    @abstractmethod
    def get_assets_by_stub(self, stubs: typing.Iterable[AssetStub]) -> list[Asset]:
        """Get a list of assets from a list of stubs"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_attr_list(
        self,
        attr: str,
        *,
        child_mode: DBInterface.ChildQueryMode,
        sorted: bool = False,
    ) -> list[str]:
        """Get a list of a single attribute on the asset list"""
        raise NotImplementedError

    @abstractmethod
    def get_asset_name_list(
        self, child_mode: DBInterface.ChildQueryMode, sorted: bool
    ) -> list[str]:
        """Get a list of asset names"""
        raise NotImplementedError

    @abstractmethod
    def get_assets_by_name(self, names: typing.Iterable[str]) -> list[Asset]:
        """Get a list of assets from a list of names"""
        raise NotImplementedError

    @abstractmethod
    def update_asset(self, asset: Asset) -> bool:
        """Update an asset in the DB"""
        raise NotImplementedError

    @abstractmethod
    def get_env_by_attr(self, attr: str, attr_val: str | int) -> Environment:
        """Get an environment based off of an attribute"""
        raise NotImplementedError

    @abstractmethod
    def get_env_by_code(self, code: str) -> Environment:
        """Get an environment based of its code"""
        raise NotImplementedError

    @abstractmethod
    def get_env_by_id(self, id: int) -> Environment:
        """Get an environment based off its id"""
        raise NotImplementedError

    @abstractmethod
    def get_env_by_stub(self, stub: EnvironmentStub) -> Environment:
        """Get an environment from its stub"""
        raise NotImplementedError

    @abstractmethod
    def get_envs_by_stub(
        self, stubs: typing.Iterable[EnvironmentStub]
    ) -> list[Environment]:
        """Get a list of environments from a list of EnvironmentStubs"""
        raise NotImplementedError

    @abstractmethod
    def get_env_attr_list(self, attr: str, *, sorted: bool) -> list[str]:
        """Get a list of values of an attribute on the environments"""
        raise NotImplementedError

    @abstractmethod
    def get_env_code_list(self, sorted: bool) -> list[str]:
        """Get a list of environment codes"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_by_attr(self, attr: str, attr_val: str | int) -> Sequence:
        """Get a sequence based off an attribute"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_by_code(self, code: str) -> Sequence:
        """Get a sequence based off the code"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_by_id(self, id: int) -> Sequence:
        """Get a sequence from the ID"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_by_stub(self, stub: SequenceStub) -> Sequence:
        """Get a sequence from a stub"""
        raise NotImplementedError

    @abstractmethod
    def get_sequences_by_stub(
        self, stubs: typing.Iterable[SequenceStub]
    ) -> list[Sequence]:
        """Get a list of sequences from a list of SequencStubs"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_attr_list(self, attr: str, *, sorted: bool) -> list[str]:
        """Get a list of sequence attributes"""
        raise NotImplementedError

    @abstractmethod
    def get_sequence_code_list(self, sorted: bool) -> list[str]:
        """Get a list of sequence codes"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_by_attr(self, attr: str, attr_val: str | int) -> Shot:
        """Get a shot based off of an attribute"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_by_code(self, code: str) -> Shot:
        """Get a shot based of its code"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_by_id(self, id: int) -> Shot:
        """Get a shot based off its id"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_by_stub(self, stub: ShotStub) -> Shot:
        """Get a shot from its stub"""
        raise NotImplementedError

    @abstractmethod
    def get_shots_by_stub(self, stubs: typing.Iterable[ShotStub]) -> list[Shot]:
        """Get a list of shots from a list of ShotStubs"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_attr_list(self, attr: str, *, sorted: bool) -> list[str]:
        """Get a list of values of an attribute on the shots"""
        raise NotImplementedError

    @abstractmethod
    def get_shot_code_list(self, sorted: bool) -> list[str]:
        """Get a list of shot codes"""
        raise NotImplementedError


if TYPE_CHECKING:
    from pathlib import Path
    from typing import Callable, Literal


log = logging.getLogger(__name__)


def dummy_shot(code: str, cut_in: int, cut_out: int, cut_duration: int) -> Shot:
    """Generate a generic `Shot` object to hold cut info that doesn't
    correspond to a ShotGrid shot"""
    return Shot(
        code=code,
        id=0,
        assets=[],
        cut_in=cut_in,
        cut_out=cut_out,
        cut_duration=cut_duration,
        sequence=None,
        set=None,
    )


@dataclass
class HudDefinition:
    """
    Definition for a viewport HUD.
    Attributes
        name: str
            Internal name used by Maya for the HUD
        command: Callable[[], str]
            Command for the HUD to call
        section: int
            HUD section to occupy (see Maya docs)
        label: str
            String that precedes the return value of `command`
        event: str
            Event string that triggers a refresh (see Maya docs)
        idle_refresh: bool
            Alternative to `event`, will refresh every frame
        blockSize: Literal["small", "large"]
            Amount of HUD space to occupy
        labelFontSize: Literal["small", "large"]
    """

    name: str
    command: Callable[[], str]
    section: int
    label: str = ""
    event: str = ""
    idle_refresh: bool = False
    blockSize: Literal["small", "large"] = "small"
    labelFontSize: Literal["small", "large"] = "small"


@dataclass
class MShotDialogConfig:
    """Information needed to add a shot to the playblast dialog
    id: str
        Unique id for this shot
    name: str
        Display name of the shot
    save_locs: list[tuple[SaveLocation, bool]]
        List of save locations, paired with their default enable value
    """

    id: str
    name: str
    save_locs: list[tuple[SaveLocation, bool]]


@dataclass
class MShotPlayblastConfig:
    """Information needed to playblast a shot.
    Attributes:
        camera: str | None
            Camera to use. Value ignored if `use_sequencer` is set
        shot: Shot
            Shot struct to hold shot code, cut in, cut out, and duration
        paths: dict[Playblaster.PRESET, list[str | Path]]
            Paths to output to
        tails: tuple[int, int]
            How many frames early/late to start playblasting
        use_sequencer: bool = False
            Whether to playblast from the sequencer. If set to True, `camera`
            will be ignored
    """

    camera: str | None
    shot: Shot
    paths: dict[Playblaster.PRESET, list[str | Path]] = field(default_factory=dict)
    tails: tuple[int, int] = (0, 0)
    use_sequencer: bool = False

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_paths(self, paths: dict[Playblaster.PRESET, list[str | Path]]) -> None:
        self.paths = paths


@dataclass
class MPlayblastConfig:
    """Information needed to configure a Maya playblast
    Attributes:
        builtin_huds: list[str]
            List of valid Maya builtin HUD names
        custom_huds: list[HudDefinition]
            List of `HudDefinition`s
        dof: bool
            Toggle depth of field
        hardware_fog: bool
            Toggle hardware fog
        lighting: bool
            Toggle viewport lighting
        shadows: bool
            Toggle viewport shadows
        shots: list[MShotPlayblastConfig]
            List of shots to playblast
        ssao: bool
            Toggle viewport screen-space anti-aliasing
    """

    builtin_huds: list[str]
    custom_huds: list[HudDefinition]
    dof: bool
    hardware_fog: bool
    lighting: bool
    shadows: bool
    shots: list[MShotPlayblastConfig]
    ssao: bool


class SaveLocation:
    """Information needed for a save location. If a lambda is provided to
    `path` it will call that and return the value"""

    name: str
    preset: Playblaster.PRESET
    _path: str | Path | Callable[[], str | Path]

    def __init__(
        self,
        name: str,
        path: str | Path | Callable[[], str | Path],
        preset: Playblaster.PRESET,
    ):
        self.name = name
        self._path = path
        self.preset = preset

    @property
    def path(self) -> str | Path:
        if callable(self._path):
            return self._path()
        else:
            return self._path


class _HoudiniLocalizer(DCCLocalizer):
    def __init__(self) -> None:
        super().__init__("houdini")

    def get_main_qt_window(self) -> QtWidgets.QWidget | None:
        if not self.is_headless():
            return hou.qt.mainWindow()
        return None

    def is_headless(self) -> bool:
        return bool(re.match(r"^.*ython(?:\.exe)?3?", sys.executable))


_l = _HoudiniLocalizer()

get_main_qt_window = _l.get_main_qt_window
is_headless = _l.is_headless


class _MayaLocalizer(DCCLocalizer):
    def __init__(self) -> None:
        super().__init__("maya")

    def get_main_qt_window(self) -> QtWidgets.QWidget | None:
        if not self.is_headless():
            ptr = omUI.MQtUtil.mainWindow()
            if ptr is not None:
                return QtCompat.wrapInstance(int(ptr), QtWidgets.QWidget)  # type: ignore[attr-defined]
        return None

    def is_headless(self) -> bool:
        pattern = re.compile("^.*mayapy(?:\.?(?:bin|exe))$")
        return bool(pattern.match(sys.executable))


_l = _MayaLocalizer()

get_main_qt_window = _l.get_main_qt_window
is_headless = _l.is_headless


class _SubstancePainterLocalizer(DCCLocalizer):
    def __init__(self) -> None:
        super().__init__("substance_painter")

    def get_main_qt_window(self) -> QtWidgets.QWidget | None:
        return ui.get_main_window()

    def is_headless(self) -> bool:
        return False


_l = _SubstancePainterLocalizer()

get_main_qt_window = _l.get_main_qt_window
is_headless = _l.is_headless


if TYPE_CHECKING:
    import typing


log = logging.getLogger(__name__)

_PROD_DB = str(get_production_path() / "asset/assetGallery.db")
_TMPDIR = Path(os.getenv("TMPDIR", os.getenv("TEMP", "/tmp"))).resolve() / str(
    os.getpid()
)
_TMPDIR.mkdir(0o755, exist_ok=True)


class HoudiniDCC(DCC):
    """Houdini DCC class"""

    _assetdb_path: str
    _orig_assetdb_path: str

    def __init__(
        self, is_python_shell: bool = False, extra_args: list[str] | None = None
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        self._assetdb_path = str(_TMPDIR / "assetGallery.db")
        self._orig_assetdb_path = str(_TMPDIR / "assetGallery_orig.db")

        env_vars: typing.Mapping[str, int | str | None] | None
        env_vars = {
            "DCC": str(this_path.parent.name),
            # Asset Gallery sqlite db (set in 456.py)
            "HOUDINI_ASSETGALLERY_DATA_SOURCE": (
                self._assetdb_path
                if platform.system() == "Linux"
                else self._assetdb_path.replace("\\", "/")
            ),
            # Backup directory
            "HOUDINI_BACKUP_DIR": "./.backup",
            # Dump the core on crash to help debugging
            "HOUDINI_COREDUMP": 1,
            # Compiled Houdini files debug
            "HOUDINI_DSO_ERROR": 2 if log.isEnabledFor(logging.DEBUG) else None,
            # Max backup files
            "HOUDINI_MAX_BACKUP_FILES": 20,
            # Prevent user envs from overriding existing values
            "HOUDINI_NO_ENV_FILE_OVERRIDES": 1,
            # Disable start page splash
            "HOUDINI_NO_START_PAGE_SPLASH": 1,
            # Configure additional HDA locations outside of the pipeline
            "HOUDINI_OTLSCAN_PATH": os.pathsep.join(
                [
                    str(p)
                    for p in resolve_mapped_path(
                        get_production_path() / "hda"
                    ).iterdir()
                ]
                + ["&"]
            ),
            # Package loading debug logging
            "HOUDINI_PACKAGE_VERBOSE": 1 if log.isEnabledFor(logging.DEBUG) else None,
            # Houdini Path
            "HOUDINI_PATH": os.pathsep.join(
                [
                    str(pipe_path / "lib/usd/kinds"),
                    "&",
                ]
            ),
            # Splash file
            "HOUDINI_SPLASH_FILE": str(pipe_path / "lib/splash/dunginisplash19.5.png"),
            # Project-specific preference overrides
            "HSITE": str(resolve_mapped_path(this_path.parent / "hsite")),
            # Job directory
            "JOB": str(resolve_mapped_path(get_production_path())),
            # Ensure LD_LIBRARY_PATH is unset to allow nesting pipe instances
            "LD_LIBRARY_PATH": None,
            # Manually set LD_LIBRARY_PATH to integrated Houdini libraries (for Axiom)
            # "LD_LIBRARY_PATH": str(Executables.hfs / "dsolib")
            # if platform.system() == "Linux"
            # else None,
            # Set project OCIO config
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            # Pass log level defined on commandline
            "PIPE_LOG_LEVEL": log.getEffectiveLevel(),
            "PIPE_PATH": str(pipe_path),
            # Configure Asset Resolver
            "PXR_AR_DEFAULT_SEARCH_PATH": os.pathsep.join(
                [
                    str(get_production_path()),
                ]
            ),
            # USD Plugins
            "PXR_PLUGINPATH_NAME": os.pathsep.join(
                [
                    str(pipe_path / "lib/usd/kinds"),
                    os.environ.get("PXR_PLUGINPATH_NAME", ""),
                ]
            ),
            # Add pipe modules to Python path
            "PYTHONPATH": os.pathsep.join(
                [
                    str(resolve_mapped_path(pipe_path)),
                    # Add $RMANTREE/bin to PYTHONPATH for the Tractor PDG scheduler
                    # os.environ.get("RMANTREE", "") + "/bin",
                    str(
                        get_production_path()
                        / (
                            "opt/pixar/RenderManProServer-26.3"
                            if platform.system() == "Linux"
                            else "PFiles/Pixar/RenderManProServer-26.3"
                        )
                    ),
                ]
            ),
            # RenderMan color config json file
            "RMAN_COLOR_CONFIG_DIR": str(pipe_path / "lib/ocio/love-v01"),
            # Explicitly set Tractor location
            "TRACTOR_ENGINE": "tractor-engine.cs.byu.edu:443",
        }

        launch_command = ""
        if is_python_shell:
            launch_command = str(Executables.hython)
        else:
            launch_command = str(Executables.houdini)

        if is_python_shell:
            launch_args = extra_args or []
        else:
            launch_args = ["-foreground", "-desktop", "Solungeon", *(extra_args or [])]

        super().__init__(
            launch_command, launch_args, env_vars, lambda: self._set_up_asset_gallery()
        )

    def _set_up_asset_gallery(self) -> None:
        for f in _TMPDIR.glob("assetGallery.*"):
            f.unlink()

        shutil.copy(_PROD_DB, self._assetdb_path)
        shutil.copy(self._assetdb_path, self._orig_assetdb_path)

        atexit.register(lambda: self._merge_asset_gallery_changes())

    def _merge_asset_gallery_changes(self) -> None:
        # test if the gallery has changed
        filecmp.clear_cache()
        if filecmp.cmp(self._orig_assetdb_path, self._assetdb_path, shallow=False):
            return

        print("Merging asset gallery changes")

        lock_path = _PROD_DB + ".lock"

        lock = FileLock(lock_path)

        # merge local modifications into the prod database
        with lock.acquire(timeout=40), closing(sqlite3.connect(_PROD_DB)) as conn:
            cur = conn.cursor()
            with (
                attach_db(cur, self._assetdb_path) as MODIFIED,
                attach_db(cur, self._orig_assetdb_path) as ORIGINAL,
                conn,
            ):
                cur.execute("BEGIN")
                table_query = (
                    f"SELECT * from {MODIFIED}.sqlite_master WHERE type='table'"
                )
                for table in (nm for tp, nm, *_ in cur.execute(table_query)):
                    # find the insertion point we left off at
                    cur.execute(f"SELECT MAX(id) FROM {ORIGINAL}.{table}")
                    last_id = cur.fetchone()[0]

                    if isinstance(last_id, int):  # if there are already entries
                        # update any changes to existing entries
                        cur.execute(
                            f"INSERT OR REPLACE INTO {table} "
                            f"SELECT * FROM {MODIFIED}.{table} WHERE id <= {last_id} "
                            + (
                                "AND marked_for_deletion = 0"
                                if table == "items"
                                else ""
                            )
                        )
                        # find all the non-id columns
                        cur.execute(f"SELECT * FROM {ORIGINAL}.{table}")
                        columns_no_id = [d[0] for d in cur.description if d[0] != "id"]
                        columns_str = ", ".join(columns_no_id)
                        # insert any new entries, will generate a new ID
                        cur.execute(
                            f"INSERT INTO {table} ({columns_str}) "
                            f"SELECT {columns_str} FROM {MODIFIED}.{table} WHERE id > {last_id} "
                            + (
                                "AND marked_for_deletion = 0"
                                if table == "items"
                                else ""
                            )
                        )
                    else:
                        # insert any new entries
                        cur.execute(
                            f"INSERT INTO {table} "
                            f"SELECT * FROM {MODIFIED}.{table} "
                            + (
                                "WHERE marked_for_deletion = 0"
                                if table == "items"
                                else ""
                            )
                        )

        # clean up
        os.remove(lock_path)
        for f in _TMPDIR.glob("assetGallery.*"):
            f.unlink()
        with suppress(OSError):
            _TMPDIR.rmdir()


@contextmanager
def attach_db(cur: sqlite3.Cursor, path: str):
    name = "".join(c for c in path if c.isalpha())
    cur.execute(f"ATTACH DATABASE '{path}' AS {name}")

    try:
        yield name
    finally:
        cur.execute(f"DETACH DATABASE {name}")


if TYPE_CHECKING:
    import typing


log = logging.getLogger(__name__)


class MayaDCC(DCC):
    """Maya DCC class"""

    shelf_path: str

    def __init__(
        self, is_python_shell: bool = False, extra_args: list[str] | None = None
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        self.shelf_path = str(
            Path(os.getenv("TMPDIR", os.getenv("TEMP", "tmp"))).resolve() / "shelves"
        )

        env_vars: typing.Mapping[str, int | str | None] | None
        env_vars = {
            "DCC": str(this_path.parent.name),
            "DWPICKER_PROJECT_DIRECTORY": str(get_rigging_path() / "Pickers"),
            "MAYA_SHELF_PATH": self.shelf_path,
            "MAYAUSD_EXPORT_MAP1_AS_PRIMARY_UV_SET": 1,
            "MAYAUSD_IMPORT_PRIMARY_UV_SET_AS_MAP1": 1,
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                    str(this_path.parent / "scripts"),
                    str(this_path.parent / "userSetup"),
                    str(this_path.parent / "scripts/studiolibrary/src"),
                    os.environ.get("RMANTREE", "") + "/bin",
                ]
            ),
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "QT_FONT_DPI": os.getenv("MAYA_FONT_DPI") if system == "Linux" else None,
            "QT_PLUGIN_PATH": None,
            # Configure Asset Resolver
            "PXR_AR_DEFAULT_SEARCH_PATH": os.pathsep.join(
                [
                    str(get_production_path()),
                ]
            ),
            # USD Plugins
            "PXR_PLUGINPATH_NAME": os.pathsep.join(
                [
                    str(pipe_path / "lib/usd/kinds"),
                    os.environ.get("PXR_PLUGINPATH_NAME", ""),
                ]
            ),
            "TRACTOR_ENGINE": "tractor-engine.cs.byu.edu:443",
            # Icons
            "XBMLANGPATH": os.pathsep.join(
                [
                    str(pth) + ("/%B" if system == "Linux" else "")
                    for pth in [
                        this_path.parent
                        / "scripts/studiolibrary/src/studiolibrary/resource/icons",
                        pipe_path / "lib/icon",
                        pipe_path / "lib/splash",
                    ]
                ]
            ),
        }

        launch_command = ""
        launch_args: list[str] = []
        if is_python_shell:
            launch_command = str(Executables.mayapy)
            cmd_str = ""
            extra_args_preamble = []

            print(extra_args)

            if extra_args:
                # extract the cmd arg so we can append it to everything else
                try:
                    cmd_flag_index = next(
                        (
                            i
                            for i, f in enumerate(extra_args)
                            if (f[0] == "-") and (f[-1] == "c")
                        )
                    )
                    cmd_str = extra_args[cmd_flag_index + 1]
                    if len(extra_args[cmd_flag_index]) > 2:
                        cmd_str_other_flags = ["-" + extra_args[cmd_flag_index][1:-1]]
                    else:
                        cmd_str_other_flags = []

                    extra_args_preamble = (
                        extra_args[:cmd_flag_index]
                        + extra_args[cmd_flag_index + 2 :]
                        + cmd_str_other_flags
                    )
                except StopIteration:
                    pass

            launch_args = extra_args_preamble + [
                "-ic",
                ";".join(
                    [
                        "import atexit",
                        "import maya.standalone",
                        "maya.standalone.initialize()",
                        "atexit.register(maya.standalone.uninitialize)",
                        cmd_str,
                    ]
                ),
            ]
        else:
            launch_command = str(Executables.maya)
            if extra_args:
                launch_args = extra_args

        super().__init__(
            launch_command, launch_args, env_vars, lambda: self.set_up_shelf_path()
        )

    def set_up_shelf_path(self) -> None:
        prod_dir = str(Path(__file__).parent / "shelves")
        local_dir = self.shelf_path

        shutil.copytree(prod_dir, local_dir, dirs_exist_ok=True)


log = logging.getLogger(__name__)


class NukeDCC(DCC):
    """Nuke DCC class"""

    def __init__(
        self, is_python_shell: bool = False, extra_args: list[str] | None = None
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        env_vars = {
            "NUKE_PATH": str(resolve_mapped_path(this_path.parent / "tools")),
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                    str(
                        get_production_path()
                        / f"../pipeline/pipeline/lib/python/3.9/{sys.platform}"
                    ),
                ]
            ),
            "QT_SCALE_FACTOR": os.getenv("NUKE_SCALE_FACTOR")
            if system == "Linux"
            else None,
        }

        launch_command = ""
        if is_python_shell:
            launch_command = str(Executables.nuke_python)
        else:
            launch_command = str(Executables.nuke)

        if is_python_shell:
            launch_args = extra_args or []
        else:
            launch_args = ["--nukex", *(extra_args or [])]

        super().__init__(launch_command, launch_args, env_vars)


log = logging.getLogger(__name__)


class SubstanceDesignerDCC(DCC):
    """Substance Designer DCC class"""

    def __init__(
        self, is_python_shell: bool = False, extra_args: list[str] | None = None
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        env_vars = {
            "DCC": str(this_path.parent.name),
            "OCIO": str(pipe_path / "lib/ocio/love-v01/config.ocio"),
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                ]
            ),
            "QT_PLUGIN_PATH": "",
        }

        if is_python_shell:
            raise NotImplementedError("Python shell is not supported for this DCC")

        launch_command = str(Executables.substance_designer)
        if not launch_command:
            raise NotImplementedError(
                f"The operating system {system} is not a supported OS for this DCC software"
            )

        launch_args = [
            "--config-file",
            str(this_path.parent / "lnd_configuration.sbscfg"),
            *(extra_args or []),
        ]

        super().__init__(launch_command, launch_args, env_vars)


if TYPE_CHECKING:
    import typing


log = logging.getLogger(__name__)


class SubstancePainterDCC(DCC):
    """Substance Painter DCC class"""

    def __init__(
        self, is_python_shell: bool = False, extra_args: list[str] | None = None
    ) -> None:
        this_path = Path(__file__).resolve()
        pipe_path = this_path.parents[2]

        system = platform.system()

        env_vars: typing.Mapping[str, int | str | None] | None
        env_vars = {
            "DCC": str(this_path.parent.name),
            "OCIO": str(
                resolve_mapped_path(pipe_path / "lib/ocio/love-v01/config.ocio")
            ),
            "PIPE_LOG_LEVEL": log.getEffectiveLevel(),
            "PIPE_PATH": str(pipe_path),
            "PYTHONPATH": os.pathsep.join(
                [
                    str(pipe_path),
                ]
            ),
            "QT_PLUGIN_PATH": "",
            "SUBSTANCE_PAINTER_PLUGINS_PATH": str(this_path.parent / "plugins"),
        }

        if is_python_shell:
            raise NotImplementedError("Python shell is not supported for this DCC")

        launch_command = str(Executables.substance_painter)
        if not launch_command:
            raise NotImplementedError(
                f"The operating system {system} is not a supported OS for this DCC software"
            )

        launch_args: list[str] = extra_args or []

        super().__init__(launch_command, launch_args, env_vars)


TimeUnit = Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]
BasicFilter = Union[
    tuple[
        str,
        Literal[
            "is", "is_not", "less_than", "greater_than", "contains", "not_contains"
        ],
        Any,
    ],
    tuple[str, Literal["starts_with", "ends_with"], str],
    tuple[str, Literal["between", "not_between"], Any, Any],
    tuple[str, Literal["in_last", "in_next"], int, TimeUnit],
    tuple[str, Literal["in"], list[Any]],
    tuple[str, Literal["type_is", "type_is_not"], Optional[str]],
    tuple[
        str, Literal["in_calendar_day", "in_calendar_week", "in_calendar_month"], int
    ],
    tuple[
        str,
        Literal[
            "name_contains", "name_not_contains", "name_starts_with", "name_ends_with"
        ],
        str,
    ],
]


class ComplexFilter(TypedDict):
    filter_operator: Literal["any", "all"]
    filters: list[BasicFilter]


Filter = Union[BasicFilter, ComplexFilter]


class AttrMappingKwargs(TypedDict):
    child_mode: NotRequired[DBInterface.ChildQueryMode]


class T_GetAssetAttrList(Protocol):
    def __call__(
        self,
        attr: str,
        *,
        sorted: bool = False,
        child_mode: DBInterface.ChildQueryMode = DBInterface.ChildQueryMode.LEAVES,
    ) -> list[str]: ...


class T_GetAssetByAttr(Protocol):
    def __call__(self, attr: str, attr_val: str | int) -> Asset: ...


class T_GetAssetById(Protocol):
    def __call__(self, id: int) -> Asset: ...


class T_GetAssetByName(Protocol):
    def __call__(self, name: str) -> Asset: ...


class T_GetAssetByStub(Protocol):
    def __call__(self, stub: AssetStub) -> Asset: ...


class T_GetAssetNameList(Protocol):
    def __call__(
        self,
        child_mode: DBInterface.ChildQueryMode = DBInterface.ChildQueryMode.LEAVES,
        sorted: bool = False,
    ) -> list[str]: ...


class T_GetAssetsByStub(Protocol):
    def __call__(self, stubs: Iterable[AssetStub]) -> list[Asset]: ...


class T_GetAttrList(Protocol):
    def __call__(self, attr: str, *, sorted: bool = False) -> list[str]: ...


class T_GetCodeList(Protocol):
    def __call__(
        self,
        *,
        sorted: bool = False,
        child_mode: DBInterface.ChildQueryMode = DBInterface.ChildQueryMode.LEAVES,
    ) -> list[str]: ...


class T_GetEntityByCode(Protocol):
    def __call__(self, entity_type: type[SGEntity], code: str) -> SGEntity: ...


class T_GetEntityCodeList(Protocol):
    def __call__(
        self,
        entity_type: type[SGEntity],
        *,
        sorted: bool = False,
        **kwargs: Unpack[AttrMappingKwargs],
    ) -> list[str]: ...


class T_GetEnvByAttr(Protocol):
    def __call__(self, attr: str, attr_val: str | int) -> Environment: ...


class T_GetEnvByCode(Protocol):
    def __call__(self, code: str) -> Environment: ...


class T_GetEnvById(Protocol):
    def __call__(self, id: int) -> Environment: ...


class T_GetEnvByStub(Protocol):
    def __call__(self, stub: EnvironmentStub) -> Environment: ...


class T_GetEnvsByStub(Protocol):
    def __call__(self, stubs: Iterable[EnvironmentStub]) -> list[Environment]: ...


class T_GetSeqByAttr(Protocol):
    def __call__(self, attr: str, attr_val: str | int) -> Sequence: ...


class T_GetSeqByCode(Protocol):
    def __call__(self, code: str) -> Sequence: ...


class T_GetSeqById(Protocol):
    def __call__(self, id: int) -> Sequence: ...


class T_GetSeqByStub(Protocol):
    def __call__(self, stub: SequenceStub) -> Sequence: ...


class T_GetSeqsByStub(Protocol):
    def __call__(self, stubs: Iterable[SequenceStub]) -> list[Sequence]: ...


class T_GetShotByAttr(Protocol):
    def __call__(self, attr: str, attr_val: str | int) -> Shot: ...


class T_GetShotByCode(Protocol):
    def __call__(self, code: str) -> Shot: ...


class T_GetShotById(Protocol):
    def __call__(self, id: int) -> Shot: ...


class T_GetShotByStub(Protocol):
    def __call__(self, stub: ShotStub) -> Shot: ...


class T_GetShotsByStub(Protocol):
    def __call__(self, stubs: Iterable[ShotStub]) -> list[Shot]: ...


rig_list = [
    "select rig",
    "Robin",
    "RobinFace",
    "Rayden",
    "RaydenFace",
    "DungeonMonster",
    "Skeleton",
    "Crossbow",
    "Cipher",
    "LootBag",
    "Door",
    "test",
]


class RigPublishUI(QtWidgets.QDialog):
    def __init__(self, parent=get_main_qt_window()):
        super().__init__(parent)

        self.setWindowTitle("Rig Publish")
        self.setMinimumWidth(200)

        self.create_widgets()
        self.create_layouts()
        self.create_connections()

    def create_widgets(self):
        self.rig_options = QtWidgets.QComboBox()
        self.rig_options.addItems(rig_list)

        self.anim_check = QtWidgets.QCheckBox("Update Anim Symlink")
        self.pvis_check = QtWidgets.QCheckBox("Update Previs Symlink")
        self.anim_check.setChecked(False)
        self.pvis_check.setChecked(False)

        self.publish_btn = QtWidgets.QPushButton("Publish")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")

    def create_layouts(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        options_layout = QtWidgets.QFormLayout()
        options_layout.addWidget(self.rig_options)
        options_layout.addWidget(self.anim_check)
        options_layout.addWidget(self.pvis_check)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.publish_btn)
        buttons_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(options_layout)
        main_layout.addLayout(buttons_layout)

    def create_connections(self):
        self.publish_btn.clicked.connect(self.on_publish)
        self.cancel_btn.clicked.connect(self.on_cancel)

    def on_publish(self):
        file_name = self.rig_options.currentText()

        if file_name == "select rig":
            mc.warning("Select a rig to publish.")
            return

        update_anim = self.anim_check.isChecked()
        update_pvis = self.pvis_check.isChecked()

        dir_path = su.get_rigging_path() / "Rigs" / file_name / "RigVersions"

        # search directory for all versions and determine new version number
        ls_dir = dir_path.iterdir()
        latest_version = 0

        for item in ls_dir:
            try:
                version = int(str(item).split(".")[-2])
                if version > latest_version:
                    latest_version = version
            except Exception as e:
                print(f"exception '{e}' for: {item}")

        v_string = str(latest_version + 1).zfill(3)

        # save file to path
        full_name = dir_path / f"{file_name}.{v_string}.mb"
        mc.file(rename=full_name)
        saved = mc.file(s=True, f=True, typ="mayaBinary")

        print(f"File saved to '{saved}'")

        # create symlinks
        if update_anim:
            anim_link_dir_path = su.get_anim_path() / "Rigs"
            temp_name = f"{anim_link_dir_path}\\tmp"
            os.symlink(full_name, temp_name)
            os.rename(temp_name, f"{anim_link_dir_path}/{file_name}.mb")

            print(
                f"Link to file created or updated at '{anim_link_dir_path}/{file_name}.mb'\n"
            )
        if update_pvis:
            pvis_link_dir_path = su.get_previs_path() / "Rigs"
            temp_name = f"{pvis_link_dir_path}\\tmp"
            os.symlink(full_name, temp_name)
            os.rename(temp_name, f"{pvis_link_dir_path}/{file_name}.mb")

            print(
                f"Link to file created or updated at '{pvis_link_dir_path}/{file_name}.mb'\n"
            )
        self.close()

    def on_cancel(self):
        print("Cancelled Rig Publish")
        self.close()


rig_pub: RigPublishUI | None = None


def run():
    global rig_pub
    try:
        assert rig_pub is not None
        rig_pub.close()
        rig_pub.deleteLater()
    except AssertionError:
        pass

    rig_pub = RigPublishUI()
    rig_pub.show()


if __name__ == "__main__":
    try:
        assert rig_pub is not None
        rig_pub.close()
        rig_pub.deleteLater()
    except AssertionError:
        pass

    rig_pub = RigPublishUI()
    rig_pub.show()


class sRGBChecker:
    srgb_channels: list[sp.textureset.Channel]

    def __init__(self) -> None:
        self.srgb_channels = []

    def check(self) -> bool:
        """Return True if sRGB channels are properly configured"""
        for ts in sp.textureset.all_texture_sets():
            try:
                stack = ts.get_stack()
            except ValueError:
                MessageDialog(
                    get_main_qt_window(),
                    "Warning! sRGB Checker could not get stack! You are doing something cool with material layering. Please show this to Scott so he can fix it.",
                ).exec_()
                return False

            for ch in stack.all_channels().values():
                if ch.format() in [
                    sp.textureset.ChannelFormat.sRGB8,
                    sp.textureset.ChannelFormat.RGB8,
                ]:
                    self.srgb_channels.append(ch)

        return not bool(self.srgb_channels)

    def prompt_srgb_fix(self) -> bool:
        """Return True if fix is successful"""
        fix_channels = MessageDialog(
            get_main_qt_window(),
            "Warning! Some of your color channels do not have a high enough bit depth for this color space! (sRGB8, RGB8). Would you like to convert them to RGB16 now?",
            "Color Bit Depth Issue",
            has_cancel_button=True,
        ).exec_()

        if not fix_channels:
            return False

        for ch in self.srgb_channels:
            ch.edit(sp.textureset.ChannelFormat.RGB16)

        MessageDialog(get_main_qt_window(), "Color bit depth has been updated.").exec_()
        return True


# Import nested modules


# mypy: disable-error-code="call-arg,arg-type"


tempList = []

cmds.spaceLocator(n="head_JNT_temp")
cmds.xform(t=(0, 151.177, -4.038))
tempList.append(cmds.ls(selection=True)[0])

cmds.spaceLocator(n="jaw_JNT_temp")
cmds.xform(t=(0, 148.835, -0.835))
tempList.append(cmds.ls(selection=True)[0])

cmds.spaceLocator(n="upperTeeth_JNT_temp")
cmds.xform(t=(0, 149.432, 5.857))
tempList.append(cmds.ls(selection=True)[0])

cmds.spaceLocator(n="lowerTeeth_JNT_temp")
cmds.xform(t=(0, 147.52, 5.738))
tempList.append(cmds.ls(selection=True)[0])

cmds.parent("upperTeeth_JNT_temp", "jaw_JNT_temp")
cmds.parent("lowerTeeth_JNT_temp", "jaw_JNT_temp")
cmds.parent("jaw_JNT_temp", "head_JNT_temp")


AGFunctions.locToJoint("head_JNT_temp")


if cmds.about(nt=True):
    cmds.file(
        "G:\dungeons\character\Rigging\Rigs\RobinFace\Controls\RobinGlobalMouthControls.ma",
        i=True,
    )
if cmds.about(os=True) == "linux64":
    cmds.file(
        "/groups/dungeons/character/Rigging/Rigs/RobinFace/Controls/RobinGlobalMouthControls.ma",
        i=True,
    )


cmds.addAttr("jaw_ctrl", ln="LipInfluence", k=True, dv=1, min=0, max=2, at="double")

cmds.parentConstraint("jaw_ctrl", "jaw_JNT")


upperLipEdges1 = cmds.ls(
    "FaceAtOrigin.e[15857]",
    "FaceAtOrigin.e[15899]",
    "FaceAtOrigin.e[15934]",
    "FaceAtOrigin.e[15863]",
    "FaceAtOrigin.e[15870]",
    "FaceAtOrigin.e[15873]",
    "FaceAtOrigin.e[15957]",
    "FaceAtOrigin.e[15874]",
    "FaceAtOrigin.e[1115]",
    "FaceAtOrigin.e[1204]",
    "FaceAtOrigin.e[1110]",
    "FaceAtOrigin.e[1107]",
    "FaceAtOrigin.e[1099]",
    "FaceAtOrigin.e[1177]",
    "FaceAtOrigin.e[1144]",
    "FaceAtOrigin.e[1098]",
    "FaceAtOrigin.e[1088]",
    "FaceAtOrigin.e[15852]",
)
upperLipEdges2 = cmds.ls(
    "FaceAtOrigin.e[15972]",
    "FaceAtOrigin.e[15865]",
    "FaceAtOrigin.e[15975]",
    "FaceAtOrigin.e[15985]",
    "FaceAtOrigin.e[15897]",
    "FaceAtOrigin.e[15856]",
    "FaceAtOrigin.e[15937]",
    "FaceAtOrigin.e[15955]",
    "FaceAtOrigin.e[15881]",
    "FaceAtOrigin.e[1120]",
    "FaceAtOrigin.e[1201]",
    "FaceAtOrigin.e[1182]",
    "FaceAtOrigin.e[1105]",
    "FaceAtOrigin.e[1218]",
    "FaceAtOrigin.e[1223]",
    "FaceAtOrigin.e[1232]",
    "FaceAtOrigin.e[1140]",
    "FaceAtOrigin.e[1092]",
)
bottomLipEdges1 = cmds.ls(
    "FaceAtOrigin.e[16019]",
    "FaceAtOrigin.e[1239]",
    "FaceAtOrigin.e[1245]",
    "FaceAtOrigin.e[1251]",
    "FaceAtOrigin.e[1261]",
    "FaceAtOrigin.e[1267]",
    "FaceAtOrigin.e[1328]",
    "FaceAtOrigin.e[1353]",
    "FaceAtOrigin.e[1362]",
    "FaceAtOrigin.e[1365]",
    "FaceAtOrigin.e[15990]",
    "FaceAtOrigin.e[15998]",
    "FaceAtOrigin.e[16005]",
    "FaceAtOrigin.e[16011]",
    "FaceAtOrigin.e[16019]",
    "FaceAtOrigin.e[16072]",
    "FaceAtOrigin.e[16098]",
    "FaceAtOrigin.e[16108]",
    "FaceAtOrigin.e[16110]",
)
bottomLipEdges2 = cmds.ls(
    "FaceAtOrigin.e[16021]",
    "FaceAtOrigin.e[1242]",
    "FaceAtOrigin.e[1248]",
    "FaceAtOrigin.e[1255]",
    "FaceAtOrigin.e[1265]",
    "FaceAtOrigin.e[1269]",
    "FaceAtOrigin.e[1332]",
    "FaceAtOrigin.e[1348]",
    "FaceAtOrigin.e[1360]",
    "FaceAtOrigin.e[1367]",
    "FaceAtOrigin.e[15994]",
    "FaceAtOrigin.e[16001]",
    "FaceAtOrigin.e[16009]",
    "FaceAtOrigin.e[16015]",
    "FaceAtOrigin.e[16021]",
    "FaceAtOrigin.e[16077]",
    "FaceAtOrigin.e[16095]",
    "FaceAtOrigin.e[16106]",
    "FaceAtOrigin.e[16113]",
)


AGFunctions.makeCurve(upperLipEdges1, "upperLipCurve1")
AGFunctions.makeCurve(upperLipEdges2, "upperLipCurve2")
AGFunctions.makeCurve(bottomLipEdges1, "bottomLipCurve1")
AGFunctions.makeCurve(bottomLipEdges2, "bottomLipCurve2")


cmds.loft("upperLipCurve1", "upperLipCurve2")
cmds.rename(cmds.ls(selection=True), "upperLipRibbon")

cmds.loft("bottomLipCurve1", "bottomLipCurve2")
cmds.rename(cmds.ls(selection=True), "bottomLipRibbon")
cmds.reverseSurface("bottomLipRibbon")

cmds.select("upperLipRibbon")
mel.eval("createHair 1 19 10 0 0 1 1 5 0 1 1 1;")

cmds.select("bottomLipRibbon")
mel.eval("createHair 1 19 10 0 0 1 1 5 0 1 1 1;")

FollicleGroup1 = cmds.listRelatives("hairSystem1Follicles")
FollicleGroup2 = cmds.listRelatives("hairSystem2Follicles")


AGFunctions.JointFollicleSnapper(FollicleGroup1)
AGFunctions.JointFollicleSnapper(FollicleGroup2)

cmds.delete("hairSystem1", "hairSystem2", "pfxHair1", "pfxHair2", "nucleus1")
cmds.delete(
    "bottomLipRibbonFollicle5044",
    "bottomLipRibbonFollicle5055",
    "bottomLipRibbonFollicle5066",
    "bottomLipRibbonFollicle5033",
    "bottomLipRibbonFollicle5022",
    "bottomLipRibbonFollicle5077",
    "bottomLipRibbonFollicle5099",
    "bottomLipRibbonFollicle5088",
    "bottomLipRibbonFollicle5011",
    "bottomLipRibbonFollicle5000",
)
cmds.delete(
    "upperLipRibbonFollicle5044",
    "upperLipRibbonFollicle5055",
    "upperLipRibbonFollicle5066",
    "upperLipRibbonFollicle5033",
    "upperLipRibbonFollicle5022",
    "upperLipRibbonFollicle5077",
    "upperLipRibbonFollicle5099",
    "upperLipRibbonFollicle5088",
    "upperLipRibbonFollicle5011",
    "upperLipRibbonFollicle5000",
)

jointNaming = AGFunctions.searchFor("hairSystem1Follicles", "joint")

cmds.rename(jointNaming[0], "R_Upper_Minor_Mouth_04_jnt")
cmds.rename(jointNaming[1], "R_Upper_Minor_Mouth_03_jnt")
cmds.rename(jointNaming[2], "R_Upper_Minor_Mouth_02_jnt")
cmds.rename(jointNaming[3], "R_Upper_Minor_Mouth_01_jnt")
cmds.rename(jointNaming[4], "M_Upper_Minor_Mouth_jnt")
cmds.rename(jointNaming[5], "L_Upper_Minor_Mouth_01_jnt")
cmds.rename(jointNaming[6], "L_Upper_Minor_Mouth_02_jnt")
cmds.rename(jointNaming[7], "L_Upper_Minor_Mouth_03_jnt")
cmds.rename(jointNaming[8], "L_Upper_Minor_Mouth_04_jnt")

jointNaming = AGFunctions.searchFor("hairSystem2Follicles", "joint")

cmds.rename(jointNaming[0], "R_Lower_Minor_Mouth_04_jnt")
cmds.rename(jointNaming[1], "R_Lower_Minor_Mouth_03_jnt")
cmds.rename(jointNaming[2], "R_Lower_Minor_Mouth_02_jnt")
cmds.rename(jointNaming[3], "R_Lower_Minor_Mouth_01_jnt")
cmds.rename(jointNaming[4], "M_Lower_Minor_Mouth_jnt")
cmds.rename(jointNaming[5], "L_Lower_Minor_Mouth_01_jnt")
cmds.rename(jointNaming[6], "L_Lower_Minor_Mouth_02_jnt")
cmds.rename(jointNaming[7], "L_Lower_Minor_Mouth_03_jnt")
cmds.rename(jointNaming[8], "L_Lower_Minor_Mouth_04_jnt")


mainJointLoc = [
    "M_Upper_Minor_Mouth_jnt",
    "M_Lower_Minor_Mouth_jnt",
    "R_Lower_Minor_Mouth_02_jnt",
    "L_Lower_Minor_Mouth_02_jnt",
    "L_Upper_Minor_Mouth_02_jnt",
    "R_Upper_Minor_Mouth_02_jnt",
    "FaceAtOrigin.vtx[7840]",
    "FaceAtOrigin.vtx[643]",
]

jointNaming = AGFunctions.snapJointTo(mainJointLoc, 1)

controlGroup = []

controlGroup.append(cmds.rename(jointNaming[0], "M_Upper_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[1], "M_Lower_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[2], "R_Lower_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[3], "L_Lower_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[4], "L_Upper_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[5], "R_Upper_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[6], "L_Corner_Main_Mouth_jnt"))
controlGroup.append(cmds.rename(jointNaming[7], "R_Corner_Main_Mouth_jnt"))


for each in controlGroup:
    getPos = cmds.xform(each, query=True, ws=True, rp=True)

    nameBase = each[: len(each) - 4]

    Circle = cmds.circle(nr=(0, 0, 1), c=(getPos[0], getPos[1], getPos[2]), r=0.5)  # type: ignore[index]
    cmds.rename(nameBase + "_ctrl")

    # center pivot
    cmds.CenterPivot()  # type: ignore[attr-defined]

    # make offset and driver group
    cmds.group(n=nameBase + "_offset2")
    cmds.group(n=nameBase + "_offset")
    cmds.CenterPivot()  # type: ignore[attr-defined]
    cmds.group(n=nameBase + "_ctrl_driver")

    getPivot = cmds.xform("jaw_JNT", query=True, ws=True, rp=True)
    cmds.move(
        getPivot[0],  # type: ignore[index]
        getPivot[1],  # type: ignore[index]
        getPivot[2],  # type: ignore[index]
        nameBase + "_ctrl_driver.scalePivot",
        nameBase + "_ctrl_driver.rotatePivot",
        ws=True,
    )

    cmds.parentConstraint(each[: len(each) - 4] + "_ctrl", each)

AGFunctions.jawControllerLinker(["M_Lower_Main_Mouth_ctrl"])
AGFunctions.jawControllerLinker(["L_Lower_Main_Mouth_ctrl", "R_Lower_Main_Mouth_ctrl"])
AGFunctions.jawControllerLinker(
    ["L_Corner_Main_Mouth_ctrl", "R_Corner_Main_Mouth_ctrl"]
)
AGFunctions.jawControllerLinker(["L_Upper_Main_Mouth_ctrl", "R_Upper_Main_Mouth_ctrl"])
AGFunctions.jawControllerLinker(["M_Upper_Main_Mouth_ctrl"])


cmds.setAttr("L_Lower_Main_Mouth_ctrl_remap.outputMax", 0.85)
cmds.setAttr("L_Corner_Main_Mouth_ctrl_remap.outputMax", 0.5)
cmds.setAttr("L_Upper_Main_Mouth_ctrl_remap.outputMax", 0.15)
cmds.setAttr("M_Upper_Main_Mouth_ctrl_remap.outputMax", 0)


cmds.group(
    "M_Upper_Main_Mouth_ctrl_driver",
    "M_Lower_Main_Mouth_ctrl_driver",
    "R_Lower_Main_Mouth_ctrl_driver",
    "L_Lower_Main_Mouth_ctrl_driver",
    "L_Upper_Main_Mouth_ctrl_driver",
    "R_Upper_Main_Mouth_ctrl_driver",
    "L_Corner_Main_Mouth_ctrl_driver",
    "R_Corner_Main_Mouth_ctrl_driver",
    n="MainMouthControlsGroup",
)
cmds.parent("MainMouthControlsGroup", "Mouth_Global_ctrl")


cmds.delete("upperLipRibbon", constructionHistory=True)
cmds.delete("bottomLipRibbon", constructionHistory=True)

cmds.xform("L_Corner_Main_Mouth_offset", ro=(17.168, 48.089, 3.472))
cmds.xform("R_Corner_Main_Mouth_offset", ro=(17.168, -48.089, -3.472))
cmds.xform("L_Upper_Main_Mouth_offset", ro=(0, 35, 0))
cmds.xform("L_Lower_Main_Mouth_offset", ro=(0, 35, 0))
cmds.xform("R_Upper_Main_Mouth_offset", ro=(0, -35, 0))
cmds.xform("R_Lower_Main_Mouth_offset", ro=(0, -35, 0))


cmds.skinCluster(
    "upperLipRibbon",
    "M_Upper_Main_Mouth_jnt",
    "L_Upper_Main_Mouth_jnt",
    "R_Upper_Main_Mouth_jnt",
    "L_Corner_Main_Mouth_jnt",
    "R_Corner_Main_Mouth_jnt",
)
cmds.skinCluster(
    "bottomLipRibbon",
    "M_Lower_Main_Mouth_jnt",
    "L_Lower_Main_Mouth_jnt",
    "R_Lower_Main_Mouth_jnt",
    "L_Corner_Main_Mouth_jnt",
    "R_Corner_Main_Mouth_jnt",
)

#####                         #####
##### Corrections and Updates #####
#####                         #####

cmds.delete("upperLipRibbonFollicle5094")
cmds.delete("upperLipRibbonFollicle5006")

cmds.parent("nurbsCircle37", world=True)
cmds.parent("nurbsCircle21", world=True)

cmds.xform("nurbsCircle37", ws=True, t=(0, 0, 0))
cmds.xform("nurbsCircle21", ws=True, t=(0, 0, 0))

emptyGroup = cmds.group(empty=True)
cmds.parent("nurbsCircle21", "null1")
AGFunctions.snapTo("null1", "R_Corner_Main_Mouth_jnt")

emptyGroup = cmds.group(empty=True)
cmds.parent("nurbsCircle37", "null2")
AGFunctions.snapTo("null2", "L_Corner_Main_Mouth_jnt")


cmds.parentConstraint(
    "bottomLipRibbonFollicle5017",
    AGFunctions.offsetGroupMaker("nurbsCircle23"),
    mo=True,
)
cmds.parentConstraint(
    "bottomLipRibbonFollicle5028",
    AGFunctions.offsetGroupMaker("nurbsCircle25"),
    mo=True,
)
cmds.parentConstraint(
    "bottomLipRibbonFollicle5039",
    AGFunctions.offsetGroupMaker("nurbsCircle27"),
    mo=True,
)
cmds.parentConstraint(
    "bottomLipRibbonFollicle5050",
    AGFunctions.offsetGroupMaker("nurbsCircle29"),
    mo=True,
)
cmds.parentConstraint(
    "bottomLipRibbonFollicle5061",
    AGFunctions.offsetGroupMaker("nurbsCircle31"),
    mo=True,
)
cmds.parentConstraint(
    "bottomLipRibbonFollicle5072",
    AGFunctions.offsetGroupMaker("nurbsCircle33"),
    mo=True,
)
cmds.parentConstraint(
    "bottomLipRibbonFollicle5083",
    AGFunctions.offsetGroupMaker("nurbsCircle35"),
    mo=True,
)

cmds.parentConstraint(
    "upperLipRibbonFollicle5017", AGFunctions.offsetGroupMaker("nurbsCircle4"), mo=True
)
cmds.parentConstraint(
    "upperLipRibbonFollicle5028", AGFunctions.offsetGroupMaker("nurbsCircle6"), mo=True
)
cmds.parentConstraint(
    "upperLipRibbonFollicle5039", AGFunctions.offsetGroupMaker("nurbsCircle8"), mo=True
)
cmds.parentConstraint(
    "upperLipRibbonFollicle5050", AGFunctions.offsetGroupMaker("nurbsCircle10"), mo=True
)
cmds.parentConstraint(
    "upperLipRibbonFollicle5061", AGFunctions.offsetGroupMaker("nurbsCircle12"), mo=True
)
cmds.parentConstraint(
    "upperLipRibbonFollicle5072", AGFunctions.offsetGroupMaker("nurbsCircle14"), mo=True
)
cmds.parentConstraint(
    "upperLipRibbonFollicle5083", AGFunctions.offsetGroupMaker("nurbsCircle16"), mo=True
)


cmds.rename("nurbsCircle29", "M_Lower_Minor_Mouth_ctrl")
cmds.rename("nurbsCircle31", "L_Lower_Minor_Mouth_01_ctrl")
cmds.rename("nurbsCircle33", "L_Lower_Minor_Mouth_02_ctrl")
cmds.rename("nurbsCircle35", "L_Lower_Minor_Mouth_03_ctrl")
cmds.rename("nurbsCircle37", "L_Corner_Minor_Mouth_ctrl")
cmds.rename("nurbsCircle27", "R_Lower_Minor_Mouth_01_ctrl")
cmds.rename("nurbsCircle25", "R_Lower_Minor_Mouth_02_ctrl")
cmds.rename("nurbsCircle23", "R_Lower_Minor_Mouth_03_ctrl")
cmds.rename("nurbsCircle21", "R_Corner_Minor_Mouth_ctrl")
cmds.rename("nurbsCircle8", "R_Upper_Minor_Mouth_01_ctrl")
cmds.rename("nurbsCircle6", "R_Upper_Minor_Mouth_02_ctrl")
cmds.rename("nurbsCircle4", "R_Upper_Minor_Mouth_03_ctrl")
cmds.rename("nurbsCircle10", "M_Upper_Minor_Mouth_ctrl")
cmds.rename("nurbsCircle12", "L_Upper_Minor_Mouth_01_ctrl")
cmds.rename("nurbsCircle14", "L_Upper_Minor_Mouth_02_ctrl")
cmds.rename("nurbsCircle16", "L_Upper_Minor_Mouth_03_ctrl")

cmds.rename("null1", "M_Lower_Minor_Mouth_offset")
cmds.rename("null2", "L_Lower_Minor_Mouth_01_offset")
cmds.rename("null3", "L_Lower_Minor_Mouth_02_offset")
cmds.rename("null4", "L_Lower_Minor_Mouth_03_offset")
cmds.rename("null5", "L_Corner_Minor_Mouth_offset")
cmds.rename("null6", "R_Lower_Minor_Mouth_01_offset")
cmds.rename("null7", "R_Lower_Minor_Mouth_02_offset")
cmds.rename("null8", "R_Lower_Minor_Mouth_03_offset")
cmds.rename("null9", "R_Corner_Minor_Mouth_offset")
cmds.rename("null10", "R_Upper_Minor_Mouth_01_offset")
cmds.rename("null11", "R_Upper_Minor_Mouth_02_offset")
cmds.rename("null12", "R_Upper_Minor_Mouth_03_offset")
cmds.rename("null13", "M_Upper_Minor_Mouth_offset")
cmds.rename("null14", "L_Upper_Minor_Mouth_01_offset")
cmds.rename("null15", "L_Upper_Minor_Mouth_02_offset")
cmds.rename("null16", "L_Upper_Minor_Mouth_03_offset")


cmds.group(
    "M_Lower_Minor_Mouth_offset",
    "L_Lower_Minor_Mouth_01_offset",
    "L_Lower_Minor_Mouth_02_offset",
    "L_Lower_Minor_Mouth_03_offset",
    "L_Corner_Minor_Mouth_offset",
    "R_Lower_Minor_Mouth_01_offset",
    "R_Lower_Minor_Mouth_02_offset",
    "R_Lower_Minor_Mouth_03_offset",
    "R_Corner_Minor_Mouth_offset",
    "R_Upper_Minor_Mouth_01_offset",
    "R_Upper_Minor_Mouth_02_offset",
    "R_Upper_Minor_Mouth_03_offset",
    "M_Upper_Minor_Mouth_offset",
    "L_Upper_Minor_Mouth_01_offset",
    "L_Upper_Minor_Mouth_02_offset",
    "L_Upper_Minor_Mouth_03_offset",
    n="MinorMouthControlsGroup",
)

cmds.parent("MinorMouthControlsGroup", "Mouth_Global_offset")
cmds.parent("jaw_offset", "Mouth_Global_offset")
cmds.parent("hairSystem1Follicles", "Mouth_Global_offset")
cmds.parent("hairSystem2Follicles", "Mouth_Global_offset")


# cmds.shadingNode("multiplyDivide", au=1, n="L_CornerLiptoUpper" + "_multi")


__all__ = [
    "db",
    "glui",
    "struct",
    "texconverter",
    "util",
]

# import DCC-specific modules

_dcc = _getenv("DCC", "")

if _dcc == "houdini":
    from . import h

    __all__ += ["h"]

elif _dcc == "maya":
    from . import m

    __all__ += ["m"]

elif _dcc == "substance_painter":
    from . import sp

    __all__ += ["sp"]

# configure logging
_log = _l.getLogger(__name__)
_l.basicConfig(
    level=int(_e.get("PIPE_LOG_LEVEL") or 0),
    format="%(asctime)s %(processName)s(%(process)s) %(threadName)s [%(name)s(%(lineno)s)] [%(levelname)s] %(message)s",
)


__all__ = [
    "Config",
    "DB",
    "DBInterface",
]


if TYPE_CHECKING:
    import typing
    from typing import Any, Callable, Iterable

    from typing_extensions import Unpack

    from .typing import *  # noqa: F403
    from .typing import AttrMappingKwargs, Filter


log = logging.getLogger(__name__)


@dataclass(eq=True, frozen=True)
class SG_Config:
    project_id: int
    # DO NOT SHARE/COMMIT THE sg_key!!! IT'S EQUIVALENT TO AN ADMIN PW!!!
    sg_key: str
    sg_script: str
    sg_server: str


class SGaaDB(DBInterface):
    """ShotGrid as a Database"""

    _sg: shotgun_api3.Shotgun
    _id: int
    _sg_entity_lists: dict[str, list[dict]]
    _update_notifier: threading.Condition
    _update_thread: threading.Thread

    _conn_instances: dict[tuple[SG_Config, bool], SGaaDB] = {}

    @classmethod
    def Get(cls, config: SG_Config, *, auto_update: bool = True) -> SGaaDB:
        key = (config, auto_update)
        if key in cls._conn_instances:
            cls._conn_instances[key]._update_sg_entity_lists()
            return cls._conn_instances[key]
        else:
            log.debug("Creating new DB instance.")
            cls._conn_instances[key] = cls(config, auto_update=auto_update)
            return cls._conn_instances[key]

    def __init__(self, config: SG_Config, *, auto_update: bool = True) -> None:
        self._sg = shotgun_api3.Shotgun(
            config.sg_server, config.sg_script, config.sg_key
        )
        self._id = config.project_id

        self._update_notifier = threading.Condition()

        self._sg_entity_lists = {}
        self._load_sg_asset_list()
        self._load_sg_env_list()
        self._load_sg_sequence_list()
        self._load_sg_shot_list()

        if auto_update:
            self._update_thread = threading.Thread(
                target=self._threaded_updater, daemon=True
            )
            self._update_thread.start()

    def _update_sg_entity_lists(self) -> None:
        self._load_sg_asset_list()
        self._load_sg_shot_list()
        self._load_sg_sequence_list()
        self._load_sg_env_list()

    def _threaded_updater(self) -> None:
        while True:
            with self._update_notifier:
                # wait until the cache is manually expired or timeout (5 min) reached
                try:
                    self._update_notifier.wait(timeout=300)
                except TimeoutError:
                    pass

                log.debug("Cache expired, refreshing list")
                self._update_sg_entity_lists()

    def _load_sg_asset_list(self) -> None:
        """Load the list of assets from SG to local cache"""
        query = _AssetListQuery(self._id)
        self._sg_entity_lists[Asset.__name__] = query.exec(self._sg)

    def _load_sg_env_list(self) -> None:
        """Load the list of environments from SG to local cache"""
        query = _EnvironmentListQuery(self._id)
        self._sg_entity_lists[Environment.__name__] = query.exec(self._sg)

    def _load_sg_sequence_list(self) -> None:
        """Load the list of sequences from SG to local cache"""
        query = _SequenceListQuery(self._id)
        self._sg_entity_lists[Sequence.__name__] = query.exec(self._sg)

    def _load_sg_shot_list(self) -> None:
        """Load the list of shots from SG to local cache"""
        query = _ShotListQuery(self._id)
        self._sg_entity_lists[Shot.__name__] = query.exec(self._sg)

    def expire_cache(self) -> None:
        with self._update_notifier:
            self._update_notifier.notify()

    def get_entity_by_attr(
        self, entity_type: type[SGEntity], attr: str, attr_val: str | int
    ) -> SGEntity:
        internal_attr = entity_type.map_sg_field_names(attr)
        return entity_type.from_sg(
            next(
                e
                for e in self._sg_entity_lists[entity_type.__name__]
                if e[internal_attr] == attr_val
            )
        )

    def _get_entity_by_attr_swap(
        self, attr: str, entity_type: type[SGEntity], attr_val: str | int
    ) -> SGEntity:
        return self.get_entity_by_attr(entity_type, attr, attr_val)

    def get_entity_by_stub(
        self, entity_type: type[SGEntity], stub: SGEntityStub
    ) -> SGEntity:
        return self.get_entity_by_attr(entity_type, "id", stub.id)

    def get_entities_by_stub(
        self, entity_type: type[SGEntity], stubs: Iterable[SGEntityStub]
    ) -> list[SGEntity]:
        ids = [s.id for s in stubs]
        return [
            entity_type.from_sg(e)
            for e in self._sg_entity_lists[entity_type.__name__]
            if e["id"] in ids
        ]

    @staticmethod
    def _default_entity_attr_mapper(
        entity_list: list[dict], attr: str, **kwargs
    ) -> list[str]:
        return [e[attr] for e in entity_list]

    @staticmethod
    def _asset_attr_mapper(
        asset_list: list[dict],
        attr: str,
        child_mode: DBInterface.ChildQueryMode = DBInterface.ChildQueryMode.LEAVES,
    ) -> list[str]:
        if child_mode == DBInterface.ChildQueryMode.ALL:
            arr = [a[attr] for a in asset_list]
        elif child_mode == DBInterface.ChildQueryMode.CHILDREN:
            arr = [a[attr] for a in asset_list if a["parents"]]
        elif child_mode == DBInterface.ChildQueryMode.ROOTS:
            arr = [a[attr] for a in asset_list if not a["parents"]]
        elif child_mode == DBInterface.ChildQueryMode.PARENTS:
            arr = [a[attr] for a in asset_list if a["assets"]]
        elif child_mode == DBInterface.ChildQueryMode.LEAVES:
            arr = [a[attr] for a in asset_list if not a["assets"]]
        else:
            raise IndexError("Not a valid ChildQueryMode", child_mode)

        return arr

    _entity_attr_custom_mappers: dict[
        str, Callable[[list[dict], str, Unpack[AttrMappingKwargs]], list[str]]
    ] = {
        Asset.__name__: _asset_attr_mapper.__func__,  # type: ignore[attr-defined]
    }

    def get_entity_attr_list(
        self,
        entity_type: type[SGEntity],
        attr: str,
        *,
        sorted: bool = False,
        **kwargs,
    ) -> list[str]:
        mapper = self._entity_attr_custom_mappers.get(
            entity_type.__name__, self._default_entity_attr_mapper
        )
        internal_attr = entity_type.map_sg_field_names(attr)
        entity_list = self._sg_entity_lists[entity_type.__name__]
        arr = mapper(entity_list, internal_attr, **kwargs)
        if sorted:
            arr.sort()
        return arr

    def _get_entity_attr_list_swap(
        self,
        attr: str,
        entity_type: type[SGEntity],
        **kwargs,
    ) -> list[str]:
        return self.get_entity_attr_list(entity_type, attr, **kwargs)

    get_entity_code_list: T_GetEntityCodeList = pm(_get_entity_attr_list_swap, "code")  # type: ignore[assignment] # noqa: F405
    get_entity_by_code: T_GetEntityByCode = pm(_get_entity_by_attr_swap, "code")  # type: ignore[assignment] # noqa: F405

    get_asset_attr_list: T_GetAssetAttrList = pm(get_entity_attr_list, Asset)  # type: ignore[assignment] # noqa: F405
    get_asset_by_attr: T_GetAssetByAttr = pm(get_entity_by_attr, Asset)  # type: ignore[assignment] # noqa: F405
    get_asset_by_name: T_GetAssetByName = pm(get_asset_by_attr, "code")  # type: ignore[assignment] # noqa: F405
    get_asset_by_id: T_GetAssetById = pm(get_asset_by_attr, "id")  # type: ignore[assignment] # noqa: F405
    get_asset_by_stub: T_GetAssetByStub = pm(get_entity_by_stub, Asset)  # type: ignore[assignment] # noqa: F405
    get_asset_name_list: T_GetCodeList = pm(get_asset_attr_list, "code")  # type: ignore[assignment] # noqa: F405
    get_assets_by_stub: T_GetAssetsByStub = pm(get_entities_by_stub, Asset)  # type: ignore[assignment] # noqa: F405

    def get_assets_by_name(self, names: Iterable[str]) -> list[Asset]:
        return [
            Asset.from_sg(i)
            for i in set(
                [
                    a
                    for a in self._sg_entity_lists[Asset.__name__]
                    if a["code"] in list(names)
                ]
            )
        ]

    def update_asset(self, asset: Asset) -> bool:
        try:
            assert asset.id
            self._sg.update("Asset", asset.id, asset.sg_diff())
        except Exception as e:
            log.error(e)
            return False
        finally:
            self.expire_cache()
        return True

    get_env_attr_list: T_GetAttrList = pm(get_entity_attr_list, Environment)  # type: ignore[assignment] # noqa: F405
    get_env_by_attr: T_GetEnvByAttr = pm(get_entity_by_attr, Environment)  # type: ignore[assignment] # noqa: F405
    get_env_by_code: T_GetEnvByCode = pm(get_env_by_attr, "code")  # type: ignore[assignment] # noqa: F405
    get_env_by_id: T_GetEnvById = pm(get_env_by_attr, "id")  # type: ignore[assignment] # noqa: F405
    get_env_by_stub: T_GetEnvByStub = pm(get_entity_by_stub, Environment)  # type: ignore[assignment] # noqa: F405
    get_env_code_list: T_GetCodeList = pm(get_env_attr_list, "code")  # type: ignore[assignment] # noqa: F405
    get_envs_by_stub: T_GetEnvsByStub = pm(get_entities_by_stub, Environment)  # type: ignore[assignment] # noqa: F405

    get_sequence_attr_list: T_GetAttrList = pm(get_entity_attr_list, Sequence)  # type: ignore[assignment] # noqa: F405
    get_sequence_by_attr: T_GetSeqByAttr = pm(get_entity_by_attr, Sequence)  # type: ignore[assignment] # noqa: F405
    get_sequence_by_code: T_GetSeqByCode = pm(get_sequence_by_attr, "code")  # type: ignore[assignment] # noqa: F405
    get_sequence_by_id: T_GetSeqById = pm(get_sequence_by_attr, "id")  # type: ignore[assignment] # noqa: F405
    get_sequence_by_stub: T_GetSeqByStub = pm(get_entity_by_stub, Sequence)  # type: ignore[assignment] # noqa: F405
    get_sequence_code_list: T_GetCodeList = pm(get_sequence_attr_list, "code")  # type: ignore[assignment] # noqa: F405
    get_sequences_by_stub: T_GetSeqsByStub = pm(get_entities_by_stub, Sequence)  # type: ignore[assignment] # noqa: F405

    get_shot_attr_list: T_GetAttrList = pm(get_entity_attr_list, Shot)  # type: ignore[assignment] # noqa: F405
    get_shot_by_attr: T_GetShotByAttr = pm(get_entity_by_attr, Shot)  # type: ignore[assignment] # noqa: F405
    get_shot_by_code: T_GetShotByCode = pm(get_shot_by_attr, "code")  # type: ignore[assignment] # noqa: F405
    get_shot_by_id: T_GetShotById = pm(get_shot_by_attr, "id")  # type: ignore[assignment] # noqa: F405
    get_shot_by_stub: T_GetShotByStub = pm(get_entity_by_stub, Shot)  # type: ignore[assignment] # noqa: F405
    get_shot_code_list: T_GetCodeList = pm(get_shot_attr_list, "code")  # type: ignore[assignment] # noqa: F405
    get_shots_by_stub: T_GetShotsByStub = pm(get_entities_by_stub, Shot)  # type: ignore[assignment] # noqa: F405


class _Query(ABC):
    """Helper class for making queries to a SG connection instance"""

    project_id: int
    fields: list[str]
    filters: list[Filter]

    def __init__(
        self,
        project_id: int,
        *,
        extra_fields: typing.Sequence[str] | None = None,
        override_default_fields: bool = False,
    ) -> None:
        if extra_fields is None:
            extra_fields = []
        self.project_id = project_id
        self.fields = self._construct_fields(extra_fields, override_default_fields)
        self.filters = self._construct_filters()

    def _construct_fields(
        self, extra_fields: typing.Sequence[str], override_default_fields: bool
    ) -> list[str]:
        """Construct the fields needed for the ShotGrid query"""
        if override_default_fields:
            return list(extra_fields)
        else:
            return list(set(self._base_fields + list(extra_fields)))

    def _construct_filters(self) -> list[Filter]:
        """Construct the list of filters needed for the ShotGrid query"""
        base_filters = self._base_filters
        base_filters.insert(
            0, ("project", "is", {"type": "Project", "id": self.project_id})
        )
        return base_filters

    def insert_field(self, field: str) -> None:
        self.fields.append(field)

    def insert_filter(self, filter: Filter) -> None:
        self.filters.append(filter)

    @abstractmethod
    def exec(self, sg: shotgun_api3.Shotgun) -> Any:
        pass

    @property
    @abstractmethod
    def _base_fields(self) -> list[str]:
        pass

    @property
    @abstractmethod
    def _base_filters(self) -> list[Filter]:
        pass


class _AssetListQuery(_Query):
    """Helper class for making queries about assets to a SG connection instance"""

    _untracked_asset_types = [
        "Environment",
        "FX",
        "Graphic",
        "Matte Painting",
        "Vehicle",
        "Tool",
        "Font",
    ]

    # Override
    def exec(self, sg: shotgun_api3.Shotgun) -> list[dict]:
        return sg.find("Asset", self.filters, self.fields)

    # Override
    @property
    def _base_fields(self) -> list[str]:
        return [
            "code",  # display name
            "sg_pipe_name",  # internal name
            "sg_path",  # asset path
            "id",  # asset id
            "parents",  # parent assets
            "assets",  # child assets
            "tags",  # asset tags
            "shots",  # shots asset present in
            "sg_material_variants",  # material variants
        ]

    # Override
    @property
    def _base_filters(self) -> list[Filter]:
        filters: list[Filter] = [
            ("sg_status_list", "is_not", "oop"),
            {
                "filter_operator": "all",
                "filters": [
                    ("sg_asset_type", "is_not", t) for t in self._untracked_asset_types
                ],
            },
        ]

        return filters


class _EnvironmentListQuery(_Query):
    # Override
    def exec(self, sg: shotgun_api3.Shotgun) -> list[dict]:
        return sg.find("Asset", self.filters, self.fields)

    # Override
    @property
    def _base_fields(self) -> list[str]:
        return [
            "code",  # display name
            "sg_pipe_name",  # internal name
            "sg_path",  # environment path
            "id",  # asset id
            "shots",  # shots environment present in
        ]

    # Override
    @property
    def _base_filters(self) -> list[Filter]:
        filters: list[Filter] = [
            ("sg_status_list", "is_not", "oop"),
            ("sg_asset_type", "is", "Environment"),
        ]

        return filters


class _ShotListQuery(_Query):
    """Helper class for making queries about shots to a SG connection instance"""

    # Override
    def exec(self, sg: shotgun_api3.Shotgun) -> list[dict]:
        return sg.find("Shot", self.filters, self.fields)

    # Override
    @property
    def _base_fields(self) -> list[str]:
        return [
            "assets",
            "code",
            "id",
            "sg_cut_in",
            "sg_cut_out",
            "sg_cut_duration",
            "sg_path",
            "sg_sequence",
            "sg_set",
            "sg_substeps",
        ]

    # Override
    @property
    def _base_filters(self) -> list[Filter]:
        filters: list[Filter] = [("sg_status_list", "is_not", "oop")]

        return filters


class _SequenceListQuery(_Query):
    """Helper class for making queries about sequences to a SG connection instance"""

    # Override
    def exec(self, sg: shotgun_api3.Shotgun) -> list[dict]:
        return sg.find("Sequence", self.filters, self.fields)

    # Override
    @property
    def _base_fields(self) -> list[str]:
        return [
            "code",
            "id",
            "sg_path",
            "sg_set",
            "shots",
        ]

    # Override
    @property
    def _base_filters(self) -> list[Filter]:
        filters: list[Filter] = [("sg_status_list", "is_not", "oop")]

        return filters


class PostProcessor(metaclass=ABCMeta):
    _conn: DB

    def __init__(self):
        self._conn = DB(DB_Config)

    @abstractmethod
    def run(self, shot_code: str) -> None:
        pass


class AnimPostProcessor(PostProcessor):
    def run(self, shot_code: str) -> None:
        # Set up
        shot = self._conn.get_shot_by_code(shot_code)
        hou.playbar.setFrameRange(shot.cut_in - 5, shot.cut_out + 5)
        hou.playbar.setPlaybackRange(shot.cut_in - 5, shot.cut_out + 5)

        stage_ctx: hou.Node = hou.node("/stage")  # type: ignore[assignment]

        load_layer = stage_ctx.createNode("sdm223::main::LnD_Load_Layers::1.0")
        load_layer.parm("shot").set(f"$JOB/{shot.path}")  # type: ignore[union-attr]

        for dep in ["cfx", "fx", "flo", "lighting"]:
            load_layer.parm(f"{dep}_enable").set(0)  # type: ignore[union-attr]

        if env_stub := (shot.set or self._conn.get_sequence_by_stub(shot.sequence).set):  # type: ignore[arg-type]
            layout = self._conn.get_env_by_stub(env_stub)
            load_layer.parm("layout_path").set(f"$JOB/{layout.path}/main.usd")  # type: ignore[union-attr]

        layer_break = stage_ctx.createNode("layerbreak")

        postprocess = stage_ctx.createNode("sdm222::lnd_anim_postprocess::1.0")

        publish = stage_ctx.createNode("usd_rop")

        publish.parm("trange").set("normal")  # type: ignore[union-attr]
        publish.parm("lopoutput").set(f"$JOB/{shot.path}/anim/usd/post-process.usd")  # type: ignore[union-attr]
        publish.parm("savestyle").set("flattenalllayers")  # type: ignore[union-attr]

        layer_break.setInput(0, load_layer)
        postprocess.setInput(0, layer_break)
        publish.setInput(0, postprocess)

        publish.parm("execute").pressButton()  # type: ignore[union-attr]


class CfxPostProcessor(PostProcessor):
    def run(self, shot_code: str) -> None:
        HShotFileManager(
            override_dept="cfx",
            override_entity_code=shot_code,
            ignore_load_warnings=True,
        ).open_file()

        publish = hou.node("/stage/PUBLISH")
        publish.parm("execute").pressButton()  # type: ignore[union-attr]


log = logging.getLogger(__name__)


class HAssetFileManager(HFileManager):
    def __init__(self, ignore_load_warnings: bool = False) -> None:
        super().__init__(Asset, ignore_load_warnings=ignore_load_warnings)

    def _generate_filename_ext(self, entity) -> tuple[str, str]:
        asset = cast(Asset, entity)
        return asset.name, "hipnc"

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        super(HAssetFileManager, HAssetFileManager)._setup_file(self, path, entity)

        hip_path = Path(hou.hscriptStringExpression("$HIP"))
        hou.setContextOption("ASSET", hip_path.name)


log = logging.getLogger(__name__)


class HEnvFileManager(HFileManager):
    def __init__(self, ignore_load_warnings: bool = False) -> None:
        super().__init__(Environment, ignore_load_warnings=ignore_load_warnings)

    def _generate_filename_ext(self, entity) -> tuple[str, str]:
        env = cast(Environment, entity)
        return env.name, "hipnc"

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        super(HEnvFileManager, HEnvFileManager)._setup_file(self, path, entity)

        hip_path = Path(hou.hscriptStringExpression("$HIP"))
        hou.setContextOption("ENVIRON", hip_path.name)


log = logging.getLogger(__name__)


class HFileManager(FileManager):
    _ignore_load_warnings: bool

    def __init__(
        self,
        entity_type: type[SGEntity],
        versioning: bool = False,
        version_glob: str = "",
        override_entity_code: str | None = None,
        ignore_load_warnings: bool = False,
    ) -> None:
        conn = DB.Get(DB_Config, auto_update=False)
        window = get_main_qt_window()
        self._ignore_load_warnings = ignore_load_warnings
        super().__init__(
            conn,
            entity_type,
            window,
            versioning=versioning,
            version_glob=version_glob,
            override_entity_code=override_entity_code,
        )

    def _check_unsaved_changes(self) -> bool:
        if self._override_entity_code:
            return True

        if hou.hipFile.hasUnsavedChanges():
            warning_response = hou.ui.displayMessage(
                "The current file has not been saved. Continue anyways?",
                buttons=("Continue", "Cancel"),
                severity=hou.severityType.ImportantMessage,
                default_choice=1,
            )
            if warning_response == 1:
                return False
        return True

    def _open_file(self, path: Path) -> None:
        hou.hipFile.load(
            str(path),
            suppress_save_prompt=True,
            ignore_load_warnings=self._ignore_load_warnings,
        )

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        hou.hipFile.clear(suppress_save_prompt=True)
        hou.hipFile.save(str(path))


log = logging.getLogger(__name__)


class HShotFileManager(HFileManager):
    _department: str

    class DEPARTMENT(str, Enum):
        CFX = "cfx"
        FX = "fx"
        FLO = "flo"
        LIGHTING = "lighting"
        RENDER = "render"

    def __init__(
        self,
        *,
        override_dept: str | None = None,
        override_entity_code: str | None = None,
        ignore_load_warnings: bool = False,
    ):
        if override_dept:
            self._department = override_dept
        else:
            department_dialog = FilteredListDialog(
                get_main_qt_window(),
                [
                    self.DEPARTMENT.CFX,
                    self.DEPARTMENT.FX,
                    self.DEPARTMENT.FLO,
                    self.DEPARTMENT.LIGHTING,
                    self.DEPARTMENT.RENDER,
                ],
                "Department Select",
                include_filter_field=False,
                accept_button_name="Select",
            )
            department_dialog.exec_()

            self._department = department_dialog.get_selected_item() or ""

        if not self._department:
            return

        super().__init__(
            Shot,
            versioning=True,
            version_glob="{}_v*.{}",
            override_entity_code=override_entity_code,
            ignore_load_warnings=ignore_load_warnings,
        )

    def _generate_filename_ext(self, entity) -> tuple[str, str]:
        return self._department, "hipnc"

    def _get_subpath(self) -> str:
        return self._department

    def _post_open_file(self, entity: SGEntity):
        shot = cast(Shot, entity)

        if self._department == HShotFileManager.DEPARTMENT.CFX:
            shot_in = 940
            shot_out = shot.cut_out + 5
        elif self._department in (
            HShotFileManager.DEPARTMENT.LIGHTING,
            HShotFileManager.DEPARTMENT.RENDER,
        ):
            shot_in = shot.cut_in
            shot_out = shot.cut_out
        else:
            shot_in = shot.cut_in - 5
            shot_out = shot.cut_out + 5

        hou.playbar.setFrameRange(shot_in, shot_out)
        hou.playbar.setPlaybackRange(shot_in, shot_out)
        hou.setFrame(shot_in)

        # update substeps
        try:
            hou.node("/stage/PUBLISH").parm("f3").set(1.0 / shot.substeps)  # type: ignore[union-attr]
        except Exception:
            pass

    def _open_file(self, path):
        def do_post_open_file(event: hou.hipFileEventType) -> None:
            if event != hou.hipFileEventType.AfterLoad:
                return
            try:
                shot_code = str(hou.contextOption("SHOT")).split("/").pop()
                conn = DB.Get(DB_Config, auto_update=False)
                shot = conn.get_shot_by_code(shot_code)
                self._post_open_file(shot)
            except Exception:
                print("Failed to update frame range!")

            hou.hipFile.removeEventCallback(do_post_open_file)

        # hou.hipFile.load interrupts the running of the script so we have to
        # call _post_open_file with a callback instead
        hou.hipFile.addEventCallback(do_post_open_file)
        super()._open_file(path)

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        super(HShotFileManager, HShotFileManager)._setup_file(self, path, entity)
        shot = cast(Shot, entity)

        if shot.path:
            hou.setContextOption("SHOT", shot.path)

        stage: hou.Node = hou.node("/stage")  # type: ignore[assignment]

        load_layer = stage.createNode("sdm223::main::LnD_Load_Layers::1.0")
        load_layer.setUserData("nodeshape", "bulge_down")
        load_layer.parm("shot").set("$JOB/`@SHOT`")  # type: ignore[union-attr]

        muted_deps: list[str] = []
        if self._department == HShotFileManager.DEPARTMENT.CFX:
            muted_deps = ["cfx", "fx", "layout", "lighting"]
        elif self._department == HShotFileManager.DEPARTMENT.FLO:
            muted_deps = ["cfx", "flo", "lighting"]
        elif self._department == HShotFileManager.DEPARTMENT.FX:
            muted_deps = ["fx"]
        elif self._department == HShotFileManager.DEPARTMENT.LIGHTING:
            muted_deps = ["lighting"]

        for dep in muted_deps:
            load_layer.parm(f"{dep}_enable").set(0)  # type: ignore[union-attr]

        if env_stub := (shot.set or self._conn.get_sequence_by_stub(shot.sequence).set):  # type: ignore[arg-type]
            layout = self._conn.get_env_by_stub(env_stub)
            load_layer.parm("layout_path").set(f"$JOB/{layout.path}/main.usd")  # type: ignore[union-attr]

        layer_break = stage.createNode("layerbreak")

        begin_dep = stage.createNode("null")
        begin_dep.setName(f"BEGIN_{self._department.upper()}")

        end_dep = stage.createNode("null")
        end_dep.setName(f"END_{self._department.upper()}")

        publish = stage.createNode("usd_rop")
        publish.setName("PUBLISH")
        publish.parm("lopoutput").set("$HIP/usd/main.usd")  # type: ignore[union-attr]
        publish.parm("trange").set("normal")  # type: ignore[union-attr]

        layer_break.setInput(0, load_layer)
        begin_dep.setInput(0, layer_break)
        end_dep.setInput(0, begin_dep)
        publish.setInput(0, end_dep)

        end_dep.setPosition((0, 1))
        begin_dep.setPosition((0, 4))
        layer_break.setPosition((0, 5))
        load_layer.setPosition((0, 6))

        if self._department == HShotFileManager.DEPARTMENT.CFX:
            publish.parm("f1").set(shot.cut_in - 5)  # type: ignore[union-attr]
            sublayer = stage.createNode("sublayer")
            sublayer.setPosition((0, 2))
            sublayer.setInput(0, begin_dep)
            end_dep.setInput(0, sublayer)

            for idx, stub in enumerate(shot.assets):
                asset = self._conn.get_asset_by_stub(stub)
                if asset.name == "rayden":
                    char_cfx = stage.createNode("cooks23::RAYDEN_CFXSHOT::1.0")
                elif asset.name == "robin":
                    char_cfx = stage.createNode("cooks23::dev::ROBIN_CFXSHOT::1.0")
                else:
                    continue
                char_cfx.setPosition((idx + 1, 3))
                char_cfx.setInput(0, begin_dep)
                sublayer.setNextInput(char_cfx)

        elif self._department == HShotFileManager.DEPARTMENT.RENDER:
            if shot.substeps != 1:
                deform_substeps = stage.createNode("rendergeometrysettings")
                deform_substeps.setName("deformation_substeps")
                deform_substeps.parm("primpattern").set("/camera /character")  # type: ignore[union-attr]
                deform_substeps.parm(
                    "xn__primvarsriobjectgeosamples_control_iwbcg"
                ).set("set")  # type: ignore[union-attr]
                deform_substeps.parm("xn__primvarsriobjectgeosamples_hjbcg").set(  # type: ignore[union-attr]
                    shot.substeps
                )
                deform_substeps.setPosition((0, 2))
                deform_substeps.setInput(0, begin_dep)
                end_dep.setInput(0, deform_substeps)

        self._post_open_file(shot)

        hou.hipFile.save()


if TYPE_CHECKING:
    import typing


_MATLIB_NAME = "Material_Library"
_MATNAME = "matname"
_NO_TEXTURES = "NO_EXPORTED_TEXTURES"


# https://github.com/Student-Accomplice-Pipeline-Team/accomplice_pipe/blob/prod/pipe/accomplice/software/houdini/pipe/tools/shading/edit_shader.py
class MatlibManager:
    _conn: DB

    def __init__(self, node: hou.LopNode | None = None) -> None:
        self._conn = DB.Get(DB_Config, auto_update=False)
        if node:
            self._init_hda(node)

    def _init_hda(self, node: hou.LopNode) -> None:
        """Initialize values on the HDA instance.
        Note that self.node does not work before initialization, so
        node is passed in as an arg"""
        var_name = node.parm("variant_name")
        assert var_name is not None
        var_id = node.parm("variant_id")
        assert var_id is not None

        # get variant list from SG
        variants = self._asset.variants
        if not variants:
            var_name.set("main")
            assert self._asset.id is not None
            var_id.set(self._asset.id)
            return

        # set default variant on the hda
        default_geo_var = self._conn.get_asset_by_stub(self._asset.variants[0])
        assert default_geo_var.variant_name is not None
        assert default_geo_var.id is not None
        var_name.set(default_geo_var.variant_name)
        var_id.set(default_geo_var.id)

        self._update_default_mat_var(default_geo_var, node=node)

        self.update_base_path(node=node)

    @property
    def _asset(self) -> Asset:
        """Get asset based off of the path of the current hipfile"""
        asset_name = str(hou.contextOption("ASSET"))
        a = self._conn.get_asset_by_attr("name", asset_name)
        return a

    @property
    def _hip(self) -> Path:
        """Get $HIP variable as a Path object"""
        return Path(hou.hscriptStringExpression("$HIP"))

    @property
    def _hsite(self) -> Path:
        """Get $HSITE variable as a Path object"""
        return Path(hou.hscriptStringExpression("$HSITE"))

    @property
    def material_info(self) -> MaterialInfo | None:
        """Attempt to get mat.json file for selected variant"""
        try:
            variant = self._conn.get_asset_by_id(self.geo_variant_id)

            if not (variant_name := variant.variant_name):
                variant_name = "main"
            with open(
                self._hip
                / "tex"
                / variant_name
                / "variants"
                / self.mat_variant_name
                / "mat.json",
                "r",
            ) as f:
                return MaterialInfo.from_json(f.read())
        except Exception:
            return None

    @property
    def matlib(self) -> hou.LopNode:
        """Get Material Library node inside of current node"""
        node = hou.node(f"./{_MATLIB_NAME}")
        assert isinstance(node, hou.LopNode)
        return node

    @property
    def node(self) -> hou.LopNode:
        """Get current node (the HDA)"""
        node = hou.node("./")
        assert isinstance(node, hou.LopNode)
        return node

    @property
    def geo_variant_id(self) -> int:
        """Get the id of the current geo variant"""
        geo_var_id = self.node.parm("variant_id")
        assert geo_var_id is not None
        # if it hasn't been set yet, set it to the default value
        if (node_val := geo_var_id.evalAsInt()) == -1:
            default = int(self.get_variant_list()[0])
            geo_var_id.set(default)
            return default
        return node_val

    @geo_variant_id.setter
    def geo_variant_id(self, id: int) -> None:
        """Set the variant ID and update the variant name"""
        geo_var_id = self.node.parm("variant_id")
        assert geo_var_id is not None
        geo_var_id.set(id)
        asset = self._conn.get_asset_by_id(id)
        assert asset.variant_name is not None
        var_name = self.node.parm("variant_name")
        assert var_name is not None
        if self._asset.variants:
            var_name.set(asset.variant_name)
        else:
            var_name.set("main")

        self._update_default_mat_var(asset)
        self.update_base_path()

    @property
    def variant_name(self) -> str:
        var_name = self.node.parm("variant_name")
        assert var_name is not None
        if (node_val := var_name.evalAsString()) == "none":
            variants = self._asset.variants
            variant_name: str
            if variants:
                var1 = self._conn.get_asset_by_stub(variants[0])
                assert var1.variant_name is not None
                variant_name = var1.variant_name
            else:
                variant_name = "main"
            var_name.set(variant_name)
            return variant_name
        return node_val

    @property
    def mat_variant_name(self) -> str:
        mat_var_name = self.node.parm("mat_var")
        assert mat_var_name is not None
        return mat_var_name.evalAsString()

    def _update_default_mat_var(
        self, default_geo_var: Asset, /, node: hou.Node | None = None
    ) -> None:
        # this may be called before initialization, so `self.node` may not work
        if not node:
            node = self.node
        # update mat_variant on the hda
        mat_var = node.parm("mat_var")
        assert mat_var is not None
        mat_var.set(next(iter(default_geo_var.material_variants), _NO_TEXTURES))

    def update_base_path(self, node: hou.LopNode | None = None) -> None:
        if not node:
            # this lets us call update_base_path from inside self._init_hda
            node = self.node

        base_path = node.parm("base_path")
        assert base_path is not None

        var_name = node.parm("variant_name")
        assert var_name is not None

        mat_var_name = node.parm("mat_var")
        assert mat_var_name is not None

        base_path.set(
            f"tex/{var_name.evalAsString()}/variants/{mat_var_name.evalAsString()}"
        )

    @staticmethod
    def _get_map_paths(
        node: hou.Node, parm: str = "filename"
    ) -> typing.Generator[Path, None, None]:
        """Helper function to get all the maps referred to by a <UDIM>
        wildcard as Path objects"""
        filename_parm = node.parm(parm)
        assert filename_parm is not None
        dir, filename = filename_parm.evalAsString().rsplit("/", 1)
        return Path(dir).glob(filename.replace("<UDIM>", "*"))

    def _cleanup_matnet(
        self,
        new_items: typing.Iterable[hou.NetworkMovableItem],
        tex_set_info: TexSetInfo,
    ) -> None:
        """Clean up a matnet after it has been imported from cpio"""

        # locate relevant nodes
        control_node: hou.Node
        displacement_map: hou.Node
        displacement_nodes: list[hou.Node] = []
        emissive_node: hou.Node
        ior_node: hou.Node
        normal_node: hou.Node
        presence_node: hou.Node
        preview_node: hou.Node
        pvwemissive_node: hou.Node
        for item in new_items:
            if item.networkItemType() != hou.networkItemType.Node:
                continue
            item = cast(hou.Node, item)
            name = item.name().lower()
            if "disp" in name:
                if name.startswith("disp"):
                    displacement_map = item
                else:
                    displacement_nodes.append(item)
            elif name.startswith("ior"):
                ior_node = item
            elif name.startswith("emissive"):
                emissive_node = item
            elif name.startswith("presence"):
                presence_node = item
            elif name.startswith("control"):
                control_node = item
            elif name.startswith("normal_"):
                normal_node = item
            elif name.startswith("usdpreview"):
                preview_node = item
            elif name.startswith("pvwemissive"):
                pvwemissive_node = item

        # Remove optional maps
        if not next(self._get_map_paths(ior_node), None):
            ior_node.destroy()

        if not next(self._get_map_paths(emissive_node), None):
            emissive_node.destroy()

        if not next(self._get_map_paths(presence_node), None):
            preview_node.setInput(8, None)
            presence_node.destroy()

        if not next(self._get_map_paths(pvwemissive_node, parm="file"), None):
            pvwemissive_node.destroy()

        # Remove unused displacement nodes
        if not next(self._get_map_paths(displacement_map), None):
            displacement_map.destroy()
            for node in displacement_nodes:
                node.destroy()
            for parm in ["disp_depth", "disp_height"]:
                p = control_node.parm(parm)
                assert p is not None
                p.hide(True)

        # Set bump roughness undisplaced bool
        if (
            (tex_set_info.normal_source == NormalSource.NORMAL_HEIGHT)
            and (tex_set_info.displacement_source == DisplacementSource.HEIGHT)
            and (tex_set_info.normal_type == NormalType.BUMP_ROUGHNESS)
        ):
            undisplaced_parm = normal_node.parm("useUndisplacedPosition")
            assert undisplaced_parm is not None
            undisplaced_parm.set(True)

    def load_items_from_file(
        self, dest_node: hou.LopNode, file_path: str
    ) -> list[hou.NetworkMovableItem]:
        """Loads a VOP network into a LOP node. Returns list of added items"""
        before = dest_node.allItems()
        dest_node.loadItemsFromFile(file_path)
        after = dest_node.allItems()

        return list(set(after) - set(before))

    def _move_matnet(
        self, new_items: typing.Iterable[hou.NetworkMovableItem], x_pos: int
    ) -> None:
        # find the master netbox
        master_box = next(
            (
                cast(hou.NetworkBox, i)
                for i in new_items
                if (i.networkItemType() == hou.networkItemType.NetworkBox)
                and (cast(hou.NetworkBox, i).comment() == _MATNAME)
            ),
            None,
        )
        if not master_box:
            return
        master_box.setPosition((x_pos, 0))

    def _rename_matnet(
        self,
        new_items: typing.Iterable[hou.NetworkMovableItem],
        name: str,
        name_placeholder: str = _MATNAME,
    ) -> None:
        # iterate over new nodes and swap placeholder names for the shading group name
        for item in new_items:
            if item.networkItemType() == hou.networkItemType.Node:
                new_name = item.name().replace(name_placeholder, name)
                item.setName(new_name)

                # update "Shading Group Name" on control null
                if new_name == f"CONTROLS_{name}":
                    node = hou.node(item.path())
                    assert node is not None
                    node_name = node.parm("name")
                    assert node_name is not None
                    node_name.set(name)
            elif item.networkItemType() == hou.networkItemType.NetworkBox:
                item = cast(hou.NetworkBox, item)
                if item.comment() == name_placeholder:
                    item.setComment(name)

    def get_variant_list(self) -> list[str]:
        """Gets list of variants in the way that the HDA interface expects:
        [id1, label1, id2, label2, ...]"""
        if len(self._asset.variants):
            return [s for v in self._asset.variants for s in (str(v.id), v.disp_name)]
        else:
            return [str(self._asset.id), "Main"]

    def get_mat_variant_list(self) -> list[str]:
        """Gets list of mat variants in the way that the HDA interface
        expects: [id1, label1, id2, label2, ...]"""
        current_geo_var = self._conn.get_asset_by_id(self.geo_variant_id)
        mvs = list(current_geo_var.material_variants) or [_NO_TEXTURES]
        return [s for v in mvs for s in (v, v)]

    def export_selected_to_path(
        self, path: str, curr_name: str = _MATNAME, new_name: str = _MATNAME
    ) -> None:
        """Export selected items as a cpio file to the path given. For
        convenience, rename their suffixes to _MATNAME before exporting,
        then change their names back"""
        items = hou.selectedItems()
        self._rename_matnet(items, new_name, curr_name)
        items[0].parent().saveItemsToFile(items, path)
        self._rename_matnet(items, curr_name, new_name)

    def import_matnets(self) -> None:
        """Import a material network for each shading group in the export"""
        if not (mat_info := self.material_info):
            MessageDialog(
                get_main_qt_window(),
                "Error! Could not get material info. Make sure that textures "
                "have been exported for the currently selected variant.",
            ).exec_()
            return

        pos = count(start=0, step=20)
        for name, shading_group in mat_info.tex_sets.items():
            if shading_group.normal_type == NormalType.STANDARD:
                template_name = "standard"
            elif shading_group.normal_type == NormalType.BUMP_ROUGHNESS:
                template_name = "b2r"
            else:
                raise ValueError(
                    f"Unimplemented NormalType: {shading_group.normal_type}"
                )

            nodes = self.load_items_from_file(
                self.matlib, str(self._hsite / f"matl/{template_name}.cpio")
            )
            self._move_matnet(nodes, next(pos))
            self._rename_matnet(nodes, name)
            self._cleanup_matnet(nodes, shading_group)


class MatlibErrorChecker:
    @staticmethod
    def CheckFilepathsRelative(matlib: hou.LopNode) -> int:
        """Returns 1 if there are any absolute filepaths in the material
        library, 0 otherwise"""
        for node in matlib.children():
            if (fn := node.parm("filename")) is not None:
                if not fn.unexpandedString().startswith("$"):
                    return 1
        return 0


log = logging.getLogger(__name__)


class AnimPlayblastDialog(PlayblastDialog):
    _conn: DB
    _shot: Shot | None

    class SAVE_LOCS(PlayblastDialog.SAVE_LOCS):
        EDIT = SaveLocation(
            "Send to Edit",
            get_edit_path() / "anim" / datetime.now().strftime("%m-%d-%y"),
            Playblaster.PRESET.EDIT_SQ,
        )

    SG_ID = "sg"
    CUSTOM_ID = "custom"

    def __init__(self, parent):
        self._conn = DB.Get(DB_Config)
        try:
            code = str(mc.fileInfo("code", query=True)[0])
            self._shot = self._conn.get_shot_by_code(code)
        except Exception:
            self._shot = None

        self._shot_dialog_configs = [
            MShotDialogConfig(
                id=self.SG_ID,
                name="Shot (from SG)",
                save_locs=[
                    (self.SAVE_LOCS.EDIT, False),
                    (self.SAVE_LOCS.CURRENT, True),
                    (self.SAVE_LOCS.CUSTOM, False),
                ],
            ),
            MShotDialogConfig(
                id=self.CUSTOM_ID,
                name="Custom",
                save_locs=[
                    (self.SAVE_LOCS.EDIT, False),
                    (self.SAVE_LOCS.CURRENT, True),
                    (self.SAVE_LOCS.CUSTOM, False),
                ],
            ),
        ]
        super().__init__(parent, self._shot_dialog_configs, "LnD Anim Playblast")

    def _setup_ui(self):
        super()._setup_ui()

        # disable the SG option if we can't find this shot in SG
        if not self._shot:
            self._enabled_shot_cbs[self.SG_ID].toggle()
            self._enabled_shot_cbs[self.SG_ID].setEnabled(False)

        anim_settings_widget = QWidget(self)
        anim_settings_layout = QGridLayout(anim_settings_widget)
        self._shot_pass = QComboBox(self)
        self._shot_pass.addItems(["Blocking #", "Polish #"])
        self._shot_pass.setEditable(True)
        self._shot_pass.setValidator(
            QRegExpValidator(QRegExp("(?:Blocking|Polish) #\d+"))
        )
        anim_settings_layout.addWidget(QLabel("Pass"), 0, 0)
        anim_settings_layout.addWidget(self._shot_pass, 0, 1, 1, 2)

        self._main_layout.insertWidget(2, anim_settings_widget)

        # Create UI for custom shot
        custom_shot_widget = QWidget(self)
        custom_shot_layout = QGridLayout(custom_shot_widget)

        self._custom_in = QSpinBox(self, maximum=10000, minimum=0, value=1001)
        self._custom_out = QSpinBox(self, maximum=10000, minimum=0, value=1100)
        custom_shot_layout.addWidget(QLabel("Custom In"), 1, 1)
        custom_shot_layout.addWidget(self._custom_in, 1, 2)
        custom_shot_layout.addWidget(QLabel("Custom Out"), 1, 3)
        custom_shot_layout.addWidget(self._custom_out, 1, 4)

        self._custom_camera = QComboBox(self)
        self._custom_camera.addItems(cameras := mc.ls(cameras=True, visible=True))
        self._custom_camera.setCurrentIndex(0)
        self._custom_camera.setValidator(QRegExpValidator(QRegExp("|".join(cameras))))
        custom_shot_layout.addWidget(QLabel("Custom Camera"), 2, 1)
        custom_shot_layout.addWidget(self._custom_camera, 2, 2, 1, 2)

        # disable UI if custom shot not enabled
        (escb := self._enabled_shot_cbs[self.CUSTOM_ID]).toggled.connect(
            checkbox_callback_helper(escb, custom_shot_widget)
        )

        self._main_layout.insertWidget(3, custom_shot_widget)

    def _generate_config(self) -> MPlayblastConfig:
        date = datetime.now().strftime("%m-%d-%y")
        shots: list[MShotPlayblastConfig] = []

        if self.is_shot_enabled(self.SG_ID):
            assert self._shot is not None
            sg_config = next(c for c in self._shot_dialog_configs if c.id == self.SG_ID)
            shots.append(
                MShotPlayblastConfig(
                    camera="|__mayaUsd__|shotCamParent|shotCam",
                    shot=self._shot,
                    paths=self.save_locations_to_paths(
                        self.SG_ID,
                        (sl[0] for sl in sg_config.save_locs),
                        f"{self._shot.code}_{date}",
                    ),
                    tails=(5, 5),
                )
            )

        if self.is_shot_enabled(self.CUSTOM_ID):
            custom_config = next(
                c for c in self._shot_dialog_configs if c.id == self.CUSTOM_ID
            )
            current_filename = mc.file(query=True, sceneName=True, shortName=True)
            shots.append(
                MShotPlayblastConfig(
                    camera=self._custom_camera.currentText(),
                    shot=dummy_shot(
                        "custom",
                        inv := self._custom_in.value(),
                        outv := self._custom_out.value(),
                        cut_duration=outv - inv,
                    ),
                    paths=self.save_locations_to_paths(
                        self.CUSTOM_ID,
                        (sl[0] for sl in custom_config.save_locs),
                        f"customPB_{current_filename}_{date}",
                    ),
                )
            )

        return MPlayblastConfig(
            builtin_huds=[
                PlayblastDialog.MAYA_HUDS.CAM_NAME,
                PlayblastDialog.MAYA_HUDS.CUR_FRAME,
                PlayblastDialog.MAYA_HUDS.FOCAL_LENGTH,
            ],
            custom_huds=[
                PlayblastDialog.CUSTOM_HUDS.FILENAME,
                PlayblastDialog.CUSTOM_HUDS.ARTIST,
                HudDefinition(
                    "LnDshot",
                    command=lambda: (
                        self._shot.code if self._shot else "No shot code found"
                    ),
                    section=7,
                    event="SceneSaved",
                ),
                HudDefinition(
                    "LnDpass",
                    command=lambda: self._shot_pass.currentText(),
                    label="Pass:",
                    section=5,
                    event="SceneSaved",
                ),
            ],
            dof=self.use_dof,
            hardware_fog=self.use_hardware_fog,
            lighting=self.use_lighting,
            shadows=self.use_shadows,
            shots=shots,
            ssao=self.use_ssao,
        )


if TYPE_CHECKING:
    from typing import Any, Generator

log = logging.getLogger(__name__)


class MPlayblaster(Playblaster):
    _config: MPlayblastConfig
    _extra_kwargs: dict[str, Any]

    def __init__(self) -> None:
        super().__init__()

    def configure(self, config: MPlayblastConfig) -> MPlayblaster:
        self._config = config
        return self

    def _write_images(self, path: str) -> None:
        """Maya implementation of playblasting image frames"""
        active_editor = str(mc.sequenceManager(query=True, modelPanel=True))
        self._extra_kwargs["viewport_options"].update(
            {
                "twoSidedLighting": mc.modelEditor(
                    active_editor, query=True, twoSidedLighting=True
                ),
            }
        )
        self._extra_kwargs["viewport2_options"].update(
            {
                **{
                    k: mc.getAttr(f"hardwareRenderingGlobals.{k}")
                    for k in (
                        "hwFogAlpha",
                        "hwFogFalloff",
                        "hwFogDensity",
                        "hwFogEnd",
                        "hwFogColorR",
                        "hwFogColorG",
                        "hwFogColorB",
                        "hwFogStart",
                    )
                },
                "alphaCutPrepass": True,
                "enableTextureMaxRes": True,
                "maxHardwareLights": 16,
                "multiSampleEnable": True,
            }
        )

        capture(
            width=1920,
            height=816,
            filename=path,
            start_frame=(self._shot.cut_in - 5),
            end_frame=(self._shot.cut_out + 5),
            format="image",
            compression="png",
            off_screen=True,
            show_ornaments=True,
            overwrite=True,
            maintain_aspect_ratio=False,
            viewer=0,
            **self._extra_kwargs,
        )

    def playblast(self) -> None:
        with (
            applied_hud(self._config.builtin_huds, self._config.custom_huds),
            maintain_selection(),
        ):
            mc.select(clear=True)

            # assemble kwargs from config options
            global_kwargs: dict[str, Any] = {
                "viewport_options": {},
                "viewport2_options": {},
                "camera_options": {},
            }

            if self._config.dof:
                global_kwargs["camera_options"].update({"depthOfField": True})

            if self._config.hardware_fog:
                global_kwargs["viewport_options"].update({"fogging": True})
                global_kwargs["viewport2_options"].update({"hwFogEnable": True})

            if self._config.lighting:
                global_kwargs["viewport_options"].update({"displayLights": "all"})

            if self._config.shadows:
                global_kwargs["viewport_options"].update({"shadows": True})

            if self._config.ssao:
                global_kwargs["viewport2_options"].update({"ssaoEnable": True})

            # iterate over shots and playblast
            for shot_config in self._config.shots:
                # assemble shot-specific kwargs
                self._extra_kwargs = copy.deepcopy(global_kwargs)
                if shot_config.use_sequencer:
                    self._extra_kwargs["use_camera_sequencer"] = True
                else:
                    self._extra_kwargs["camera"] = shot_config.camera

                with self(shot_config.shot):
                    super()._do_playblast(
                        shot_config.paths,
                        shot_config.tails,
                    )


@contextmanager
def applied_hud(
    builtin_huds: list[str], custom_huds: list[HudDefinition]
) -> Generator[None, None, None]:
    # hide current huds and store current state
    orig_visibility: dict[str, bool] = {}
    orig_huds: list[str] = mc.headsUpDisplay(query=True, listHeadsUpDisplays=True)  # type: ignore[assignment]
    for hud in orig_huds:
        vis = bool(mc.headsUpDisplay(hud, query=True, visible=True))
        orig_visibility[hud] = vis
        if vis:
            mc.headsUpDisplay(hud, edit=True, visible=False)

    # display requested builtin huds
    for hud in builtin_huds:
        mc.headsUpDisplay(hud, edit=True, visible=True)

    # create requested custom huds
    for chud in custom_huds:
        if chud.name in orig_huds:
            mc.headsUpDisplay(chud.name, remove=True)

        kwargs: dict[str, Any] = dict()
        if chud.idle_refresh:
            kwargs.update({"attachToRefresh": True})
        else:
            kwargs.update({"event": chud.event})

        mc.headsUpDisplay(
            chud.name,
            block=mc.headsUpDisplay(nextFreeBlock=chud.section),  # type: ignore[arg-type]
            blockSize=chud.blockSize,
            command=chud.command,
            label=chud.label,
            labelFontSize=chud.labelFontSize,
            section=chud.section,
            **kwargs,
        )

    try:
        yield
    finally:
        # restore original visibility
        for hud, state in orig_visibility.items():
            mc.headsUpDisplay(hud, edit=True, visible=state)

        for chud in custom_huds:
            mc.headsUpDisplay(chud.name, remove=True)


log = logging.getLogger(__name__)


class PrevisPlayblastDialog(PlayblastDialog):
    _camera_shot_lookup: dict[str, str]
    _sequence_dialog_configs: list[MShotDialogConfig]
    _shot_dialog_configs: list[MShotDialogConfig]

    class SAVE_LOCS(PlayblastDialog.SAVE_LOCS):
        EDIT = SaveLocation(
            "Send to Edit",
            get_edit_path() / "previs" / datetime.now().strftime("%m-%d-%y"),
            Playblaster.PRESET.EDIT_SQ,
        )

    def __init__(self, parent) -> None:
        shot_node_list: list[str] = mc.sequenceManager(listShots=True) or []  # type: ignore[assignment]

        # generate lookup table for matching cameras to shots
        self._camera_shot_lookup = {
            str(mc.shot(node, query=True, currentCamera=True)): str(
                mc.shot(node, query=True, shotName=True)
            )
            for node in shot_node_list
        }

        self._shot_dialog_configs = [
            MShotDialogConfig(
                id=shot_node,
                name=str(mc.shot(shot_node, query=True, shotName=True)),
                save_locs=[
                    (self.SAVE_LOCS.EDIT, True),
                    (self.SAVE_LOCS.CURRENT, False),
                    (self.SAVE_LOCS.CUSTOM, False),
                ],
            )
            for shot_node in shot_node_list
        ]
        self._sequence_dialog_configs = [
            MShotDialogConfig(
                id=str(mc.sequenceManager(query=True, writableSequencer=True)),
                name="Camera Sequencer",
                save_locs=[
                    (self.SAVE_LOCS.EDIT, True),
                    (self.SAVE_LOCS.CURRENT, True),
                    (self.SAVE_LOCS.CUSTOM, False),
                ],
            )
        ]

        super().__init__(
            parent,
            self._shot_dialog_configs + self._sequence_dialog_configs,
            "Lnd Previs Playblast",
        )

    def _do_camera_shot_lookup(self) -> str:
        """Look up the current shot based off of the camera"""
        panel: str = mc.getPanel(withLabel="CapturePanel")  # type: ignore[assignment]
        try:
            if panel:
                camera = (
                    str(mc.modelEditor(panel, query=True, camera=True)).split("|").pop()  # type: ignore[arg-type]
                )
                return self._camera_shot_lookup[camera]
        except KeyError:
            pass
        return "No shot data"

    def _generate_config(self) -> MPlayblastConfig:
        seq_node = str(mc.sequenceManager(query=True, writableSequencer=True))
        date = datetime.now().strftime("%m-%d-%y")
        return MPlayblastConfig(
            builtin_huds=[
                PlayblastDialog.MAYA_HUDS.CAM_NAME,
                PlayblastDialog.MAYA_HUDS.CUR_FRAME,
                PlayblastDialog.MAYA_HUDS.FOCAL_LENGTH,
            ],
            custom_huds=[
                PlayblastDialog.CUSTOM_HUDS.FILENAME,
                PlayblastDialog.CUSTOM_HUDS.ARTIST,
                HudDefinition(
                    "LnDshot",
                    command=self._do_camera_shot_lookup,
                    section=7,
                    idle_refresh=True,
                ),
            ],
            dof=self.use_dof,
            hardware_fog=self.use_hardware_fog,
            lighting=self.use_lighting,
            shadows=self.use_shadows,
            shots=[
                MShotPlayblastConfig(
                    camera=str(mc.shot(config.id, query=True, currentCamera=True)),
                    shot=dummy_shot(
                        shot_name := str(mc.shot(config.id, query=True, shotName=True)),
                        int(mc.shot(config.id, query=True, startTime=True)),
                        int(mc.shot(config.id, query=True, endTime=True)),
                        int(mc.shot(config.id, query=True, clipDuration=True)),
                    ),
                    paths=self.save_locations_to_paths(
                        config.id,
                        (sl[0] for sl in config.save_locs),
                        f"{shot_name}_{date}",
                    ),
                )
                for config in self._shot_dialog_configs
                if self.is_shot_enabled(config.id)
            ]
            + [
                MShotPlayblastConfig(
                    camera=None,
                    shot=dummy_shot(
                        code=(name := Path(mc.file(query=True, sceneName=True)).stem),  # type: ignore[arg-type]
                        cut_in=(ci := mc.getAttr(f"{seq_node}.minFrame")),
                        cut_out=(co := mc.getAttr(f"{seq_node}.maxFrame")),
                        cut_duration=co - ci,
                    ),
                    paths=self.save_locations_to_paths(
                        config.id, (sl[0] for sl in config.save_locs), f"{name}_{date}"
                    ),
                    use_sequencer=True,
                )
                for config in self._sequence_dialog_configs
                if self.is_shot_enabled(config.id)
            ],
            ssao=self.use_ssao,
        )


if TYPE_CHECKING:
    from typing import Callable, Iterable

    from .struct import MPlayblastConfig, MShotDialogConfig

log = logging.getLogger(__name__)


class ClickableQLabel(QLabel):
    clicked = QtCore.Signal()

    def mousePressEvent(self, ev):
        self.clicked.emit()


class PlayblastDialog(ButtonPair, QtWidgets.QMainWindow):
    """Dialog for a generic Maya playblaster. To subclass:
    - subclass SAVE_LOCS as necessary to add more locations
    - define a `_generate_config` function
    """

    _central_widget: QWidget
    _custom_folder_text: QLabel
    _enabled_loc_cbs: dict[str, dict[str, QCheckBox]]
    _enabled_shot_cbs: dict[str, QCheckBox]
    _main_layout: QtWidgets.QLayout
    _use_dof: QCheckBox
    _use_hardware_fog: QCheckBox
    _use_lighting: QCheckBox
    _use_shadows: QCheckBox
    _use_ssao: QCheckBox

    playblaster = MPlayblaster()
    shot_configs: list[MShotDialogConfig]

    class SAVE_LOCS:
        CUSTOM = SaveLocation("Custom Folder", "", Playblaster.PRESET.WEB)
        CURRENT = SaveLocation("Current Folder", "", Playblaster.PRESET.WEB)

    class MAYA_HUDS:
        CAM_NAME = "HUDCameraNames"
        CUR_FRAME = "HUDCurrentFrame"
        FOCAL_LENGTH = "HUDFocalLength"

    class CUSTOM_HUDS:
        FILENAME = HudDefinition(
            "LnDfilename",
            command=lambda: str(mc.file(query=True, sceneName=True)),
            event="SceneSaved",
            label="File:",
            section=5,
        )
        ARTIST = HudDefinition(
            "LnDartist",
            command=lambda: os.getlogin(),
            event="SceneOpened",
            label="Artist:",
            section=5,
        )

    def __init__(
        self,
        parent: QWidget | None,
        shot_configs: list[MShotDialogConfig],
        windowTitle: str = "LnD Playblast",
    ) -> None:
        super().__init__(parent, windowTitle=windowTitle)
        # initialize SAVE_LOCS paths
        self.SAVE_LOCS.CUSTOM._path = lambda: self._custom_folder_text.text()
        self.SAVE_LOCS.CURRENT._path = lambda: (
            Path(
                mc.file(query=True, sceneName=True)  # type: ignore[arg-type]
            ).parent
        )

        # initialize other values
        self.shot_configs = shot_configs
        self._enabled_shot_cbs = dict()
        self._enabled_loc_cbs = defaultdict(dict)
        self._setup_ui()

    def _setup_ui(self) -> None:
        # set up main layout
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)
        self._main_layout = QtWidgets.QVBoxLayout()
        self._central_widget.setLayout(self._main_layout)

        # title
        title = QLabel("Playblast")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: bold;")
        self._main_layout.addWidget(title, 0)

        # iterate over shot configs and add them to the table
        playblasts_layout = QtWidgets.QGridLayout()
        for idx, pb in enumerate(self.shot_configs):
            # create shot enable checkbox
            shot_enable_cb_widget = QWidget()
            shot_enable_cb_layout = QHBoxLayout(shot_enable_cb_widget)
            self._enabled_shot_cbs[pb.id] = QCheckBox()
            cb = self._enabled_shot_cbs[pb.id]
            cb.setChecked(True)
            shot_enable_cb_layout.addWidget(cb)

            shot_label = ClickableQLabel(f"<b>{pb.name}</b>", cb)
            shot_label.clicked.connect(self._click_checkbox(cb))
            shot_enable_cb_layout.addWidget(shot_label)
            playblasts_layout.addWidget(shot_enable_cb_widget, idx + 1, 0, 1, 1)

            # disable the output checkboxes when the shot is disabled
            outputs_container = QWidget()
            cb.toggled.connect(checkbox_callback_helper(cb, outputs_container))
            outputs_layout = QHBoxLayout(outputs_container)
            playblasts_layout.addWidget(outputs_container, idx + 1, 1, 1, 1)

            # create the location checkboxes
            for location, enabled_by_default in pb.save_locs:
                loc_cb = QCheckBox(location.name)
                loc_cb.setChecked(enabled_by_default)
                self._enabled_loc_cbs[pb.id][location.name] = loc_cb
                outputs_layout.addWidget(loc_cb)

            playblasts_layout.addWidget(outputs_container, idx + 1, 2, 1, 1)

        # Create check all/none buttons
        shots_toggle_container = QWidget()
        shots_toggle_container.setStyleSheet("margin: 0; padding: 0;")
        shots_toggle_layout = QHBoxLayout(shots_toggle_container)
        shots_all = QtWidgets.QPushButton("All", self)
        shots_all.clicked.connect(
            lambda: [
                cb.setChecked(True)  # type: ignore[func-returns-value]
                for cb in self._enabled_shot_cbs.values()
                if cb.isEnabled()
            ]
        )
        shots_toggle_layout.addWidget(shots_all)
        shots_none = QtWidgets.QPushButton("None", self)
        shots_none.clicked.connect(
            lambda: [
                cb.setChecked(False)  # type: ignore[func-returns-value]
                for cb in self._enabled_shot_cbs.values()
                if cb.isEnabled()
            ]
        )
        shots_toggle_layout.addWidget(shots_none)

        outputs_toggle_container = QWidget()
        outputs_toggle_layout = QHBoxLayout(outputs_toggle_container)
        for loc, _ in pb.save_locs:
            loc_toggle_container = QWidget()
            loc_toggle_container.setStyleSheet("margin: 0; padding: 0;")
            loc_toggle_layout = QHBoxLayout(loc_toggle_container)
            loc_all = QtWidgets.QPushButton("All", self)
            loc_all.clicked.connect(
                self._set_checkboxes(self._enabled_loc_cbs.values(), loc.name, True)
            )
            loc_toggle_layout.addWidget(loc_all)
            loc_none = QtWidgets.QPushButton("None", self)
            loc_none.clicked.connect(
                self._set_checkboxes(self._enabled_loc_cbs.values(), loc.name, False)
            )
            loc_toggle_layout.addWidget(loc_none)
            outputs_toggle_layout.addWidget(loc_toggle_container)

        playblasts_layout.addWidget(shots_toggle_container, 0, 0, 1, 1)
        playblasts_layout.addWidget(outputs_toggle_container, 0, 1)

        # configure playblast widget group
        playblasts_widget = QWidget()
        playblasts_widget.setLayout(playblasts_layout)
        playblasts_scroll_area = QtWidgets.QScrollArea()
        playblasts_scroll_area.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff
        )
        playblasts_scroll_area.setWidget(playblasts_widget)
        playblasts_scroll_area.setWidgetResizable(True)
        self._main_layout.addWidget(playblasts_scroll_area)

        # create lighting, shadow, ssao toggles
        active_editor = str(mc.sequenceManager(query=True, modelPanel=True))
        toggles_layout = QHBoxLayout()
        toggles_widget = QWidget()
        toggles_widget.setLayout(toggles_layout)
        self._use_lighting = QCheckBox("Use Lighting")
        self._use_lighting.setChecked(
            mc.modelEditor(active_editor, query=True, displayLights=True) == "all"
        )
        toggles_layout.addWidget(self._use_lighting)
        self._use_shadows = QCheckBox("Use Shadows")
        self._use_shadows.setChecked(
            bool(mc.modelEditor(active_editor, query=True, shadows=True))
        )
        toggles_layout.addWidget(self._use_shadows)
        self._use_ssao = QCheckBox("Use Anti-aliasing")
        self._use_ssao.setChecked(
            bool(mc.getAttr("hardwareRenderingGlobals.ssaoEnable"))
        )
        toggles_layout.addWidget(self._use_ssao)
        self._use_hardware_fog = QCheckBox("Use Hardware Fog")
        self._use_hardware_fog.setChecked(
            bool(mc.modelEditor(active_editor, query=True, fogging=True))
        )
        toggles_layout.addWidget(self._use_hardware_fog)
        self._use_dof = QCheckBox("Use DoF")
        camera = str(
            mc.modelEditor(active_editor, query=True, activeView=True, camera=True)
        )
        self._use_dof.setChecked(bool(mc.camera(camera, query=True, depthOfField=True)))
        toggles_layout.addWidget(self._use_dof)
        self._main_layout.addWidget(toggles_widget)

        # custom folder prompt
        custom_folder_layout = QHBoxLayout()
        self._custom_folder_text = QLabel(os.getenv("TMPDIR", os.getenv("TEMP", "tmp")))
        custom_folder_button = QtWidgets.QPushButton(text="Set Custom Folder")
        custom_folder_button.clicked.connect(self._set_custom_folder)
        custom_folder_layout.addWidget(self._custom_folder_text)
        custom_folder_layout.addWidget(custom_folder_button)
        self._main_layout.addLayout(custom_folder_layout)

        self._init_buttons(has_cancel_button=True, ok_name="Playblast")
        self.buttons.rejected.connect(self.close)
        self.buttons.accepted.connect(self.do_export)
        self._main_layout.addWidget(self.buttons)

    @staticmethod
    def _click_checkbox(checkbox: QCheckBox) -> Callable[[], None]:
        def inner() -> None:
            checkbox.click()

        return inner

    @staticmethod
    def _set_checkboxes(
        checkboxes_index: Iterable[dict[str, QCheckBox]], loc: str, val: bool
    ) -> Callable[[], None]:
        def inner() -> None:
            for cbi in checkboxes_index:
                cbi[loc].setChecked(val)

        return inner

    @property
    def use_dof(self) -> bool:
        return self._use_dof.isChecked()

    @property
    def use_hardware_fog(self) -> bool:
        return self._use_hardware_fog.isChecked()

    @property
    def use_lighting(self) -> bool:
        return self._use_lighting.isChecked()

    @property
    def use_shadows(self) -> bool:
        return self._use_shadows.isChecked()

    @property
    def use_ssao(self) -> bool:
        return self._use_ssao.isChecked()

    def save_locations_to_paths(
        self, dialog_id: str, locs: Iterable[SaveLocation], filename: str
    ) -> dict[Playblaster.PRESET, list[str | Path]]:
        paths: dict[Playblaster.PRESET, list[str | Path]] = defaultdict(list)
        for loc in locs:
            if self.is_location_enabled(dialog_id, loc.name):
                paths[loc.preset].append(str(loc.path) + "/" + filename)

        return paths

    def _set_custom_folder(self) -> None:
        """Prompt user to select a custom folder for saving"""
        path_list = mc.fileDialog2(
            caption="Select a custom playblast folder",
            fileMode=2,
            hideNameEdit=True,
            okCaption="Select",
            setProjectBtnEnabled=False,
        )
        if path_list:
            path = path_list[0]
            self._custom_folder_text.setText(path)

    @abstractmethod
    def _generate_config(self) -> MPlayblastConfig:
        pass

    def is_shot_enabled(self, dialog_id: str) -> bool:
        """Takes an MShotDialogConfig id and returns if it's enabled"""
        return self._enabled_shot_cbs[dialog_id].isChecked()

    def is_location_enabled(self, dialog_id: str, loc_name: str) -> bool:
        return self._enabled_loc_cbs[dialog_id][loc_name].isChecked()

    def do_export(self):
        self.playblaster.configure(self._generate_config()).playblast()

        MessageDialog(self.parent(), "Playblast(s) successful!").exec_()
        self.close()


if TYPE_CHECKING:
    from typing import Any, Generator


log = logging.getLogger(__name__)

CACHE_SET = "cache_SET"
PROP_SET = "prop_SET"


class AnimPublisher(Publisher):
    _shot: Shot
    _timeline: Timeline
    _init_success: bool

    def __init__(self, headless: bool = False):
        super().__init__(use_sg_entity=False, headless=headless)
        try:
            shot_code = mc.fileInfo("code", query=True)[0]
            self._init_success = True
        except IndexError:
            mc.error("Could not find shot code in fileInfo! Cannot export shot.")
            if not self._is_headless:
                error = MessageDialog(
                    self._window,
                    "Error: could not detect shot code. Please reach out to Scott",
                )
                error.exec_()
            self._init_success = False

        self._shot = self._conn.get_shot_by_code(shot_code)
        self._timeline = Timeline.from_shot(self._shot, preroll_duration=55)

    def _set_origin_keyframes(self) -> None:
        with maintain_current_time():
            keyframed = [
                o
                for o in mc.ls(dagObjects=True, type="transform")
                if mc.keyframe(o, query=True)
            ]
            mc.currentTime(self._timeline.preroll + 4)
            mc.setKeyframe(*keyframed, insert=True)
            mc.currentTime(self._timeline.preroll)
            mc.xform(
                *keyframed,
                matrix=(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),  # type: ignore[arg-type]
            )
            mc.setKeyframe(*keyframed)

    def _prepublish(self) -> bool:
        if not self._init_success:
            return False

        self._set_origin_keyframes()

        cache_sets = mc.ls("::" + CACHE_SET, sets=True)
        prop_sets = mc.ls("::" + PROP_SET, sets=True)

        mc.select(*cache_sets, *prop_sets, replace=True)

        return True

    def _get_save_path(self) -> Path | None:
        if not self._shot.path:
            return None
        return get_production_path() / self._shot.path / "anim/usd/main.usd"

    def _presave(self) -> bool:
        return True

    def _get_mayausd_kwargs(self) -> dict[str, Any]:
        prop_sets = mc.ls("::" + PROP_SET, sets=True)
        props = dict()
        with maintain_selection():
            for s in prop_sets:
                mc.select(s)
                namespace = s.split(":")[0]
                props[namespace] = [n.split(":")[1] for n in mc.ls(selection=True)]

        return {
            "chaser": [ExportChaser.ID],
            "chaserArgs": [
                (ExportChaser.ID, "mode", ChaserMode.ANIM),
                (ExportChaser.ID, "props", json.dumps(props)),
                (ExportChaser.ID, "timeline", self._timeline.to_json()),
            ],
            "exportColorSets": False,
            "exportComponentTags": False,
            "exportUVs": False,
            "frameRange": (
                self._timeline.preroll,
                self._timeline.tail,
            ),
            "frameStride": 1.0 / self._shot.substeps,
            "shadingMode": "none",
            "stripNamespaces": False,
        }

    def _get_confirm_message(self):
        return f"Animation has been exported to {self._publish_path}"

    def _postpublish(self) -> None:
        """Launch a Houdini process to compute the anim post-process HDA"""
        post_anim_script = ";".join(
            [
                f"AnimPostProcessor().run('{self._shot.code}')",
                "exit()",
            ]
        )
        HoudiniDCC(is_python_shell=True, extra_args=["-c", post_anim_script]).launch()

        root_layer = Sdf.Layer.FindOrOpen(str(self._publish_path))
        root_layer.subLayerPaths.append("post-process.usd")
        root_layer.Save()

        # send CFX to farm
        job = author.Job()
        job.title = (
            f"CFX {self._shot.code} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        job.envkey = [
            generate_tractor_setenv(
                [
                    "OCIO",
                    "PATH",
                    "PIXAR_LICENSE_FILE",
                    "PXR_AR_DEFAULT_SEARCH_PATH",
                    "PXR_PLUGINPATH_NAME",
                    "RMANTREE",
                ]
            )
        ]
        job.priority = 90
        task = author.Task(title="cache")
        task.addCommand(
            author.Command(
                argv=[
                    "python",
                    str(get_pipe_path()),
                    "-l",
                    "DEBUG",
                    "-p",
                    "houdini",
                    "-c",
                    (f"CfxPostProcessor().run('{self._shot.code}');exit()"),
                ],
                maxrunsecs=3600,
                retryrc=[-11, 3, 139],
                service="EL9",
            )
        )
        job.addChild(task)
        job.spool(block=True)
        author.closeEngineClient()


def generate_tractor_setenv(parms: list[str]) -> str:
    return " ".join(
        ["setenv"]
        + [f"{var}={os.getenv(var)}" for var in parms if var]
        + ["HOUDINI_LICENSE_SERVER=animlic.cs.byu.edu"]
    )


@contextmanager
def maintain_current_time() -> Generator[int, None, None]:
    ctime = mc.currentTime(query=True)
    try:
        yield ctime
    finally:
        mc.currentTime(ctime)


if TYPE_CHECKING:
    from typing import Any, Sequence


try:
    from modelChecker.modelChecker_UI import UI as MCUI
except TypeError:
    # this external code throws errors when in headless mode
    MCUI = object

log = logging.getLogger(__name__)


class PublishAssetDialog(FilteredListDialog):
    _substance_only: QCheckBox

    def __init__(self, parent: QWidget | None, items: Sequence[str]) -> None:
        super().__init__(
            parent,
            items,
            "Publish Asset",
            "Select asset to publish",
            accept_button_name="Publish",
        )

        self._substance_only = QCheckBox(
            "Export Substance-only file? ONLY USE IF INSTRUCTED BY A LEAD"
        )
        self._layout.insertWidget(1, self._substance_only)

    @property
    def is_substance_only(self) -> bool:
        return self._substance_only.isChecked()


class AssetPublisher(Publisher):
    _override: bool

    def __init__(self) -> None:
        super().__init__(PublishAssetDialog)

    def _prepublish(self) -> bool:
        checker = ModelChecker.get()
        self._override = False
        if not checker.check_selected():
            checker_fail_dialog = MessageDialogCustomButtons(
                self._window,
                "Error. This asset did not pass the model checker. Please "
                "ensure your model meets the requirements set by the model "
                "checker.",
                "Cannot export: Model Checker",
                has_cancel_button=True,
                ok_name="Override",
                cancel_name="Ok",
            )
            self._override = bool(checker_fail_dialog.exec_())
            if not self._override:
                cursor = QTextCursor(checker.reportOutputUI.textCursor())
                cursor.setPosition(0)
                cursor.insertHtml(
                    "<h1>Asset not exported. Please resolve model checks.</h1>"
                )
                return False
        return True

    def _get_entity_list(self) -> list[str]:
        return self._conn.get_asset_name_list(sorted=True)

    def _get_entity_from_name(self, name: str) -> SGEntity | None:
        return self._conn.get_asset_by_name(name)

    def _get_save_path(self) -> Path | None:
        dialog = cast(PublishAssetDialog, self._dialog)
        asset = cast(Asset, self._entity)
        try:
            assert asset.path is not None
        except AssertionError:
            error = MessageDialog(
                self._window,
                "Error: No path for this Asset set in ShotGrid. Nothing exported",
                "Error",
            )
            error.exec_()
            return None

        return (
            get_production_path()
            / asset.path
            / (asset.name + ("_SUBSTANCE" if dialog.is_substance_only else "") + ".usd")
        )

    def _presave(self) -> bool:
        # notify webhook of override
        if self._override:
            asset = cast(Asset, self._entity)
            override_info = {
                "user": os.getlogin(),
                "asset": asset.disp_name,
                "path": str(self._publish_path),
            }
            data = bytes(json.dumps(override_info), encoding="utf-8")
            hashcheck = (
                "sha1=" + hmac.new(PIPEBOT_SECRET.encode(), data, sha1).hexdigest()
            )

            req = request.Request(
                url=PIPEBOT_URL + "/model_checker",
                data=data,
            )
            req.add_header("x-pipebot-signature", hashcheck)
            request.urlopen(req)
        return True

    def _get_mayausd_kwargs(self) -> dict[str, Any]:
        return {
            "shadingMode": "useRegistry",
        }


class ModelChecker(MCUI):
    @classmethod
    def get(cls):
        if not cls.qmwInstance or (type(cls.qmwInstance) is not cls):
            cls.qmwInstance = cls()
        return cls.qmwInstance

    def configure(self) -> None:
        self.uncheckAll()
        commands = [
            "crossBorder",
            "hardEdges",
            "lamina",
            "missingUVs",
            "ngons",
            "noneManifoldEdges",
            "onBorder",
            # "selfPenetratingUVs",
            "zeroAreaFaces",
            "zeroLengthEdges",
        ]
        for cmd in commands:
            self.commandCheckBox[cmd].setChecked(True)

    def check_selected(self) -> bool:
        self.configure()
        self.sanityCheck(["Selection"], True)
        self.createReport("Selection")

        # loop and show UI if anything had an error
        diagnostics = self.contexts["Selection"]["diagnostics"]
        for error in self.commandsList.keys():
            if (error in diagnostics) and len(self.parseErrors(diagnostics[error])):
                self.show_UI()
                return False

        return True

    # Override
    def sanityCheck(self, contextsUuids, refreshSelection=True) -> None:
        """The `sanityCheck` function cannot handle transforms that do not
        have children. This catches those errors and warns the modelers."""
        try:
            super().sanityCheck(contextsUuids, refreshSelection)
        except RuntimeError as err:
            if (
                "(kInvalidParameter): Object is incompatible with this method"
                in err.args
            ):
                MessageDialog(
                    self.parent(),
                    "The model checker could not run. Please ensure that you do "
                    "not have any empty transforms.",
                    "Model Checker Failed",
                ).exec_()
            else:
                raise err


if TYPE_CHECKING:
    from typing import Any, Sequence


log = logging.getLogger(__name__)


class PublishCameraDialog(FilteredListDialog):
    _camera: QComboBox

    def __init__(self, parent: QWidget | None, items: Sequence[str]) -> None:
        super().__init__(
            parent,
            items,
            "Publish Camera",
            "Select a shot to publish the camera for",
            accept_button_name="Publish",
        )

        self._camera = QComboBox(
            self,
        )
        cameras = mc.ls(cameras=True, visible=True)
        self._camera.addItems(cameras)
        self._camera.setCurrentText(cameras[0])
        validator = QRegExpValidator(QRegExp("|".join(cameras)))
        self._camera.setValidator(validator)

        camera_widget = QWidget()
        camera_layout = QHBoxLayout(camera_widget)
        camera_label = QLabel("Camera:")
        camera_layout.addWidget(camera_label, 1)
        camera_layout.addWidget(self._camera, 99)

        self._layout.insertWidget(0, camera_widget)


class CameraPublisher(Publisher):
    def __init__(self) -> None:
        super().__init__(PublishCameraDialog)

    def _get_entity_list(self) -> list[str]:
        return self._conn.get_shot_code_list(sorted=True)

    def _get_entity_from_name(self, name: str) -> SGEntity | None:
        return self._conn.get_shot_by_code(name)

    def _get_save_path(self) -> Path | None:
        try:
            assert self._entity.path is not None
        except AssertionError:
            error = MessageDialog(
                self._window,
                "Error: No path for this Shot set in ShotGrid. Nothing exported",
                "Error",
            )
            error.exec_()
            return None

        return get_production_path() / self._entity.path / "cam" / "cam.usd"

    def _presave(self) -> bool:
        mc.select(self._camera, replace=True)
        return True

    def _get_mayausd_kwargs(self) -> dict[str, Any]:
        shot = cast(Shot, self._entity)
        start = shot.cut_in - 5
        end = shot.cut_out + 5
        return {
            "chaser": [ExportChaser.ID],
            "chaserArgs": [(ExportChaser.ID, "mode", ChaserMode.CAM)],
            "frameRange": (start, end),
            "frameStride": 1.0 / shot.substeps,
        }

    def _get_confirm_message(self) -> str:
        return f"The camera has been exported to {self._publish_path}"

    @property
    def _camera(self) -> str:
        return cast(PublishCameraDialog, self._dialog)._camera.currentText()


if TYPE_CHECKING:
    from typing import Any

    from Qt.QtWidgets import QWidget

log = logging.getLogger(__name__)


class Publisher:
    """Class for publishing USDs out of Maya"""

    _conn: DB
    _dialog: FilteredListDialog
    _dialog_T: type[FilteredListDialog]
    _entity: SGEntity
    _is_headless: bool
    _publish_path: Path
    _selected_item: str
    _system: str
    _use_sg_entity: bool
    _window: QWidget | None

    def __init__(
        self,
        dialog: type[FilteredListDialog] | None = None,
        use_sg_entity: bool = True,
        headless: bool = False,
    ) -> None:
        self._conn = DB.Get(DB_Config)
        self._window = None if headless else get_main_qt_window()
        self._system = platform.system()
        self._dialog_T = dialog or FilteredListDialog
        self._use_sg_entity = use_sg_entity
        self._is_headless = headless

    @staticmethod
    def _assert_not_none(fun):
        @wraps(fun)
        def wrap(*args, **kwargs):
            result = fun(*args, **kwargs)
            if result is None:
                raise AssertionError
            return result

        return wrap

    def __init_subclass__(cls, *args, **kwargs) -> None:
        """Wrap overridden definitions of these methods"""
        super().__init_subclass__(*args, **kwargs)
        funcs = (cls._get_entity_from_name, cls._get_save_path)
        for f in funcs:
            setattr(cls, f.__name__, cls._assert_not_none(f))

    @property
    def _IS_WINDOWS(self) -> bool:
        return self._system == "Windows"

    def _prepublish(self) -> bool:
        """Runs before any other part of the publish function"""
        return True

    def _get_entity_list(self) -> list[str]:
        """Get a list of strings to prompt in the dialog"""
        return []

    @_assert_not_none
    def _get_entity_from_name(self, name: str) -> SGEntity | None:
        """Turn the string chosen in the dialog into a SG entity"""
        return None

    @_assert_not_none
    def _get_save_path(self) -> Path | None:
        """Get the save path"""
        if user_select := mc.fileDialog2(fileFilter="*.usd"):
            return Path(user_select[0])
        return None

    def _presave(self) -> bool:
        """Run before any files are saved out"""
        return True

    def _get_mayausd_kwargs(self) -> dict[str, Any]:
        """A dictionary of additional arguments to `mc.mayaUSDExport`"""
        return {}

    def _get_confirm_message(self) -> str:
        return f"The selected objects have been exported to {self._publish_path}"

    def publish(self):
        """Generic publishing function.
        `Exporter().publish()` will publish the selected geometry to the place
        chosen in the pop-up dialog, accounting for the USD export bug on
        Windows. Specific functionality is defined by passing a
        `FilteredListDialog` class into `__init__` and by overriding the
        following functions:
          - `prepublish(self)`
          - `get_entity_list(self) -> list[str]`
          - `get_entity_from_name(self, disp_name: str) -> SGEntity`
          - `get_save_path(self) -> Path`
          - `presave(self)`
          - `get_mayausd_kwargs(self) -> dict[str, Any]`
        """
        with maintain_selection():
            if not self._prepublish():
                return

            if entity_list := self._get_entity_list():
                # if there is a non-empty entity list, prompt the user with a dialog
                self._dialog = self._dialog_T(self._window, entity_list)
                if not self._dialog.exec_():
                    return

                self._selected_item = self._dialog.get_selected_item()

                if self._selected_item is None:
                    error = MessageDialog(
                        self._window,
                        "Error: Nothing selected. Nothing exported",
                        "Error",
                    )
                    error.exec_()
                    return

                # get the corresponding SGEntity object
                if self._use_sg_entity:
                    try:
                        self._entity = self._get_entity_from_name(self._selected_item)
                    except AssertionError:
                        error = MessageDialog(
                            self._window,
                            "Error: The selected item did not correspond to a valid "
                            f"{self._entity.__class__.__name__} in ShotGrid. Please "
                            "report this error. Nothing exported",
                            "Error",
                        )
                        error.exec_()
                        return
                    log.debug(self._entity)

            self._publish_path = self._get_save_path()
            if not self._publish_path:
                mc.error("No save path found!")
                return

            if not self._presave():
                return

            self._publish_path.parent.mkdir(parents=True, exist_ok=True)
            temp_publish_path = (
                os.getenv("TEMP", "") + os.pathsep + self._publish_path.name
            )

            kwargs = {
                "file": str(
                    temp_publish_path if self._IS_WINDOWS else self._publish_path
                ),
                "selection": True,
                "stripNamespaces": True,
                # "writeDefaults": True,
                **self._get_mayausd_kwargs(),
            }

            try:
                mc.mayaUSDExport(**kwargs)  # type: ignore[attr-defined]
            except Exception:
                print(traceback.format_exc())
                if not self._is_headless:
                    MessageDialog(
                        self._window,
                        "WARNING: Publish failed! Please check the console for more information",
                        "Export Failed",
                    ).exec_()
                return

            # if on Windows, work around this bug: https://github.com/PixarAnimationStudios/OpenUSD/issues/849
            # TODO: check if this is still needed in Maya 2026
            if self._IS_WINDOWS:
                shutil.move(temp_publish_path, self._publish_path)

            self._postpublish()

            print("Export Complete")
            if not self._is_headless:
                confirm = MessageDialog(
                    self._window,
                    self._get_confirm_message(),
                    "Export Complete",
                )
                confirm.exec_()

    def _postpublish(self) -> None:
        pass


if TYPE_CHECKING:
    from typing import Any


log = logging.getLogger(__name__)

CACHE_SET = "cache_SET"
PROP_SET = "prop_SET"


class RigPublisher(Publisher):
    def __init__(self) -> None:
        super().__init__(use_sg_entity=False)

    def _get_entity_list(self) -> list[str]:
        cache_sets = mc.ls("::" + CACHE_SET, sets=True)
        return [s.split(":")[0] for s in cache_sets]

    def _get_mayausd_kwargs(self) -> dict[str, Any]:
        kwargs = {
            "chaser": [ExportChaser.ID],
            "chaserArgs": [(ExportChaser.ID, "mode", ChaserMode.CHAR)],
            "exportCollectionBasedBindings": True,
            "exportMaterialCollections": True,
            "legacyMaterialScope": True,
            "materialCollectionsPath": "/ROOT/MODEL",
            "shadingMode": "useRegistry",
        }

        return kwargs

    def _presave(self) -> bool:
        mc.select(self._selected_item + ":" + CACHE_SET)
        return True


if TYPE_CHECKING:
    from typing import Any, Callable, Iterable, Protocol

    class TimeSampleble(Protocol):
        def GetTimeSamples(self) -> list[float]: ...

        def GetNumTimeSamples(self) -> int: ...


class ChaserMode(IntEnum):
    ANIM = 1
    CAM = 2
    CHAR = 3


def get_frames_from_attr(attr: TimeSampleble) -> Iterable[Usd.TimeCode]:
    return (
        (Usd.TimeCode(f) for f in attr.GetTimeSamples())
        if attr.GetNumTimeSamples()
        else (Usd.TimeCode.Default(),)
    )


def create_or_clear_layer(path: str) -> Sdf.Layer:
    layer = Sdf.Layer.FindOrOpen(path)
    if layer:
        layer.Clear()
    else:
        layer = Sdf.Layer.CreateNew(path)
    return layer


def scale_down_geo(stage: Usd.Stage, scale_factor: float = 0.01) -> None:
    """Recurse through the stage and scale down all Mesh and BasisCurves prims by
    `scale_factor`"""

    root_prim = stage.GetPseudoRoot()
    data: Any

    for prim in (it := iter(Usd.PrimRange(root_prim))):
        extent = prim.GetAttribute(UsdGeom.Tokens.extent)
        if extent.IsValid():
            for frame in get_frames_from_attr(extent):
                data = np.array(extent.Get(frame))
                data *= scale_factor
                extent.Set(Vt.Vec3fArray.FromNumpy(data), frame)  # type: ignore[arg-type]

        xformable = UsdGeom.Xformable(prim)
        xformop: UsdGeom.XformOp
        for xformop in xformable.GetOrderedXformOps():
            xform_type = UsdGeom.XformOp.GetOpTypeToken(xformop.GetOpType())

            if (not xformop.IsDefined()) or xformop.IsInverseOp():
                continue

            if xform_type == UsdGeom.XformOpTypes.translate:
                for frame in get_frames_from_attr(xformop):
                    data: Gf.Vec3d = xformop.Get(frame)  # type: ignore[no-redef]
                    data *= scale_factor
                    xformop.Set(data, frame)

            elif xform_type == UsdGeom.XformOpTypes.transform:
                for frame in get_frames_from_attr(xformop):
                    data: Gf.Matrix4d = xformop.GetOpTransform(frame)  # type: ignore[no-redef]
                    translate = data.ExtractTranslation()
                    translate *= scale_factor
                    data.SetTranslateOnly(translate)
                    xformop.Set(data, frame)

        if not (prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.BasisCurves)):  # type: ignore[call-overload]
            continue

        # don't recurse deeper than this
        it.PruneChildren()

        for attr_token in (UsdGeom.Tokens.points,):
            attr = prim.GetAttribute(attr_token)
            if not attr.IsValid():
                continue

            for frame in get_frames_from_attr(attr):
                data = np.array(attr.Get(frame))
                data *= scale_factor
                attr.Set(Vt.Vec3fArray.FromNumpy(data), frame)  # type: ignore[arg-type]

    UsdGeom.SetStageMetersPerUnit(
        stage, UsdGeom.GetStageMetersPerUnit(stage) / scale_factor
    )


TOPOLOGY_ATTRIBS = (
    UsdGeom.Tokens.cornerIndices,
    UsdGeom.Tokens.cornerSharpnesses,
    UsdGeom.Tokens.creaseIndices,
    UsdGeom.Tokens.creaseLengths,
    UsdGeom.Tokens.creaseSharpnesses,
    UsdGeom.Tokens.faceVaryingLinearInterpolation,
    UsdGeom.Tokens.faceVertexCounts,
    UsdGeom.Tokens.faceVertexIndices,
    UsdGeom.Tokens.holeIndices,
    UsdGeom.Tokens.interpolateBoundary,
    UsdGeom.Tokens.triangleSubdivisionRule,
)


def make_topo_attrs_default(stage: Usd.Stage) -> None:
    root_prim = stage.GetPseudoRoot()
    for prim in (it := iter(Usd.PrimRange(root_prim))):
        if not (prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.BasisCurves)):  # type: ignore[call-overload]
            continue

        # don't recurse deeper than this
        it.PruneChildren()

        for attr_token in TOPOLOGY_ATTRIBS:
            attr = prim.GetAttribute(attr_token)
            if not attr.IsValid():
                continue
            data = attr.Get(1)
            if data:
                attr.Clear()
                attr.Set(data, Usd.TimeCode.Default())


def update_material_bindings(
    stage: Usd.Stage, old: str, new: str, name_prepend: str = ""
) -> None:
    """Update material bindings to what Houdini will expect"""

    bindings = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath(Sdf.Path(new)))
    for rel in bindings.GetCollectionBindingRels():
        t1, t2 = rel.GetTargets()
        # strip the namespace because the USD exporter strips the geo namespace but not the material namespace
        new_name = t2.name.split("_", 1)[1]
        # Change the material binding to match how it will look in Houdini
        rel.SetTargets(
            (
                t1,
                Sdf.Path(
                    f"{str(t2.GetParentPath()).replace(old, new)}/{name_prepend}{new_name}"
                ),
            )
        )


def move_prim(
    layer: Sdf.Layer, prim_to_move: Sdf.Path, new_prim_parent: Sdf.Path
) -> None:
    with Sdf.ChangeBlock():
        old_prim_parent = prim_to_move.GetParentPath()
        if old_prim_parent != new_prim_parent:
            prim_spec = Sdf.CreatePrimInLayer(layer, new_prim_parent)
            prim_spec.SetInfo(prim_spec.SpecifierKey, Sdf.SpecifierDef)

            edit = Sdf.BatchNamespaceEdit()
            edit.Add(Sdf.NamespaceEdit.Reparent(prim_to_move, new_prim_parent, -1))
            edit.Add(Sdf.NamespaceEdit.Remove(old_prim_parent.GetPrefixes()[0]))

            if not layer.Apply(edit):
                raise Exception("Failed to apply layer edit!")


def find_and_move_prim(
    layer: Sdf.Layer, prim_to_find: str, new_prim_parent: Sdf.Path
) -> None:
    """Searches for the prim with name `prim_to_find` and moves it underneath
    `new_prim_parent`. *Assumes only 1 prim with the given name*"""
    # TODO: will work in Usd v24?
    # editor = Usd.NamespaceEditor(self._stage)
    # editor.MovePrimAtPath(Sdf.Path("/WORLD/CAM/LnD_shotCam"), Sdf.Path("/"))
    # editor.ApplyEdits()

    prim_search: list[Sdf.Path] = []

    def traverse_kernel(path: Sdf.Path | str):
        if isinstance(path, str):
            path = Sdf.Path(path)
        if path.IsPrimPath():
            if path.name == prim_to_find:
                prim_search.append(path)

    layer.Traverse(Sdf.Path("/"), traverse_kernel)

    try:
        prim_to_move = prim_search.pop()
    except IndexError:
        raise RuntimeError(f"Could not find {prim_to_find} in export!")

    move_prim(layer, prim_to_move, new_prim_parent)


def remove_namespace(layer: Sdf.Layer, root: Sdf.Path = Sdf.Path("/")) -> bool:
    edit = Sdf.BatchNamespaceEdit()

    def traverse_kernel(path: Sdf.Path | str):
        if isinstance(path, str):
            path = Sdf.Path(path)
        if path.IsPrimPath():
            try:
                edit.Add(Sdf.NamespaceEdit.Rename(path, path.name.split("_", 1)[1]))
            except IndexError:
                print(f"Namespace not changed for {str(path)}")

    layer.Traverse(root, traverse_kernel)
    return layer.Apply(edit)


def split_by_namespace(stage: Usd.Stage, suffix: str) -> dict[str, Sdf.Layer]:
    root_layer = stage.GetRootLayer()
    root_layer_path = Path(root_layer.realPath)
    stage.SetEditTarget(root_layer)

    child_names = stage.GetPseudoRoot().GetChildrenNames()
    namespaces: set[str] = set()
    for n in child_names:
        namespace, item = n.split("_", 1)
        if item.startswith("S_"):  # static props
            remove_namespace(root_layer, Sdf.Path("/" + n))
            remove_namespace(root_layer, Sdf.Path("/" + item))
            s, namespace, _ = item.split("_", 2)
        namespaces.add(namespace)

    child_names = stage.GetPseudoRoot().GetChildrenNames()
    layers: dict[str, Sdf.Layer] = dict()
    for namespace in namespaces:
        layer_name = namespace.lower()
        layer_path = str(root_layer_path.parent / f"{layer_name}.{suffix}.usd")
        layer = create_or_clear_layer(layer_path)
        layer.TransferContent(root_layer)

        children_to_keep = [c for c in child_names if c.startswith(namespace + "_")]
        edit = Sdf.BatchNamespaceEdit()
        for child in child_names:
            if child not in children_to_keep:
                edit.Add(Sdf.NamespaceEdit.Remove("/" + child))

        layer.Apply(edit)
        if not remove_namespace(layer):
            raise RuntimeError(f"Could not remove namespace on layer `{layer_name}`")

        layer.Save()
        layers.update({layer_name: layer})

    # clear out root layer
    edit = Sdf.BatchNamespaceEdit()
    for child in child_names:
        edit.Add(Sdf.NamespaceEdit.Remove("/" + child))
    root_layer.Apply(edit)
    root_layer.Save()

    return layers


def float_range_compare_factory(
    keep_start: float | None, keep_end: float | None
) -> Callable[[float], bool]:
    def check_start(val: float) -> bool:
        return isclose(val, keep_start, rel_tol=1e-4) or (keep_start < val)  # type: ignore[arg-type, operator]

    def check_end(val: float) -> bool:
        return isclose(val, keep_end, rel_tol=1e-4) or (val < keep_end)  # type: ignore[arg-type, operator]

    def check_both(val: float) -> bool:
        return check_start(val) and check_end(val)

    if (keep_start is not None) and (keep_end is not None):
        return check_both
    elif keep_start is not None:
        return check_start
    elif keep_end is not None:
        return check_end
    else:
        raise ValueError("Must provide keep_start or keep_end")


def timesample_erase_kernel_factory(
    layer: Sdf.Layer, *, keep_start: float | None = None, keep_end: float | None = None
) -> Callable[[Sdf.Path | str], None]:
    """Returns a layer traversal kernel that erases time samples not between
    keep_start and keep_end
    NOTE: assume that all time samples are in this layer"""

    def kernel(path: Sdf.Path | str) -> None:
        if isinstance(path, str):
            path = Sdf.Path(path)
        if not path.IsPrimPropertyPath():
            return
        attr_spec = layer.GetAttributeAtPath(path)
        if not attr_spec.variability == Sdf.VariabilityVarying:
            return

        start = (
            layer.GetBracketingTimeSamplesForPath(path, keep_start)[0]
            if keep_start
            else None
        )
        end = (
            layer.GetBracketingTimeSamplesForPath(path, keep_end)[1]
            if keep_end
            else None
        )
        cmp = float_range_compare_factory(start, end)
        for ts in layer.ListTimeSamplesForPath(path):
            if cmp(ts):
                continue
            layer.EraseTimeSample(path, ts)

        if keep_start:
            layer.startTimeCode = keep_start
        if keep_end:
            layer.endTimeCode = keep_end

    return kernel


def split_preroll(
    anim_layer: Sdf.Layer, name: str, prim_path: Sdf.Path, tl: Timeline
) -> Sdf.Layer:
    """Split anim and preroll data into separate files, then stitch them together
    with Value Clips"""
    preroll_layer_path = str(Path(anim_layer.realPath).parent / f"{name}.preroll.usd")
    preroll_layer = create_or_clear_layer(preroll_layer_path)
    preroll_layer.TransferContent(anim_layer)

    preroll_layer.Traverse(
        preroll_layer.pseudoRoot.path,
        timesample_erase_kernel_factory(preroll_layer, keep_end=(tl.head - 1)),
    )
    preroll_layer.Save()

    anim_layer.Traverse(
        anim_layer.pseudoRoot.path,
        timesample_erase_kernel_factory(anim_layer, keep_start=tl.head),
    )
    anim_layer.Save()

    stitched_layer_path = str(Path(anim_layer.realPath).parent / f"{name}.usd")
    stiched_layer = create_or_clear_layer(stitched_layer_path)
    stiched_layer.TransferContent(anim_layer)

    timesample_files = [preroll_layer.realPath, anim_layer.realPath]
    topology_layer = create_or_clear_layer(
        UsdUtils.GenerateClipTopologyName(stiched_layer.resolvedPath)
    )
    manifest_layer = create_or_clear_layer(
        UsdUtils.GenerateClipManifestName(stiched_layer.realPath)
    )
    UsdUtils.StitchClipsTopology(topology_layer, timesample_files)
    UsdUtils.StitchClipsManifest(
        manifest_layer, topology_layer, timesample_files, prim_path
    )
    UsdUtils.StitchClips(
        stiched_layer, timesample_files, prim_path, tl.preroll, tl.end, False
    )
    stiched_layer.Save()

    return stiched_layer


@attrs.define
class ChaserArgs:
    mode: ChaserMode = attrs.field(converter=int)
    timeline: Optional[Timeline] = attrs.field(
        default=None,
        kw_only=True,
        converter=lambda t: Timeline.from_json(t) if t else None,
    )
    props: Optional[dict[str, list[str]]] = attrs.field(
        default=None,
        kw_only=True,
        converter=lambda p: json.loads(p) if p else None,
    )


class ExportChaser(mayaUsdLib.ExportChaser):
    ID: str = "lnd"

    _chaser_args: ChaserArgs
    _dag_to_usd: mayaUsdLib.DagToUsdMap
    _stage: Usd.Stage

    def __init__(self, factoryContext, *args, **kwargs) -> None:
        super(ExportChaser, self).__init__(factoryContext, *args, **kwargs)

        self._dag_to_usd = factoryContext.GetDagToUsdMap()
        self._stage = factoryContext.GetStage()
        self.job_args = factoryContext.GetJobArgs()
        self._chaser_args = ChaserArgs(**self.job_args.allChaserArgs[self.ID])

    @log_errors
    def PostExport(self) -> bool:
        if self._chaser_args.mode == ChaserMode.ANIM:
            assert self._chaser_args.props is not None
            assert self._chaser_args.timeline is not None

            scale_down_geo(self._stage)
            make_topo_attrs_default(self._stage)
            layers = split_by_namespace(self._stage, "anim")

            root_layer = self._stage.GetRootLayer()
            root_layer_path = Path(root_layer.realPath)

            conn = DB.Get(DB_Config)

            for name, layer in layers.items():
                print(name)

                # the rigs that need the controls exported instead of the mesh
                if name in [
                    "gemheart",
                    "raydenring",
                    "ringroom",
                    "robinring",
                    "rrbrickdoor",
                    "statueringpillar",
                    "strikemagicpillarpath",
                ]:
                    character_root_path = Sdf.Path("/ROOT/CTRLS")
                else:
                    character_root_path = Sdf.Path("/ROOT/MODEL")

                stitched_layer = split_preroll(
                    layer, name, character_root_path, self._chaser_args.timeline
                )

                char_prim_spec = Sdf.CreatePrimInLayer(
                    root_layer, Sdf.Path(f"/__class__/character/{name}")
                )
                char_prim_spec.specifier = Sdf.SpecifierOver

                reference = Sdf.Reference(
                    f"./{Path(stitched_layer.realPath).relative_to(root_layer_path.parent)}",
                    character_root_path,
                )

                char_prim_spec.referenceList.appendedItems = [reference]

                try:
                    asset = conn.get_asset_by_attr("name", name)
                    assert asset.path is not None
                    rig_path = f"{asset.path}/usd/main.usd"
                    walk_up_len = (
                        len(root_layer_path.relative_to(get_production_path()).parts)
                        - 1
                    )
                    root_layer.subLayerPaths.append("../" * walk_up_len + rig_path)
                except Exception:
                    print(f"Warning! Could not find asset matching namespace {name}")

        elif self._chaser_args.mode == ChaserMode.CHAR:
            scale_down_geo(self._stage)
            update_material_bindings(self._stage, "/ROOT", "/ROOT/MODEL", "MAT_")

        elif self._chaser_args.mode == ChaserMode.CAM:
            # We don't scale down the camera here because we need to import it
            # back into Maya. Instead we'll scale it down when we import it into
            # Solaris.

            new_shotCam_path = Sdf.Path("/LnD_shotCam")
            find_and_move_prim(
                self._stage.GetEditTarget().GetLayer(), "world_CTRL", new_shotCam_path
            )
            self._stage.SetDefaultPrim(self._stage.GetPrimAtPath(new_shotCam_path))
        else:
            raise ValueError(
                f"{self._chaser_args.mode} is not a valid LnD chaser mode."
            )

        return True


log = logging.getLogger(__name__)


class MAnimShotFileManager(MShotFileManager):
    @classmethod
    def run_on_open(cls):
        super().run_on_open()

        # Duplicate the USD camera into a temp Maya camera
        CAM_NAME = "shotCam"
        try:
            mc.mayaUsdDiscardEdits(CAM_NAME)
        except RuntimeError:
            pass
        finally:
            camera_prim = next(
                prim
                for prim in cls.get_stage().Traverse(Usd.PrimIsDefined)
                if prim.IsA(UsdGeom.Camera) and prim.GetName() == CAM_NAME
            )
            mc.mayaUsdEditAsMaya(
                cls.get_stage_shape() + "," + str(camera_prim.GetPrimPath())
            )
            camera_shape = mc.listRelatives(CAM_NAME, fullPath=True, shapes=True)[0]
            mc.lookThru(CAM_NAME)
            mc.camera(camera_shape, edit=True, lockTransform=True)

    def _get_subpath(self) -> str:
        return "anim"

    def _setup_scene(self) -> None:
        self._import_camera()
        self._import_env()

        # Import Rigs
        for asset_stub in self.shot.assets:
            asset = self._conn.get_asset_by_stub(asset_stub)
            if not asset.path:
                continue
            rig_folder = get_production_path() / asset.path / "rig"
            rig_list = sorted(list(rig_folder.glob("rig*.mb")))
            try:
                rig_path = rig_list.pop()
                if rig_path.exists():
                    mc.file(str(rig_path), reference=True, namespace=asset.name)
                else:
                    raise FileNotFoundError

            except (FileNotFoundError, IndexError):
                print(f'Unable to find rig for asset "{asset.disp_name}"')

    def _setup_file(self, path: Path, entity) -> None:
        mc.file(newFile=True, force=True)
        super()._setup_file(path, entity)


log = logging.getLogger(__name__)


class MRLOShotFileManager(MShotFileManager):
    def __init__(self):
        super().__init__(version_glob="{}*.{}", version_msg="Open alt version")

    def _check_unsaved_changes(self) -> bool:
        return True

    def _get_subpath(self) -> str:
        return "rlo"

    def _setup_scene(self) -> None:
        self._import_env()

    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        if not path.exists():
            prompt_create = MessageDialogCustomButtons(
                self._main_window,
                f"The RLO file for shot {entity.code} does not exist. Continue "
                "to save a copy of the current file as the RLO file?",
                has_cancel_button=True,
                ok_name="Continue",
                cancel_name="Cancel",
            )
            if not bool(prompt_create.exec_()):
                return
        super()._setup_file(path, entity)


log = logging.getLogger(__name__)


class MShotFileManager(FileManager):
    MAYA_OVERRIDE = "maya_override.usd"
    shot: Shot

    def __init__(self, **kwargs) -> None:
        conn = DB.Get(DB_Config)
        window = get_main_qt_window()
        super().__init__(conn, Shot, window, versioning=True, **kwargs)

    @classmethod
    def get_stage_shape(cls) -> str:
        if ss := mc.ls(type="mayaUsdProxyShape", long=True)[0]:
            return ss
        raise RuntimeError("No USD stage found in scene")

    @classmethod
    def get_stage(cls) -> Usd.Stage:
        return mayaUsd.ufe.getStage(cls.get_stage_shape())

    @classmethod
    @log_errors
    def run_on_open(cls) -> None:
        """Function to run on file open via script node"""

        # save edit target layer on save
        beforeSaveId = om.MSceneMessage.addCallback(
            om.MSceneMessage.kBeforeSave,
            lambda _: MShotFileManager.get_stage().GetEditTarget().GetLayer().Save(),
        )

        # remove callback before opening a new file
        om.MSceneMessage.addCallback(
            om.MSceneMessage.kBeforeOpen,
            lambda kwargs: om.MSceneMessage.removeCallback(kwargs["ID"]),
            {"ID": beforeSaveId},
        )

        # change default render resolution
        mc.setAttr("defaultResolution.width", 1920)  # type: ignore[arg-type]
        mc.setAttr("defaultResolution.height", 816)  # type: ignore[arg-type]
        mc.setAttr("defaultResolution.pixelAspect", 1.0)  # type: ignore[arg-type]
        mc.setAttr("defaultResolution.deviceAspectRatio", 1920 / 816)  # type: ignore[arg-type]

        # set session USD target layer to the override layer
        try:
            shot_code = ""
            try:
                shot_code = mc.fileInfo("code", query=True)[0]
            except IndexError:
                mc.error(
                    "Could not find shot code in fileInfo! USD edit target not set"
                )
            if shot_code:
                mc.mayaUsdEditTarget(  # type: ignore[attr-defined]
                    cls.get_stage_shape(),
                    edit=True,
                    editTarget="/".join(["shot", shot_code, "set", cls.MAYA_OVERRIDE]),
                )

                conn = DB.Get(DB_Config)
                shot = conn.get_shot_by_code(shot_code)

                # Import Timeline
                frames, colors, comments = shot_timeline_generator(
                    shot.cut_duration, shot.cut_in
                )
                TimelineMarker.clear()
                TimelineMarker.set(frames, colors, comments)
                mc.playbackOptions(
                    animationStartTime=frames[0],
                    animationEndTime=frames[-1],
                    minTime=frames[0],
                    maxTime=frames[-1],
                )
        except Exception:
            mc.error("Warning! Could not set edit target!")

    def _check_unsaved_changes(self) -> bool:
        if mc.file(query=True, modified=True):
            warning_response = mc.confirmDialog(
                title="Do you want to save?",
                message="The current file has not been saved. Continue anyways?",
                button=["Continue", "Cancel"],
                defaultButton="Cancel",
                cancelButton="Cancel",
                dismissString="Cancel",
            )
            if warning_response == "Cancel":
                return False
        return True

    def _generate_filename_ext(self, entity) -> tuple[str, str]:
        shot = cast(Shot, entity)
        return shot.code, "mb"

    def _open_file(self, path: Path) -> None:
        mc.file(str(path), open=True, force=True)

    def _post_open_file(self, entity: SGEntity) -> None:
        """create `lndOnOpen` script node"""
        ON_OPEN_SCRIPT = "lndOnOpen"

        if mc.objExists(ON_OPEN_SCRIPT):
            return

        classname = self.__class__.__name__
        mc.scriptNode(
            beforeScript=f"{classname}.{self.__class__.run_on_open.__name__}()",
            name=ON_OPEN_SCRIPT,
            scriptType=1,
            sourceType="python",
        )
        # script node is created, will not run this session, so run manually
        self.run_on_open()

    def _import_camera(self) -> None:
        assert self.shot.path is not None
        root_layer = self.get_stage().GetRootLayer()

        # mc.mayaUsdLayerEditor(cam_layer.identifier, edit=True, lockLayer=(2, 0, stageShape))

        cam_file_layer = Sdf.Layer.FindOrOpenRelativeToLayer(
            root_layer, "/".join((self.shot.path, "cam", "cam.usd"))
        )
        if not cam_file_layer:
            mc.warning("No exported camera found")
            return

        if cam_file_layer.identifier not in root_layer.subLayerPaths:  # type: ignore[operator]
            root_layer.subLayerPaths.append(cam_file_layer.identifier)

    def _import_env(self) -> None:
        assert self.shot.path is not None
        stage = self.get_stage()
        root_layer = stage.GetRootLayer()
        # locked_layers: list[str] = []

        ## Fix env scale
        stage.SetEditTarget(Usd.EditTarget(root_layer))
        env_prim = stage.OverridePrim(Sdf.Path("/environment"))
        env_xformable = UsdGeom.Xformable(env_prim)
        env_xformable.ClearXformOpOrder()
        env_scale_op = env_xformable.AddScaleOp()
        env_scale_op.Set((100, 100, 100))

        # Set up shot-level overrides
        env_override_layer = Sdf.Layer.FindOrOpenRelativeToLayer(
            root_layer,
            "/".join((self.shot.path, "set", MShotFileManager.MAYA_OVERRIDE)),
        ) or Sdf.Layer.CreateNew(
            str(
                get_production_path()
                / self.shot.path
                / "set"
                / MShotFileManager.MAYA_OVERRIDE
            )
        )
        env_override_layer.Save()

        if env_override_layer.identifier not in root_layer.subLayerPaths:  # type: ignore[operator]
            root_layer.subLayerPaths.append(env_override_layer.identifier)

        ## Fix env scale
        # env_prim = stage.OverridePrim(Sdf.Path("/environment"))
        # env_xformable = UsdGeom.Xformable(env_prim)
        # env_xformable.GetScaleOp().Set((100, 100, 100))

        stage.SetEditTarget(Usd.EditTarget(env_override_layer))

        if not (env_stub := self.shot.set):
            if not self.shot.sequence:
                env_stub = None
            else:
                env_stub = self._conn.get_sequence_by_stub(self.shot.sequence).set

        if env_stub and (env := self._conn.get_env_by_stub(env_stub)) and env.path:
            env_file_layer = Sdf.Layer.FindOrOpenRelativeToLayer(
                root_layer, "/".join((env.path, "main.usd"))
            )
            if env_file_layer.identifier not in root_layer.subLayerPaths:  # type: ignore[operator]
                root_layer.subLayerPaths.append(env_file_layer.identifier)
            # locked_layers.append(env_file_layer.identifier)
            env_file_layer.SetPermissionToSave(False)

        # for id in locked_layers:
        #     mc.mayaUsdLayerEditor(id, edit=True, lockLayer=(2, 0, stageShape))

    @abstractmethod
    def _setup_scene(self) -> None:
        pass

    def _setup_file(self, path: Path, entity) -> None:
        mc.file(rename=str(path))

        self.shot = cast(Shot, entity)
        assert self.shot.path is not None

        # Create USD Stage
        transform = mc.createNode("transform", name="stage_transform")
        mc.createNode("mayaUsdProxyShape", name="stage", parent=transform)
        stage_shape = self.get_stage_shape()
        mc.connectAttr("time1.outTime", f"{stage_shape}.time")

        ROOT_LAYER = "maya_root.usd"
        root_layer_path = str(get_production_path() / self.shot.path / ROOT_LAYER)
        root_layer = Sdf.Layer.FindOrOpen(root_layer_path) or Sdf.Layer.CreateNew(
            root_layer_path
        )
        root_layer.Save()
        mc.setAttr(f"{stage_shape}.filePath", "../" + ROOT_LAYER, type="string")

        # mc.mayaUsdLayerEditor(str(get_production_path() / "root.usda"), edit=True, lockLayer=(2, 0, stage_shape))

        # Set up stage
        self._setup_scene()
        root_layer.Save()
        root_layer.SetPermissionToSave(False)

        # Save USD Edits to the scene file and don't prompt about it
        mc.optionVar(intValue=("mayaUsd_SerializedUsdEditsLocationPrompt", 0))
        mc.optionVar(intValue=("mayaUsd_SerializedUsdEditsLocation", 2))

        # Save shot code to file
        mc.fileInfo("code", self.shot.code)
        mc.file(save=True, force=True)


if TYPE_CHECKING:
    import typing

    RT = typing.TypeVar("RT")  # return type


lib_path = resolve_mapped_path(Path(__file__).parents[1] / "lib")
log = logging.getLogger(__name__)


@dataclass
class TexSetExportSettings:
    tex_set: sp.textureset.TextureSet
    extra_channels: set[sp.textureset.Channel]
    resolution: int
    displacement_source: DisplacementSource
    normal_type: NormalType
    normal_source: NormalSource


class Exporter:
    """Class to manage exporting and converting textures"""

    _asset: Asset
    _conn: DB
    _out_path: Path
    _preview_path: Path
    _src_path: Path
    _tex_path: Path

    def __init__(self) -> None:
        self._conn = DB.Get(DB_Config)
        id = sp.project.Metadata("LnD").get("asset_id")
        assert (a := self._conn.get_asset_by_id(id)) is not None
        self._asset = a

    def _init_paths(self, mat_var: str) -> None:
        # initialize paths, pulling from SG database
        assert self._asset.tex_path is not None
        base_path = get_production_path() / self._asset.tex_path / "variants" / mat_var

        self._out_path = resolve_mapped_path(base_path)
        self._src_path = self._out_path / "src"
        self._tex_path = self._out_path / "tex"
        self._preview_path = self._out_path / "preview"

        # create paths if not exist
        self._src_path.mkdir(parents=True, exist_ok=True)
        self._tex_path.mkdir(parents=True, exist_ok=True)
        self._preview_path.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        exp_setting_arr: typing.Sequence[TexSetExportSettings],
        mat_var: str,
    ) -> bool:
        """Export all the textures of the given Texture Sets"""
        self._init_paths(mat_var)

        try:
            [tss.tex_set.get_stack() for tss in exp_setting_arr]
        except ValueError:
            MessageDialog(
                get_main_qt_window(),
                "Warning! Exporter could not get stack! You are doing something cool with material layering. Please show this to Scott so he can fix it.",
            ).exec_()
            return False

        config = Exporter._generate_config(self._src_path, exp_setting_arr)
        log.debug(config)

        export_result: sp.export.TextureExportResult
        try:
            export_result = sp.export.export_project_textures(config)
        except Exception as e:
            print(e)
            return False

        self.write_mat_info(exp_setting_arr)

        tex_converter = TexConverter(
            self._tex_path, self._preview_path, export_result.textures.values()
        )

        try:
            tex_converter.convert_tex()
            tex_converter.convert_previewsurface()
        except TexConversionError:
            MessageDialog(
                get_main_qt_window(),
                (
                    "Warning! Not all textures were converted! Make sure to "
                    'stop rendering this asset in Houdini and press "Reset '
                    'RenderMan RIS/XPU".'
                ),
            ).exec_()
            return False

        return True

    def write_mat_info(
        self, export_settings_arr: typing.Iterable[TexSetExportSettings]
    ) -> bool:
        """Write out JSON file with information about the texturesets"""
        mat_info_path = self._out_path / "mat.json"
        old_mat_info: MaterialInfo
        if mat_info_path.exists():
            with open(mat_info_path, "r") as f:
                old_mat_info = MaterialInfo.from_json(f.read())
        else:
            old_mat_info = MaterialInfo()

        all_tex_sets = [ts.name() for ts in sp.textureset.all_texture_sets()]
        for tex_set in list(old_mat_info.tex_sets.keys()):
            if tex_set not in all_tex_sets:
                del old_mat_info.tex_sets[tex_set]

        new_mat_info = MaterialInfo(
            {
                **old_mat_info.tex_sets,
                **{
                    export_settings.tex_set.name(): TexSetInfo(
                        displacement_source=export_settings.displacement_source,
                        has_udims=export_settings.tex_set.has_uv_tiles(),
                        normal_source=export_settings.normal_source,
                        normal_type=export_settings.normal_type,
                    )
                    for export_settings in export_settings_arr
                },
            }
        )
        with open(str(self._out_path / "mat.json"), "w", encoding="utf-8") as f:
            f.write(new_mat_info.to_json())
        return True

    @staticmethod
    def _generate_config(
        asset_path: Path, export_settings_arr: typing.Iterable[TexSetExportSettings]
    ) -> dict:
        return {
            "exportPath": str(asset_path),
            "exportShaderParams": True,
            "exportPresets": [
                {
                    "name": export_settings.tex_set.name(),
                    "maps": [
                        # Default RenderMan maps
                        *Exporter._shader_maps(export_settings),
                        # Extra AOVs
                        *[
                            {
                                "fileName": f"$textureSet_{getattr(ch, 'label', None) and ch.label().replace(' ', '') or ch.type().name}(_$colorSpace)(.$udim)",
                                "channels": [
                                    {
                                        "destChannel": color,
                                        "srcChannel": color,
                                        "srcMapType": "documentMap",
                                        "srcMapName": ch.type().name.lower(),
                                    }
                                    for color in colors
                                ],
                                "parameters": {
                                    "bitDepth": bit_depth.lower(),
                                    "fileFormat": "png",
                                    "sizeLog2": export_settings.resolution,
                                },
                            }
                            for ch in export_settings.extra_channels
                            for colors, bit_depth in re.findall(
                                r"^s?(L|RGB)(\d{1,2}F?)$",
                                export_settings.tex_set.get_stack()
                                .get_channel(ch.type())
                                .format()
                                .name,
                            )
                        ],
                        # Preview Surface
                        *Exporter._preview_surface_maps(),
                    ],
                }
                for export_settings in export_settings_arr
            ],
            "exportList": [
                {
                    "rootPath": str(export_settings.tex_set.get_stack()),
                    "exportPreset": export_settings.tex_set.name(),
                }
                for export_settings in export_settings_arr
            ],
            "exportParameters": [
                {
                    "parameters": {
                        "dithering": False,
                        "paddingAlgorithm": "color",
                        "dilationDistance": 24,
                    }
                }
            ],
        }

    @staticmethod
    def _shader_maps(export_settings: TexSetExportSettings) -> list:
        maps = [
            {
                "fileName": "$textureSet_BaseColor(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": ch,
                        "srcChannel": ch,
                        "srcMapType": "documentMap",
                        "srcMapName": "baseColor",
                    }
                    for ch in "RGB"
                ],
                "parameters": {
                    "bitDepth": "16",
                    "fileFormat": "png",
                    "sizeLog2": export_settings.resolution,
                },
            },
            {
                "fileName": "$textureSet_Metallic(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": "L",
                        "srcChannel": "L",
                        "srcMapType": "documentMap",
                        "srcMapName": "metallic",
                    },
                ],
                "parameters": {
                    "bitDepth": "8",
                    "fileFormat": "png",
                    "sizeLog2": export_settings.resolution,
                },
            },
            {
                "fileName": "$textureSet_IOR(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": "L",
                        "srcChannel": "L",
                        "srcMapType": "documentMap",
                        "srcMapName": "specular",
                    },
                ],
                "parameters": {
                    "bitDepth": "8",
                    "fileFormat": "png",
                    "sizeLog2": export_settings.resolution,
                },
            },
            {
                "fileName": "$textureSet_SpecularRoughness(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": "L",
                        "srcChannel": "L",
                        "srcMapType": "documentMap",
                        "srcMapName": "roughness",
                    },
                ],
                "parameters": {
                    "bitDepth": "8",
                    "fileFormat": "png",
                    "sizeLog2": export_settings.resolution,
                },
            },
            {
                "fileName": "$textureSet_Emissive(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": ch,
                        "srcChannel": ch,
                        "srcMapType": "documentMap",
                        "srcMapName": "emissive",
                    }
                    for ch in "RGB"
                ],
                "parameters": {
                    "bitDepth": "16",
                    "fileFormat": "png",
                    "sizeLog2": export_settings.resolution,
                },
            },
            {
                "fileName": "$textureSet_Presence(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": "L",
                        "srcChannel": "L",
                        "srcMapType": "documentMap",
                        "srcMapName": "opacity",
                    },
                ],
                "parameters": {
                    "bitDepth": "8",
                    "fileFormat": "png",
                    "sizeLog2": export_settings.resolution,
                },
            },
            {
                "fileName": f"$textureSet_Normal(_$colorSpace)(.$udim){'.pre-b2r' if export_settings.normal_type == NormalType.BUMP_ROUGHNESS else ''}",
                "channels": [
                    {
                        "destChannel": ch,
                        "srcChannel": ch,
                        **(
                            {
                                "srcMapType": "virtualMap",
                                "srcMapName": "Normal_OpenGL",
                            }
                            if export_settings.normal_source
                            is NormalSource.NORMAL_HEIGHT
                            else {
                                "srcMapType": "documentMap",
                                "srcMapName": "normal",
                            }
                        ),
                    }
                    for ch in "RGB"
                ],
                "parameters": {
                    **(
                        {
                            "bitDepth": "16f",
                            "fileFormat": "exr",
                        }
                        if export_settings.normal_type is NormalType.BUMP_ROUGHNESS
                        else {
                            "bitDepth": "16",
                            "fileFormat": "png",
                        }
                    ),
                    "sizeLog2": export_settings.resolution,
                },
            },
        ]

        if export_settings.displacement_source is not DisplacementSource.NONE:
            maps += [
                {
                    "fileName": "$textureSet_Displacement(_$colorSpace)(.$udim)",
                    "channels": [
                        {
                            "destChannel": "L",
                            "srcChannel": "L",
                            "srcMapType": "documentMap",
                            "srcMapName": (
                                "height"
                                if export_settings.displacement_source
                                == DisplacementSource.HEIGHT
                                else "displacement"
                            ),
                        },
                    ],
                    "parameters": {
                        "bitDepth": "16",
                        "fileFormat": "png",
                        "sizeLog2": export_settings.resolution,
                    },
                }
            ]

        return maps

    @staticmethod
    def _preview_surface_maps() -> list:
        return [
            {
                "fileName": "$textureSet_DiffuseColor(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": ch,
                        "srcChannel": ch,
                        "srcMapType": "documentMap",
                        "srcMapName": "baseColor",
                    }
                    for ch in "RGB"
                ],
                "parameters": {
                    "bitDepth": "8",
                    "dithering": True,
                    "fileFormat": "jpeg",
                },
            },
            {
                "fileName": "$textureSet_ORM(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": "R",
                        "srcChannel": "R",
                        "srcMapType": "documentMap",
                        "srcMapName": "opacity",
                    },
                    {
                        "destChannel": "G",
                        "srcChannel": "G",
                        "srcMapType": "documentMap",
                        "srcMapName": "roughness",
                    },
                    {
                        "destChannel": "B",
                        "srcChannel": "B",
                        "srcMapType": "documentMap",
                        "srcMapName": "metallic",
                    },
                ],
                "parameters": {
                    "bitDepth": "8",
                    "fileFormat": "jpeg",
                },
            },
            {
                "fileName": "$textureSet_Emissive(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": ch,
                        "srcChannel": ch,
                        "srcMapType": "documentMap",
                        "srcMapName": "emissive",
                    }
                    for ch in "RGB"
                ],
                "parameters": {
                    "bitDepth": "8",
                    "dithering": True,
                    "fileFormat": "jpeg",
                },
            },
            {
                "fileName": "$textureSet_NormalDX(_$colorSpace)(.$udim)",
                "channels": [
                    {
                        "destChannel": ch,
                        "srcChannel": ch,
                        "srcMapType": "virtualMap",
                        "srcMapName": "Normal_DirectX",
                    }
                    for ch in "RGB"
                ],
                "parameters": {
                    "bitDepth": "8",
                    "fileFormat": "jpeg",
                },
            },
        ]


class MetadataUpdater:
    _conn: DB

    def __init__(self) -> None:
        self._conn = DB.Get(DB_Config)

    def check(self) -> bool:
        data = sp.project.Metadata("LnD")
        return data.get("asset_id") in self._conn.get_asset_attr_list("id")

    def prompt_update(self) -> bool:
        if self.check():
            return True

        update = MessageDialog(
            get_main_qt_window(),
            "It looks like this file is not associated with an asset in ShotGrid. Would you like to associate it now?",
            "Associate Asset with ShotGrid?",
            has_cancel_button=True,
        ).exec_()

        if not update:
            MessageDialog(
                get_main_qt_window(),
                "Warning! You will need to associate this asset with ShotGrid before exporting textures.",
                "No asset selected",
            ).exec_()
            return False

        return self.do_update()

    def do_update(self) -> bool:
        fld = FilteredListDialog(
            get_main_qt_window(),
            self._conn.get_asset_name_list(sorted=True),
            "Associate Asset with ShotGrid",
            "Select an asset to associate this Substance Painter file with",
            accept_button_name="Associate",
        )
        if not fld.exec_():
            return False
        item = fld.get_selected_item()

        if item is None:
            MessageDialog(
                get_main_qt_window(),
                "Warning! No asset selected, you will need to associate this asset with ShotGrid before exporting.",
                "No asset selected",
            ).exec_()
            return False

        asset = self._conn.get_asset_by_name(item)
        assert asset is not None
        data = sp.project.Metadata("LnD")
        data.set("asset_id", asset.id)

        MessageDialog(
            get_main_qt_window(),
            f"Successfully associated with asset {asset.disp_name} in ShotGrid!",
            "Success",
        ).exec_()
        return True


def reload_pipe() -> None:
    sp_plugins = [
        spp.plugins["export"],
        spp.plugins["shelf"],
    ]
    _reload_pipe(sp_plugins)

    for plugin in sp_plugins:
        plugin.close_plugin()
        plugin.start_plugin()


if TYPE_CHECKING:
    import typing


log = logging.getLogger(__name__)


class SubstanceExportWindow(QMainWindow, ButtonPair):
    _asset: Asset
    _central_widget: QtWidgets.QWidget
    _conn: DB
    _main_layout: QLayout
    _mat_var_dropdown: QComboBox
    # _mat_var_enabled: QtWidgets.QCheckBox
    _metadataManager: MetadataUpdater
    _srgbChecker: sRGBChecker
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
        self.buttons.accepted.connect(self.do_export)
        self._main_layout.addWidget(self.buttons)

    def _preflight(self) -> bool:
        """Check for asset metadata and correct channel types before running
        the export"""
        metaUpdater = MetadataUpdater()
        srgbChecker = sRGBChecker()
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
            checkbox_callback_helper(self._enabled_checkbox, settings_container)
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


if TYPE_CHECKING:
    import typing

    RT = typing.TypeVar("RT")  # return type


log = logging.getLogger(__name__)


class TexConversionError(ChildProcessError):
    pass


class TexConverter:
    tex_path: Path
    preview_path: Path
    imgs_by_tex_set: typing.Iterable[list[str]]

    def __init__(
        self,
        tex_path: Path,
        preview_path: Path,
        imgs_by_tex_set: typing.Iterable[list[str]],
    ) -> None:
        self.tex_path = tex_path
        self.preview_path = preview_path
        self.imgs_by_tex_set = imgs_by_tex_set

    def convert_tex(self) -> list[Path]:
        """Convert all .png textures in the most recent export to .tex"""

        assert self.tex_path is not None

        # Remove any corrupted tex files from a previous export
        for file in self.tex_path.iterdir():
            if file.name.endswith(".temp.tex"):
                file.unlink()

        @self._debug_out
        def tex_cmd(img: str, is_color: bool = False) -> list[str]:
            # currently using oiiotool so txmake doesn't freak out at the color space
            # TODO: switch back to txmake for color in R26
            # fmt: off
            return [
                str(Executables.oiiotool),
                img,
                *(
                    [
                        "--colorconvert", "ACEScg", "srgb-ap1",
                        "-d", "uint8",
                        "--dither",
                    ] if is_color else []
                ),
                "--compression", "lzw" if is_color else "lossless",
                "--planarconfig", "separate",
                "-otex:fileformatname=tx:wrap=clamp:resize=1:prman_options=1",
                f"{str(self.tex_path / Path(img).stem.replace('ACEScg', 'srgb-ap1'))}.tex",
            ]
            # fmt: on

        @self._debug_out
        def b2r_cmd(img: str) -> list[str]:
            # fmt: off
            return [
                str(Executables.txmake),
                "-resize", "round-",
                "-mode", "periodic",
                "-filter", "box",
                "-mipfilter", "box",
                "-bumprough", "2", "0", "0", "0", "0", "1",
                "-newer",
                img,
                f"{str(self.tex_path / Path(img).stem)}.b2r",
            ]
            # fmt: on

        @self._debug_out
        def norm2height(img: str) -> list[str]:
            """Convert normal map to height map
            This is necessary because if we run b2r conversion directly on a
            normal map, reversed UV tiles will have incorrect normals.
            We can't run b2r conversion directly on the height map from
            Substance because that doesn't include normal painting or
            stickers. Thus, the remaining option is to convert the Normal map
            from Substance back into a height map."""
            img_dims = [str(int(log2(int(d)))) for d in self._img_dims(img)]
            # fmt: off
            return [
                str(Executables.sbsrender),
                "render",
                "--engine", "d3d11pc",
                "--exr-format-compression", "zip",
                "--output-bit-depth", "16f",
                "--output-format", "exr",
                "--input", f"{os.getenv('PIPE_PATH', '')}/lib/sbs/normal2height.sbsar",
                "--set-entry", f"input@{img}",
                "--set-value", f"$outputsize@{','.join(img_dims)}",
                "--output-path", str(Path(img).parent),
                "--output-name", img.replace(".pre-b2r", ""),
            ]
            # fmt: on

        pre_cmdlines: list[list[str]] = []
        cmdlines: list[list[str]] = []
        for imgs in self.imgs_by_tex_set:
            log.debug(imgs)
            for img in imgs:
                if img.endswith(".jpeg"):
                    continue
                log.debug(f"        {img}")
                if "pre-b2r" in img:
                    pre_cmdlines.append(norm2height(img))
                    cmdlines.append(b2r_cmd(img.replace(".pre-b2r", "")))
                else:
                    cmdlines.append(tex_cmd(img, ("Color" in img or "Emissive" in img)))

        self._wait_and_check_cmds(pre_cmdlines, skip_check=True)
        finished_imgs = self._wait_and_check_cmds(cmdlines)

        if len(finished_imgs) != len(cmdlines):
            raise TexConversionError("Not all png textures were converted")

        return finished_imgs

    def convert_previewsurface(self) -> list[Path]:
        """Compile all .jpeg textures in the most recent export to UDIM-less tiles"""

        assert self.preview_path is not None

        @self._debug_out
        def jpeg_cmd(root: Path, imgs: typing.Sequence[str]) -> list[str]:
            dimx, dimy = self._img_dims(imgs[0])

            img_name = re.search(r"^(.*_)(.+)$", root.name)
            assert img_name is not None
            name_base, color_space = img_name.group(1, 2)

            count = len(imgs)
            grid_height = int(floor(sqrt(count)))
            grid_base = int(grid_height + ceil(count / grid_height - grid_height))

            # fmt: off
            return [
                str(Executables.oiiotool),
                *imgs,
                "--mosaic", f"{grid_base}x{grid_height}",
                "--resize", f"{dimx}x{dimy}",
                "-o", f"{str(self.preview_path / name_base)}{'sRGB' if color_space == 'sRGB-Texture' else 'Linear'}.jpeg",
            ]
            # fmt: on

        # construct list of grouped images
        img_list: dict[str, list[str]] = {}
        for imgs in self.imgs_by_tex_set:
            for img in imgs:
                if img.endswith(".jpeg"):
                    key_search = re.search(r"^(.*)\.\d{4}\.jpeg$", img)
                    if not key_search:  # no UDIMs
                        key_search = re.search(r"^(.*)\.jpeg$", img)
                        assert key_search is not None

                    key = key_search.group(1)
                    if key not in img_list:
                        img_list[key] = []
                    img_list[key].append(img)

        cmdlines = [
            jpeg_cmd(Path(root), sorted(imgs)) for root, imgs in img_list.items()
        ]

        finished_imgs = self._wait_and_check_cmds(cmdlines)

        if len(finished_imgs) != len(cmdlines):
            raise TexConversionError("Not all jpeg textures were converted")

        return finished_imgs

    @staticmethod
    def _img_dims(img: str) -> tuple[str, str]:
        img_info = subprocess.check_output(
            [
                str(Executables.oiiotool),
                "--info",
                img,
            ],
            startupinfo=silent_startupinfo(),
        ).decode("utf-8")
        img_dims = re.search(r"^.* : +(\d+) +x +(\d+), .*$", img_info)

        assert img_dims is not None
        matches = img_dims.group(1, 2)
        return (matches[0], matches[1])

    @staticmethod
    def _wait_and_check_cmds(
        cmds: typing.Sequence[list[str]], batch_size: int = 18, skip_check: bool = False
    ) -> list[Path]:
        """Wait for list of processes to finish and print them to the debug log"""

        batched_cmds = (
            cmds[i : i + batch_size] for i in range(0, len(cmds), batch_size)
        )

        finished_imgs: list[Path] = []

        while batch := next(batched_cmds, None):
            start_time = time.time()

            procs = [
                subprocess.Popen(
                    cmd,
                    env=os.environ,
                    startupinfo=silent_startupinfo(),
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                )
                for cmd in batch
            ]

            for p in procs:
                p.wait()
                if log.isEnabledFor(logging.DEBUG):
                    if p.stdout and (stdout := p.stdout.read().decode("utf-8")):
                        log.debug(stdout)
                    if p.stderr and (stderr := p.stderr.read().decode("utf-8")):
                        log.debug(stderr)

                if skip_check:
                    continue

                img = Path(cast(str, p.args[-1]))  # type: ignore[index]

                # check file has been touched recently
                if start_time < img.stat().st_mtime:
                    log.debug(f"Successfully converted {img}")
                    finished_imgs.append(img)

        return finished_imgs

    def _debug_out(self, func: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
        """Decorator to debug print the output of the function"""

        def inner(self: TexConverter, *args, **kwargs) -> RT:
            ret = func(self, *args, **kwargs)
            log.debug(ret)
            return ret

        return inner


if TYPE_CHECKING:
    from types import ModuleType
    from typing import Any, Callable, Sequence

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


log = logging.getLogger(__name__)


class OpenFileDialog(FilteredListDialog):
    _version_cb: QtWidgets.QCheckBox | None

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        items: list[str],
        entity_type: type[SGEntity],
        versioning: bool,
        version_msg: str,
    ) -> None:
        super().__init__(
            parent,
            items,
            f"Open {entity_type.__name__} File",
            f"Select the {entity_type.__name__} file that you'd like to open.",
            accept_button_name="Open",
        )

        if versioning:
            self._version_cb = QtWidgets.QCheckBox(version_msg)
            self._layout.insertWidget(1, self._version_cb)
        else:
            self._version_cb = None

    @property
    def open_old_file(self) -> bool:
        if self._version_cb:
            return self._version_cb.isChecked()
        return False


class FileManager(metaclass=ABCMeta):
    _conn: DBInterface
    _entity_type: type[SGEntity]
    _main_window: QtWidgets.QWidget | None
    _versioning: bool
    _version_glob: str
    _version_msg: str
    _override_entity_code: str | None

    def __init__(
        self,
        conn: DBInterface,
        entity_type: type[SGEntity],
        main_window: QtWidgets.QWidget | None,
        *,
        versioning: bool = False,
        version_glob: str = "{}.*.{}",
        version_msg: str = "Open older version",
        override_entity_code: str | None = None,
    ) -> None:
        self._conn = conn
        self._entity_type = entity_type
        self._main_window = main_window
        self._versioning = versioning
        self._version_glob = version_glob
        self._version_msg = version_msg
        self._override_entity_code = override_entity_code

    @abstractmethod
    def _check_unsaved_changes(self) -> bool:
        pass

    @abstractmethod
    def _generate_filename_ext(self, entity: SGEntity) -> tuple[str, str]:
        pass

    def _get_subpath(self) -> str:
        return ""

    @abstractmethod
    def _open_file(self, path: Path) -> None:
        """Opens the file into the current session"""
        pass

    @abstractmethod
    def _setup_file(self, path: Path, entity: SGEntity) -> None:
        """Setup a new file in the current session"""
        pass

    def _post_open_file(self, entity: SGEntity) -> None:
        """Execute additional code after opening or creating a scene"""
        pass

    def _prompt_create_if_not_exist(self, path: Path) -> bool:
        """Returns True if safe to proceed, False otherwise"""
        if not path.exists():
            if not self._override_entity_code:
                prompt_create = MessageDialogCustomButtons(
                    self._main_window,
                    f"{str(path)} does not exist. Create?",
                    has_cancel_button=True,
                    ok_name="Create Folder",
                    cancel_name="Cancel",
                )
                if not bool(prompt_create.exec_()):
                    return False
            path.mkdir(mode=0o770, parents=True)
        return True

    def open_file(self) -> None:
        if not self._check_unsaved_changes():
            return
        if not self._override_entity_code:
            entity_names = self._conn.get_entity_code_list(
                self._entity_type,
                sorted=True,
                child_mode=DBInterface.ChildQueryMode.ROOTS,
            )
            open_file_dialog = OpenFileDialog(
                self._main_window,
                entity_names,
                self._entity_type,
                versioning=self._versioning,
                version_msg=self._version_msg,
            )

            if not open_file_dialog.exec_():
                log.debug("error intializing dialog")
                return

            response = open_file_dialog.get_selected_item()
        else:
            response = self._override_entity_code

        if not response:
            return

        entity = self._conn.get_entity_by_code(self._entity_type, response)

        try:
            assert entity is not None
            assert entity.path is not None
        except AssertionError:
            MessageDialog(
                self._main_window,
                f"The {self._entity_type.__name__.lower()} you are trying to "
                "load does not have a path set in ShotGrid.",
                "Error: No path set",
            ).exec_()
            return

        entity_path = get_production_path() / entity.path / self._get_subpath()
        if not self._prompt_create_if_not_exist(entity_path):
            return

        filename, ext = self._generate_filename_ext(entity)
        file_path = entity_path / f"{filename}.{ext}"

        if self._versioning:
            files = [file_path] + sorted(
                entity_path.glob(self._version_glob.format(filename, ext))
            )

            # prompt the user for which version to open
            if (not self._override_entity_code) and open_file_dialog.open_old_file:
                version_file_dialog = FilteredListDialog(
                    self._main_window,
                    [file.name for file in files],
                    "Choose a version",
                    "Select the version filename to open",
                    accept_button_name="Select",
                )
                if not version_file_dialog.exec_():
                    log.debug("error initializing version dialog")
                    return

                version = version_file_dialog.get_selected_item()
                if not version:
                    return
                file_path = entity_path / version

            # otherwise get the alphabetically last file
            else:
                file_path = files.pop()

        if file_path.is_file():
            self._open_file(file_path)
        else:
            self._setup_file(file_path, entity)

        self._post_open_file(entity)


class CascadingComboBox(QtWidgets.QWidget):
    def __init__(self):
        super(CascadingComboBox, self).__init__()
        self.setWindowTitle("L&D Import Render Layers!!")
        self.setGeometry(100, 100, 800, 600)

        # Mode tracking: "renders" for render folders, "layers" for render layers.
        self.current_mode = "renders"
        self.current_render = None

        # Use a random sentence for the title label.
        random_sentences = [
            "What's the best kind of music to listen to when fishing? Something catchy.",
            "How did the pirate get his ship for so cheap? It was on sail.",
            "Why do dads take an extra pair of socks when they play golf? In case they get a hole in one.",
            "As the dog said when the train ran over his tail --It won't be long now.",
            "What comes once in a minute, twice in a moment but never in a thousand years? The letter M.",
            "What's the best kind of bird to work for a construction company? A crane.",
            "It is awfully hard work doing nothing. I don't mind working hard if I don't have to do anything.",
            "What did the T-Rex use to cut wood? A dino-saw.",
            "A gentleman is someone who can play the accordion, but doesn't.",
            "So what if I can't spell Aarghmageddon, it's not like it's the end of the world.",
            "I only know 25 letters of the alphabet. I don't know y.",
            "What has five toes and isn't your foot? My foot.",
            "Why do bees have sticky hair? Because they use a honeycomb.",
            "I can tolerate algebra, maybe even a little calculus, but geometry is where I draw the line.",
        ]
        self.title_label = QtWidgets.QLabel(random.choice(random_sentences), self)
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)

        self.tool_button = QtWidgets.QToolButton(self)
        self.tool_button.setText("Select Shot")
        self.tool_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.menu = QtWidgets.QMenu(self)
        self.tool_button.setMenu(self.menu)

        all_shots = self.get_shots()
        categorized_data = self.categorize_data(all_shots)
        self.populate_cascading_menu(categorized_data)

        # Derive default shot from the Nuke root name.
        self.default_shot = os.path.basename(nuke.Root().name())[:-3]
        if not re.match(r"^[A-Za-z]_", self.default_shot):
            self.default_shot = "A_010"

        self.current_shot_label = QtWidgets.QLabel(
            f"Selected Shot: {self.default_shot}", self
        )
        self.current_shot_label.setAlignment(QtCore.Qt.AlignLeft)

        self.instructions = QtWidgets.QLabel(
            "Select the render you want the camera for:", self
        )
        instructions_font = QtGui.QFont()
        instructions_font.setPointSize(10)
        self.instructions.setFont(instructions_font)
        self.instructions.setAlignment(QtCore.Qt.AlignCenter)

        self.thumbnail_list = QtWidgets.QListWidget(self)
        self.thumbnail_list.setViewMode(QtWidgets.QListWidget.ListMode)
        self.thumbnail_list.setIconSize(QtCore.QSize(60, 60))
        self.thumbnail_list.setResizeMode(QtWidgets.QListWidget.Adjust)
        self.thumbnail_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )

        self.update_renders(self.default_shot)

        self.action_button = QtWidgets.QPushButton("Import Camera", self)
        self.action_button.clicked.connect(self.import_camera)

        self.back_button = QtWidgets.QPushButton("Back", self)
        self.back_button.clicked.connect(self.go_back)
        self.back_button.hide()

        self.cancel_button = QtWidgets.QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.close)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.back_button)
        button_layout.addWidget(self.action_button)
        button_layout.addWidget(self.cancel_button)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(self.title_label)
        main_layout.addWidget(self.tool_button)
        main_layout.addWidget(self.current_shot_label)
        main_layout.addWidget(self.instructions)
        main_layout.addWidget(self.thumbnail_list)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def get_shots(self):
        try:
            conn = DB.Get(DB_Config)
            return conn.get_shot_code_list()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to fetch shots: {e}")
            return []

    def import_camera(self):
        selected_items = self.thumbnail_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(
                self,
                "No Selection",
                "Please select a render folder to import the camera from.",
            )
            return

        item = selected_items[0]
        widget = self.thumbnail_list.itemWidget(item)
        render_folder = widget.layout().itemAt(0).widget().text()

        base_path = "/groups/dungeons/production/shot"
        render_dir = os.path.join(base_path, self.default_shot, "render", render_folder)

        camera_path = ""
        # 1. Check for the 'beauty' folder first.
        beauty_path = os.path.join(render_dir, "beauty", "render.usd")
        if os.path.exists(beauty_path):
            camera_path = beauty_path
        else:
            # 2. Check subfolders (ignoring .backup and beauty) for render.usd.
            for subfolder_name in os.listdir(render_dir):
                if subfolder_name.lower() in [".backup", "beauty"]:
                    continue
                subfolder_path = os.path.join(render_dir, subfolder_name)
                if os.path.isdir(subfolder_path):
                    candidate = os.path.join(subfolder_path, "render.usd")
                    if os.path.exists(candidate):
                        camera_path = candidate
                        break

        # 3. If still not found, check if render.usd exists directly in render_dir.
        if not camera_path:
            candidate = os.path.join(render_dir, "render.usd")
            if os.path.exists(candidate):
                camera_path = candidate

        if not camera_path:
            QtWidgets.QMessageBox.warning(
                self,
                "File Not Found",
                f"Could not find a valid render.usd in the expected locations:\n{render_dir}",
            )
            return

        try:
            cam = nuke.createNode("Camera3")
            cam["read_from_file"].setValue(True)
            cam["file"].setValue(camera_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Import Failed", f"Could not import camera:\n{e}"
            )

        self.close()

    def categorize_data(self, all_shots):
        categorized_data = {"Other": []}
        for item in all_shots:
            if len(item) > 1 and item[0].isalpha() and item[1] == "_":
                category = item.split("_")[0]
                categorized_data.setdefault(category, []).append(item)
            else:
                categorized_data["Other"].append(item)
        for key in categorized_data:
            categorized_data[key] = sorted(categorized_data[key])
        sorted_categories = {
            k: categorized_data[k] for k in sorted(categorized_data) if k != "Other"
        }
        if "Other" in categorized_data:
            sorted_categories["Other"] = categorized_data["Other"]
        return sorted_categories

    def populate_cascading_menu(self, categorized_data):
        for category, items in categorized_data.items():
            if category != "Other":
                submenu = self.menu.addMenu(f"{category} Sequence")
                for shot in items:
                    action = submenu.addAction(shot)
                    action.triggered.connect(partial(self.on_shot_selected, shot))
            else:
                other_menu = self.menu.addMenu("Other")
                for shot in items:
                    action = other_menu.addAction(shot)
                    action.triggered.connect(partial(self.on_shot_selected, shot))

    def on_shot_selected(self, shot):
        self.tool_button.setText(shot)
        self.current_shot_label.setText(f"Current Shot: {shot}")
        self.default_shot = shot

        self.current_mode = "renders"
        self.current_render = None
        self.thumbnail_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self.action_button.setText("Select Render")
        self.back_button.hide()
        self.update_renders(shot)

    def update_renders(self, shot_num):
        self.thumbnail_list.clear()
        base_path = "/groups/dungeons/production/shot"
        shot_path = os.path.join(base_path, shot_num, "render")
        items_list = []

        if os.path.exists(shot_path):
            for folder_name in os.listdir(shot_path):
                if folder_name.lower() == ".backup":
                    continue
                folder_path = os.path.join(shot_path, folder_name)
                if os.path.isdir(folder_path):
                    images_folder_path = os.path.join(folder_path, "images")
                    try:
                        file_times = [
                            os.path.getmtime(os.path.join(images_folder_path, f))
                            for f in os.listdir(images_folder_path)
                            if f.lower().endswith((".png", ".jpg", ".jpeg", ".exr"))
                        ]
                        creation_time = (
                            min(file_times)
                            if file_times
                            else os.path.getmtime(folder_path)
                        )
                    except Exception:
                        creation_time = os.path.getmtime(folder_path)

                    # Build a custom widget for the list item.
                    item = QtWidgets.QListWidgetItem()
                    widget = QtWidgets.QWidget()
                    layout = QtWidgets.QHBoxLayout()
                    layout.setContentsMargins(10, 4, 10, 4)

                    name_label = QtWidgets.QLabel(folder_name)
                    name_label.setAlignment(
                        QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
                    )
                    creation_date = time.strftime(
                        "%m-%d-%Y", time.localtime(creation_time)
                    )
                    date_label = QtWidgets.QLabel(creation_date)
                    date_label.setAlignment(
                        QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
                    )

                    layout.addWidget(name_label)
                    layout.addStretch()
                    layout.addWidget(date_label)
                    widget.setLayout(layout)
                    item.setSizeHint(widget.sizeHint())

                    items_list.append((creation_time, item, widget))

        # Add items sorted by creation time (newest first).
        items_list.sort(key=lambda x: x[0], reverse=True)
        for _, item, widget in items_list:
            self.thumbnail_list.addItem(item)
            self.thumbnail_list.setItemWidget(item, widget)

    def load_layers(self):
        selected_items = self.thumbnail_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Please select a render folder."
            )
            return

        item = selected_items[0]
        widget = self.thumbnail_list.itemWidget(item)
        render_folder = widget.layout().itemAt(0).widget().text()
        self.current_render = render_folder

        base_path = "/groups/dungeons/production/shot"
        shot_path = os.path.join(base_path, self.default_shot, "render", render_folder)
        self.thumbnail_list.clear()

        if os.path.exists(shot_path):
            layer_items = []
            self.thumbnail_list.setSelectionMode(
                QtWidgets.QAbstractItemView.ExtendedSelection
            )

            for layer_name in os.listdir(shot_path):
                if layer_name.lower() == ".backup":
                    continue

            for item in layer_items:
                self.thumbnail_list.addItem(item)

            self.current_mode = "layers"
            self.action_button.setText("Import Layers")
            self.back_button.show()
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing Folder",
                f"The render folder '{render_folder}' does not exist.",
            )

    def go_back(self):
        self.current_mode = "renders"
        self.current_render = None
        self.thumbnail_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self.action_button.setText("Select Render")
        self.back_button.hide()
        self.update_renders(self.default_shot)

    def import_layers(self):
        selected_items = self.thumbnail_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(
                self,
                "No Selection",
                "Please select at least one render layer to import.",
            )
            return

        base_path = "/groups/dungeons/production/shot"
        for item in selected_items:
            layer_folder = item.text()
            images_dn_path = os.path.join(
                base_path,
                self.default_shot,
                "render",
                self.current_render,
                layer_folder,
                "images_dn",
            )

            if os.path.exists(images_dn_path):
                exr_files = [
                    f for f in os.listdir(images_dn_path) if f.lower().endswith(".exr")
                ]
                if exr_files:
                    try:
                        exr_files.sort(
                            key=lambda x: int(os.path.splitext(x)[0].split(".")[-1])
                        )
                    except Exception as e:
                        print("Error sorting EXR files:", e)

                    first_frame = int(os.path.splitext(exr_files[0])[0].split(".")[-1])
                    last_frame = int(os.path.splitext(exr_files[-1])[0].split(".")[-1])
                    sequence_path = os.path.join(images_dn_path, "####.exr")
                    read = nuke.createNode("Read", f"file {{{sequence_path}}}")
                    read["first"].setValue(first_frame)
                    read["last"].setValue(last_frame)
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Missing Sequence",
                        f"No EXR files found in {images_dn_path}",
                    )
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Missing Folder",
                    f"The folder '{images_dn_path}' does not exist.",
                )
        self.close()


def show_simple_window():
    global simple_window  # Prevent garbage collection
    simple_window = CascadingComboBox()
    simple_window.show()


def run():
    show_simple_window()


# run()


project_file = nuke.root()["name"].value()


def make_text_nodes():
    # Text Padding
    rl_padding = 25
    tb_padding = 25
    font_size = 25
    frame_height = 816
    frame_width = 1920

    # Frame Number
    frame_num_text = nuke.createNode("Text2", "font_size 30")
    frame_num_text.knob("font_size").setValue(font_size)
    frame_num_text.knob("box").setValue(
        [rl_padding, tb_padding, frame_width - rl_padding, frame_height - tb_padding]
    )
    frame_num_text.knob("xjustify").setValue("right")
    frame_num_text.knob("yjustify").setValue("bottom")
    frame_num_text.knob("enable_background").setValue(1)
    frame_num_text.setName("Frame_Number")
    # message set below to force the font size to update

    # Department
    department_text = nuke.createNode("Text2")
    department_text.knob("font_size").setValue(font_size)
    department_text.knob("box").setValue(
        [
            rl_padding,
            tb_padding * 2 + font_size * 3,
            frame_width - rl_padding,
            frame_height,
        ]
    )
    department_text.knob("xjustify").setValue("left")
    department_text.knob("yjustify").setValue("bottom")
    department_text.knob("enable_background").setValue(1)
    department_text.setName("department_text")
    dropdown_knob = nuke.Enumeration_Knob(
        "departmentDropdown", "departmentDropdown", ["Lighting", "Compositing"]
    )
    department_text.addKnob(dropdown_knob)
    # message set below to force the font size to update

    # Shot Code
    shot_code_text = nuke.createNode("Text2")
    shot_code_text.knob("font_size").setValue(font_size)
    shot_code_text.knob("box").setValue(
        [rl_padding, tb_padding + font_size * 2, frame_width - rl_padding, frame_height]
    )
    shot_code_text.knob("xjustify").setValue("right")
    shot_code_text.knob("yjustify").setValue("bottom")
    shot_code_text.knob("enable_background").setValue(1)
    shot_code_text.setName("Shot_Code")
    # message set below to force the font size to update

    # date
    date_text = nuke.createNode("Text2")
    date_text.knob("font_size").setValue(font_size)
    date_text.knob("box").setValue(
        [rl_padding, tb_padding + font_size * 2, frame_width - rl_padding, frame_height]
    )
    date_text.knob("xjustify").setValue("left")
    date_text.knob("yjustify").setValue("bottom")
    date_text.knob("enable_background").setValue(1)
    date_text.setName("date")
    # message set below to force the font size to update

    # user name
    name_text = nuke.createNode("Text2")
    name_text.knob("font_size").setValue(font_size)
    name_text.knob("box").setValue(
        [rl_padding, tb_padding, frame_width - rl_padding, frame_height - tb_padding]
    )
    name_text.knob("xjustify").setValue("left")
    name_text.knob("yjustify").setValue("bottom")
    name_text.knob("enable_background").setValue(1)
    name_text.setName("name")
    # message set below to force the font size to update

    blur_node = nuke.createNode("Blur")
    nuke.delete(
        blur_node
    )  # What's this for? Idk why, but this makes it so the user name isn't gigantic. idk why.

    # set text node message values (because if I don't do it here, the font size won't update in time and you'll just have big massive font sizes)

    return [frame_num_text, shot_code_text, date_text, name_text, department_text]


def update_text_messages(
    frame_num_text, shot_code_text, date_text, name_text, department_text
):
    frame_num_text.knob("message").setValue("Frame: [frame]")
    shot_code_text.knob("message").setValue(get_project_name())
    date_text.knob("message").setValue(get_date())
    name_text.knob("message").setValue(str(get_users_name()))

    # department dropdown and text
    department_text.knob("message").setValue("[value departmentDropdown]")


def get_in_out():
    curr_shot = get_project_name()
    conn = DB.Get(DB_Config)
    print(str(curr_shot))
    shot_info = conn.get_shot_by_code(curr_shot)
    # print(curr_shot)
    # print(shot_info.cut_in)
    # print(shot_info.cut_out)
    return [shot_info.cut_in, shot_info.cut_out]


def get_project_name():
    project_name = ""
    if project_file:
        project_name_with_ext = os.path.basename(project_file)
        project_name, ext = os.path.splitext(project_name_with_ext)
    else:
        project_name = "Unsaved Project"
    return project_name


def get_date():
    today = datetime.date.today()
    formatted_date = today.strftime("%m/%d/%Y")
    return formatted_date


def get_users_name():
    """
    Returns the full name corresponding to the current user's login as defined in usernames.json.
    If the username is not found in the JSON file, returns None.
    """
    # Get the current login username
    username = os.getlogin()

    # Determine the path to the usernames.json file in production.

    json_path = str(get_production_path()) + "/json/usernames.json"
    # print(str(json_path))

    # Open and load the JSON file.
    with open(json_path, "r") as f:
        user_data = json.load(f)

    # Return the corresponding name for the username.
    # If the key is not found, .get() will return None.
    return user_data.get(username)


def get_output_file_info_mov():
    base_path = "/groups/dungeons/edit/shots/lighting/"
    shot_code = os.path.splitext(os.path.basename(nuke.root().name()))[0]

    # Construct the folder path
    folder_path = os.path.join(base_path, shot_code)

    # If the folder doesn't exist, default to version 001.
    if not os.path.exists(folder_path):
        new_file_name = f"{shot_code}_V001.mov"
    else:
        all_file_names = os.listdir(folder_path)
        # Extract version numbers from file names that match the pattern.
        version_numbers = [
            int(re.search(r"_V(\d+)", f).group(1))
            for f in all_file_names
            if re.search(r"_V\d+", f)
        ]
        next_version = (max(version_numbers) if version_numbers else 0) + 1
        new_file_name = f"{shot_code}_V{next_version:03d}.mov"

    return [new_file_name, folder_path]


def get_output_file_info_exr():
    base_path = "/groups/dungeons/edit/shots/comp/"

    # setting the file parameter
    file_name = os.path.splitext(os.path.basename(nuke.root().name()))[0]
    folder_path = base_path + file_name
    full_path = folder_path + "/" + file_name + ".###.exr"
    return [folder_path, full_path]


def make_MOV_node():
    new_file_name = get_output_file_info_mov()[0]
    folder_path = get_output_file_info_mov()[1]

    # Create the full file path.
    full_path = os.path.join(folder_path, new_file_name)
    # print("full file path: " + full_path)

    write_node = nuke.createNode("Write")
    write_node.setName("MOV_write")

    # Set file and file type.
    write_node["file"].setValue(full_path)
    write_node["file_type"].setValue("mov64")

    # Create directories automatically.
    write_node["create_directories"].setValue(1)

    # Other write node settings.
    write_node["colorspace"].setValue(6)  # Data (linear-rawr)
    write_node["transformType"].setValue(1)  # Display transform
    write_node["mov64_codec"].setValue(
        12
    )  # Avid DnxHr (integer value 12 for some reason)
    write_node["mov64_dnxhd_codec_profile"].setValue(1)  # DNxHD 422 10-bit 220Mbit

    # Example: touching the file after render (using the new file name)
    command = 'os.system("touch ' + os.path.join(folder_path, new_file_name) + '")'
    write_node["afterRender"].setValue(command)

    return write_node


def update_mov_node(write_node):
    # print("in the update mov node")
    write_node["mov64_codec"].setValue(
        13
    )  # option 13 should be Avid DnxHr WHY NOT 3?? Idk
    write_node["mov64_dnxhd_codec_profile"].setValue(
        0
    )  # option 1 should be 4:4:4 12 bit


def make_EXR_node():
    # folder_path = get_output_file_info_exr()[0]
    full_path = get_output_file_info_exr()[1]

    write_node = nuke.createNode("Write")
    write_node["file"].setValue(full_path)
    write_node.setName("EXR_write")

    # create directories
    write_node["create_directories"].setValue(1)

    # TODO set exr settings and stuff
    write_node["write_ACES_compliant_EXR"].setValue(1)
    write_node["colorspace"].setValue(7)  # Data (linear-rawr)
    write_node["transformType"].setValue(0)  # Display transform
    return write_node


def check_saved():
    current_script_name = os.path.splitext(os.path.basename(nuke.root().name()))[0]
    if current_script_name == "Root":
        nuke.message(
            "This nuke script isn't saved, so I don't know what shot you're wanting to write out! Please save your shot!"
        )
        return False
    else:
        return True


def makeUI(groupNode):
    # groupNode = nuke.createNode("NoOp")
    # tab 1 (mov export)
    mov_tab_name = "MOV Export"
    tab_knob = nuke.Tab_Knob(mov_tab_name)
    groupNode.addKnob(tab_knob)

    # Define the script for the PyScript_Knob.
    mov_export_script = """
group = nuke.thisNode()
# Read the frame range from the node's custom knobs.
first_frame = int(group["export_frame_in"].value())
last_frame  = int(group["export_frame_out"].value())

group.begin()  # Enter the group's internal node graph.
write_node = nuke.toNode("MOV_write")
if write_node:
    nuke.execute(write_node.name(), first_frame, last_frame, 1)
else:
    nuke.message("MOV_write node not found inside the group!")
group.end()  # Exit the group.
    """
    # render button
    mov_export_button = nuke.PyScript_Knob(
        "mov_export", "Export MOV", mov_export_script
    )

    new_file_name = get_output_file_info_mov()[0]
    folder_path = get_output_file_info_mov()[1]

    # Create the full file path.
    full_path = os.path.join(folder_path, new_file_name)

    mov_export_path = nuke.Text_Knob("mov_export_path", "")
    mov_export_path.setValue(full_path)
    # mov_export_path.clearFlag(nuke.STARTLINE)

    button_script_open_file = """
import os
import nuke

folder = "{folder_path}"
if not os.path.exists(folder):
    nuke.message("This folder does not exist yet, but it will after you export")
else:
    os.system("xdg-open '" + folder + "'")
""".format(folder_path=folder_path)

    # Create the PyScript_Knob with the script above.
    open_folder_button = nuke.PyScript_Knob(
        "open_folder", "Open Folder", button_script_open_file
    )
    open_folder_button.clearFlag(nuke.STARTLINE)

    # frame range note
    # cut_info = get_in_out()
    frame_range = nuke.Text_Knob("frame_range", "")
    frame_range.setValue(
        "Frame range is currently set to:"
    )  # + str(cut_info[0]) + "-" + str(cut_info[1]))

    # frame ranges
    frame_in = nuke.Int_Knob("export_frame_in", "")
    frame_in.setValue(get_in_out()[0])
    frame_out = nuke.Int_Knob("export_frame_out", "")
    frame_out.setValue(get_in_out()[1])
    frame_out.clearFlag(nuke.STARTLINE)

    groupNode.addKnob(mov_export_button)
    groupNode.addKnob(frame_range)
    groupNode.addKnob(frame_in)
    groupNode.addKnob(frame_out)

    # checkboxes
    checkbox1 = nuke.Boolean_Knob("disable_text", "Disable On Screen Text")

    # dividers
    divider1 = nuke.Text_Knob("divider1", "")
    divider2 = nuke.Text_Knob("divider2", "")
    divider3 = nuke.Text_Knob("divider3", "")

    # dropdown
    department_dropdown = nuke.Enumeration_Knob(
        "departmentDropdown", "", ["Lighting", "Compositing"]
    )

    # add all knobs to node
    groupNode.addKnob(divider1)
    groupNode.addKnob(department_dropdown)
    groupNode.addKnob(checkbox1)  # disable on screen text
    groupNode.addKnob(divider2)
    groupNode.addKnob(mov_export_path)
    groupNode.addKnob(open_folder_button)

    # EXR    EXR EXR EXR     EXR EXR     EXR EXR
    # tab 1 (EXR export)
    exr_tab_name = "EXR Export"
    tab_knob = nuke.Tab_Knob(exr_tab_name)
    groupNode.addKnob(tab_knob)

    exr_export_script = """
group = nuke.thisNode()
# Read the frame range from the node's custom knobs.
first_frame = int(group["export_frame_in_exr"].value())
last_frame  = int(group["export_frame_out_exr"].value())

group.begin()  # Enter the group's internal node graph.
write_node = nuke.toNode("EXR_write")
if write_node:
    nuke.execute(write_node.name(), first_frame, last_frame, 1)
else:
    nuke.message("EXR_write node not found inside the group!")
group.end()  # Exit the group.
    """

    # render button
    mov_export_button = nuke.PyScript_Knob(
        "exr_export", "Export EXR", exr_export_script
    )

    # frame range note
    frame_range = nuke.Text_Knob("frame_range_exr", "")
    frame_range.setValue(
        "Frame range is currently set to:"
    )  # + str(cut_info[0]) + "-" + str(cut_info[1]) + "\n\n")

    # frame ranges
    frame_in_exr = nuke.Int_Knob("export_frame_in_exr", "")
    frame_in_exr.setValue(get_in_out()[0])
    frame_out_exr = nuke.Int_Knob("export_frame_out_exr", "")
    frame_out_exr.setValue(get_in_out()[1])
    frame_out_exr.clearFlag(nuke.STARTLINE)

    # Exr render note
    note_exr = nuke.Text_Knob("note_exr", "")
    note_exr.setValue("\n(Please note, EXR's will NOT have text overlay)\n")
    full_path = get_output_file_info_exr()[1]
    folder_path = get_output_file_info_exr()[0]
    exr_export_path = nuke.Text_Knob("exr_export_path", "")
    exr_export_path.setValue(full_path)
    # mov_export_path.clearFlag(nuke.STARTLINE)

    button_script_open_file = """
import os
import nuke

folder = "{folder_path}"
if not os.path.exists(folder):
    nuke.message("This folder does not exist yet, but it will after you export")
else:
    os.system("xdg-open '" + folder + "'")
""".format(folder_path=folder_path)

    # Create the PyScript_Knob with the script above.
    open_folder_button_exr = nuke.PyScript_Knob(
        "open_folder", "Open Folder", button_script_open_file
    )
    open_folder_button_exr.clearFlag(nuke.STARTLINE)

    groupNode.addKnob(mov_export_button)
    groupNode.addKnob(frame_range)
    groupNode.addKnob(frame_in_exr)
    groupNode.addKnob(frame_out_exr)

    groupNode.addKnob(note_exr)

    groupNode.addKnob(divider3)
    groupNode.addKnob(exr_export_path)
    groupNode.addKnob(open_folder_button_exr)


def createLinks(groupNode, text_nodes, mov_node, exr_node, switch):
    # mov export tab:
    switch["which"].setExpression("parent.disable_text")
    text_nodes[4]["departmentDropdown"].setExpression(
        "parent.departmentDropdown"
    )  # department


def main():
    if check_saved():
        current_node = None
        selected_nodes = nuke.selectedNodes()
        if selected_nodes:
            current_node = selected_nodes[0]

        base_name = "LD_Write"
        final_name = base_name

        # Check if a node with the base name exists.
        if nuke.toNode(base_name) is not None:
            count = 2  # Start numbering at 2.
            final_name = "{}{}".format(base_name, count)
            # Increment count until a unique name is found.
            while nuke.toNode(final_name) is not None:
                count += 1
                final_name = "{}{}".format(base_name, count)

        # Create the group node and set its name to the unique name.
        groupNode = nuke.createNode("Group")
        groupNode["name"].setValue(final_name)

        # Enter the group to build its internal node graph.
        groupNode.begin()

        # input_node
        input_node = nuke.createNode("Input")

        # All text nodes
        text_nodes = make_text_nodes()

        # Switch Node
        text_node_pos_x = text_nodes[3].xpos()
        text_node_pos_y = text_nodes[3].ypos()
        switcheroo = nuke.createNode("Switch")
        switcheroo.setInput(0, text_nodes[3])
        switcheroo.setInput(1, input_node)
        switcheroo.setXYpos(text_node_pos_x + 100, text_node_pos_y)

        # reformat node
        nuke.createNode("Reformat")

        # MOV node
        mov_node = make_MOV_node()

        # update text nodes messages
        update_text_messages(
            text_nodes[0], text_nodes[1], text_nodes[2], text_nodes[3], text_nodes[4]
        )

        # update settings in mov node
        update_mov_node(mov_node)

        # output Node
        output_node = nuke.createNode("Output")
        output_node.setInput(0, switcheroo)
        output_node.setXYpos(text_node_pos_x, text_node_pos_y + 100)

        # EXR node
        mov_node_pos_x = mov_node.xpos()
        mov_node_pos_y = mov_node.ypos()
        exr_node = make_EXR_node()
        exr_node.setInput(0, input_node)
        exr_node.setXYpos(mov_node_pos_x + 100, mov_node_pos_y)

        makeUI(groupNode)
        createLinks(groupNode, text_nodes, mov_node, exr_node, switcheroo)
        # Create Links

        for n in nuke.allNodes():
            n.hideControlPanel()
        groupNode.end()

        groupNode.setSelected(True)

        if current_node:
            groupNode.setInput(0, current_node)

        groupNode["tile_color"].setValue(0xFF6699FF)  # Example: a blueish color


# main()


project_file = nuke.root()["name"].value()


def make_text_nodes():
    # Text Padding
    rl_padding = 25
    tb_padding = 25
    font_size = 25
    frame_height = 816
    frame_width = 1920

    # Frame Number
    frame_num_text = nuke.createNode("Text2", "font_size 30")
    frame_num_text.knob("font_size").setValue(font_size)
    frame_num_text.knob("box").setValue(
        [rl_padding, tb_padding, frame_width - rl_padding, frame_height - tb_padding]
    )
    frame_num_text.knob("xjustify").setValue("right")
    frame_num_text.knob("yjustify").setValue("bottom")
    frame_num_text.knob("enable_background").setValue(1)
    frame_num_text.setName("Frame_Number")
    # message set below to force the font size to update

    # Department
    department_text = nuke.createNode("Text2")
    department_text.knob("font_size").setValue(font_size)
    department_text.knob("box").setValue(
        [
            rl_padding,
            tb_padding * 2 + font_size * 3,
            frame_width - rl_padding,
            frame_height,
        ]
    )
    department_text.knob("xjustify").setValue("left")
    department_text.knob("yjustify").setValue("bottom")
    department_text.knob("enable_background").setValue(1)
    department_text.setName("department_text")
    dropdown_knob = nuke.Enumeration_Knob(
        "departmentDropdown", "departmentDropdown", ["Lighting", "Compositing"]
    )
    department_text.addKnob(dropdown_knob)
    # message set below to force the font size to update

    # Shot Code
    shot_code_text = nuke.createNode("Text2")
    shot_code_text.knob("font_size").setValue(font_size)
    shot_code_text.knob("box").setValue(
        [rl_padding, tb_padding + font_size * 2, frame_width - rl_padding, frame_height]
    )
    shot_code_text.knob("xjustify").setValue("right")
    shot_code_text.knob("yjustify").setValue("bottom")
    shot_code_text.knob("enable_background").setValue(1)
    shot_code_text.setName("Shot_Code")
    # message set below to force the font size to update

    # date
    date_text = nuke.createNode("Text2")
    date_text.knob("font_size").setValue(font_size)
    date_text.knob("box").setValue(
        [rl_padding, tb_padding + font_size * 2, frame_width - rl_padding, frame_height]
    )
    date_text.knob("xjustify").setValue("left")
    date_text.knob("yjustify").setValue("bottom")
    date_text.knob("enable_background").setValue(1)
    date_text.setName("date")
    # message set below to force the font size to update

    # user name
    name_text = nuke.createNode("Text2")
    name_text.knob("font_size").setValue(font_size)
    name_text.knob("box").setValue(
        [rl_padding, tb_padding, frame_width - rl_padding, frame_height - tb_padding]
    )
    name_text.knob("xjustify").setValue("left")
    name_text.knob("yjustify").setValue("bottom")
    name_text.knob("enable_background").setValue(1)
    name_text.setName("name")
    # message set below to force the font size to update

    blur_node = nuke.createNode("Blur")
    nuke.delete(
        blur_node
    )  # What's this for? Idk why, but this makes it so the user name isn't gigantic. idk why.

    # set text node message values (because if I don't do it here, the font size won't update in time and you'll just have big massive font sizes)
    return [frame_num_text, shot_code_text, date_text, name_text, department_text]


def update_text_messages(
    frame_num_text, shot_code_text, date_text, name_text, department_text
):
    frame_num_text.knob("message").setValue("Frame: [frame]")
    shot_code_text.knob("message").setValue(get_project_name())
    date_text.knob("message").setValue(get_date())
    name_text.knob("message").setValue(str(get_users_name()))

    # department dropdown and text
    department_text.knob("message").setValue("[value departmentDropdown]")


def get_in_out():
    curr_shot = get_project_name()
    conn = DB.Get(DB_Config)
    print(str(curr_shot))
    shot_info = conn.get_shot_by_code(curr_shot)
    # print(curr_shot)
    # print(shot_info.cut_in)
    # print(shot_info.cut_out)
    return [shot_info.cut_in, shot_info.cut_out]


def get_project_name():
    project_name = ""
    if project_file:
        project_name_with_ext = os.path.basename(project_file)
        project_name, ext = os.path.splitext(project_name_with_ext)
    else:
        project_name = "Unsaved Project"
    return project_name


def get_date():
    today = datetime.date.today()
    formatted_date = today.strftime("%m/%d/%Y")
    return formatted_date


def increment_version_num(curr_version):
    num_str = curr_version.split("_")[1]
    num_int = int(num_str) + 1
    return f"V_{num_int:0{len(num_str)}d}"


def get_version_num():
    # path to the shot versions json
    json_path = str(get_production_path()) + "/json/shot_versions.json"

    with open(json_path, "r") as f:
        shot_data = json.load(f)

    # I think this should return the version number, with V_001 is the default. Hopefully.
    shot_code = get_shot_code()
    if shot_data.get(shot_code):
        return increment_version_num(
            shot_data.get(shot_code)
        )  # if a shot code already exists, you gotta increment it.
    else:
        return "V_001"  # If the shot has never been rendered out before


def get_shot_code():
    return os.path.splitext(os.path.basename(nuke.root().name()))[0]


def get_users_name():
    """
    Returns the full name corresponding to the current user's login as defined in usernames.json.
    If the username is not found in the JSON file, returns None.
    """
    # Get the current login username
    username = os.getlogin()

    # Determine the path to the usernames.json file in production.

    json_path = str(get_production_path()) + "/json/usernames.json"
    # print(str(json_path))

    # Open and load the JSON file.
    with open(json_path, "r") as f:
        user_data = json.load(f)

    # Return the corresponding name for the username.
    # If the key is not found, .get() will return None.
    return user_data.get(username)


def get_week_range():
    """Returns the start and end date of the current week (Sunday to Saturday)."""
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday() + 1)  # Sunday
    end_of_week = start_of_week + datetime.timedelta(days=6)  # Saturday
    return start_of_week, end_of_week


def get_output_file_info_mov():
    start_of_week, end_of_week = get_week_range()
    base_path = "/groups/dungeons/edit/shots/lighting/"
    shot_code = get_shot_code()

    valid_subfolder = None  # Store the most recent valid subfolder if found
    latest_date = None  # Track the most recent date found

    # Look for the most recent subfolder within the current week
    for subfolder in os.listdir(base_path):
        subfolder_path = os.path.join(base_path, subfolder)

        if os.path.isdir(subfolder_path) and len(subfolder) == 10:
            try:
                folder_date = datetime.datetime.strptime(subfolder, "%m-%d-%Y").date()
                if start_of_week <= folder_date <= end_of_week:
                    if latest_date is None or folder_date > latest_date:
                        latest_date = folder_date
                        valid_subfolder = (
                            subfolder_path  # Store the most recent valid folder
                        )
            except ValueError:
                continue  # Skip non-matching folders

    # If no valid subfolder is found, create one with today's date
    if valid_subfolder is None:
        today_str = datetime.date.today().strftime("%m-%d-%Y")
        valid_subfolder = os.path.join(base_path, today_str)
        os.makedirs(valid_subfolder)
        print(f"Created new subfolder: {valid_subfolder}")
    else:
        print(f"Using most recent subfolder: {valid_subfolder}")

    next_version = get_version_num()
    new_file_name = shot_code + "_" + next_version + ".mov"

    return [new_file_name, valid_subfolder]  # Always returns a list


def get_output_file_info_exr():
    base_path = "/groups/dungeons/edit/shots/comp/"

    # setting the file parameter
    file_name = get_shot_code()
    folder_path = base_path + file_name
    full_path = folder_path + "/" + file_name + ".###.exr"
    return [folder_path, full_path]


def make_MOV_node():
    new_file_name = get_output_file_info_mov()[0]
    folder_path = get_output_file_info_mov()[1]

    # Create the full file path.
    full_path = os.path.join(folder_path, new_file_name)
    # print("full file path: " + full_path)

    write_node = nuke.createNode("Write")
    write_node.setName("MOV_write")

    # Set file and file type.
    write_node["file"].setValue(full_path)
    write_node["file_type"].setValue("mov64")

    # Create directories automatically.
    write_node["create_directories"].setValue(1)

    # Other write node settings.
    write_node["colorspace"].setValue(6)  # Data (linear-rawr)
    write_node["transformType"].setValue(1)  # Display transform
    write_node["mov64_codec"].setValue(
        12
    )  # Avid DnxHr (integer value 12 for some reason)
    write_node["mov64_dnxhd_codec_profile"].setValue(1)  # DNxHD 422 10-bit 220Mbit

    # update the version number json.
    shot_code = get_shot_code()
    version_num = get_version_num()
    json_path = str(get_production_path()) + "/json/shot_versions.json"
    command = (
        "import json, os\n"
        'json_path = "{json_path}"\n'
        'with open(json_path, "r") as f:\n'
        "    data = json.load(f)\n"
        'data["{shot_code}"] = "{version_num}"\n'
        'with open(json_path, "w") as f:\n'
        "    json.dump(data, f, indent=4)\n"
    ).format(json_path=json_path, shot_code=shot_code, version_num=version_num)
    write_node["afterRender"].setValue(command)

    return write_node


def update_mov_node(write_node):
    # print("in the update mov node")
    write_node["mov64_codec"].setValue(
        13
    )  # option 13 should be Avid DnxHr WHY NOT 3?? Idk
    write_node["mov64_dnxhd_codec_profile"].setValue(
        0
    )  # option 1 should be 4:4:4 12 bit


def make_demoReel_mov_node():
    shot_code = get_shot_code() + ".mov"
    folder_path = "/groups/dungeons/edit/Reel_Shots"

    # Create the full file path.
    full_path = os.path.join(folder_path, shot_code)
    print(str(full_path))

    reel_write_node = nuke.createNode("Write")
    reel_write_node.setName("MOV_write_noText")

    # Set file and file type.
    reel_write_node["file"].setValue(full_path)
    reel_write_node["file_type"].setValue("mov64")

    # Create directories automatically.
    reel_write_node["create_directories"].setValue(1)

    # Other write node settings.
    reel_write_node["colorspace"].setValue(6)  # Data (linear-rawr)
    reel_write_node["transformType"].setValue(1)  # Display transform tried: 2,
    reel_write_node["mov64_codec"].setValue(
        "appr"
    )  # Avid DnxHr (integer value 12 for some reason) #don't try 2!!
    reel_write_node["mov_prores_codec_profile"].setValue(2)  # DNxHD 422 10-bit 220Mbit

    return reel_write_node


def make_EXR_node():
    # folder_path = get_output_file_info_exr()[0]
    full_path = get_output_file_info_exr()[1]

    write_node = nuke.createNode("Write")
    write_node["file"].setValue(full_path)
    write_node.setName("EXR_write")

    # create directories
    write_node["create_directories"].setValue(1)

    # TODO set exr settings and stuff
    write_node["write_ACES_compliant_EXR"].setValue(1)
    write_node["colorspace"].setValue(10)  # should be scene_linear (ACEScg)
    write_node["transformType"].setValue(0)  # transform type- colorspace
    return write_node


def check_saved():
    current_script_name = get_shot_code()
    if current_script_name == "Root":
        nuke.message(
            "This nuke script isn't saved, so I don't know what shot you're wanting to write out! Please save your shot!"
        )
        return False
    else:
        return True


def makeUI(groupNode):
    mov_tab_name = "MOV Export"
    tab_knob = nuke.Tab_Knob(mov_tab_name)
    groupNode.addKnob(tab_knob)

    mov_export_script = """
group = nuke.thisNode()
first_frame = int(group["export_frame_in"].value())
last_frame  = int(group["export_frame_out"].value())

group.begin()
write_node = nuke.toNode("MOV_write")
demo_node = nuke.toNode("MOV_write_noText")

if write_node:
    nuke.execute(write_node.name(), first_frame, last_frame, 1)
else:
    nuke.message("MOV_write node not found inside the group!")

if demo_node:
    nuke.execute(demo_node.name(), first_frame, last_frame, 1)
else:
    nuke.message("MOV_write_noText node not found inside the group!")

group.end()
"""

    # render button
    mov_export_button = nuke.PyScript_Knob(
        "mov_export", "Export MOV", mov_export_script
    )

    new_file_name = get_output_file_info_mov()[0]
    folder_path = get_output_file_info_mov()[1]
    full_path = os.path.join(folder_path, new_file_name)

    mov_export_path = nuke.Text_Knob("mov_export_path", "")
    mov_export_path.setValue(full_path)

    button_script_open_file = f"""
import os
import nuke

folder = "{folder_path}"
if not os.path.exists(folder):
    nuke.message("This folder does not exist yet, but it will after you export")
else:
    os.system("xdg-open '" + folder + "'")
"""

    open_folder_button = nuke.PyScript_Knob(
        "open_folder", "Open Folder", button_script_open_file
    )
    open_folder_button.clearFlag(nuke.STARTLINE)

    # frame range label
    frame_range = nuke.Text_Knob("frame_range", "")
    frame_range.setValue("Frame range is currently set to:")

    # frame ranges
    frame_in = nuke.Int_Knob("export_frame_in", "")
    frame_in.setValue(get_in_out()[0])
    frame_out = nuke.Int_Knob("export_frame_out", "")
    frame_out.setValue(get_in_out()[1])
    frame_out.clearFlag(nuke.STARTLINE)

    # shot handles button
    add_handles_script = """
group = nuke.thisNode()
original_in = int(group['export_frame_in'].value())
original_out = int(group['export_frame_out'].value())
new_in = original_in - 5
new_out = original_out + 5
group['export_frame_in'].setValue(new_in)
group['export_frame_out'].setValue(new_out)
nuke.message("This render will have 5 frames added to beginning and end of shot. Adjusted frame range = " + str(new_in) + "-" + str(new_out))
"""
    add_handles_button = nuke.PyScript_Knob(
        "add_shot_handles", "add shot handles", add_handles_script
    )
    add_handles_button.clearFlag(nuke.STARTLINE)

    # checkboxes
    checkbox1 = nuke.Boolean_Knob("disable_text", "Disable On Screen Text")

    # dividers
    divider1 = nuke.Text_Knob("divider1", "")
    divider2 = nuke.Text_Knob("divider2", "")
    divider3 = nuke.Text_Knob("divider3", "")

    # dropdown
    department_dropdown = nuke.Enumeration_Knob(
        "departmentDropdown", "", ["Lighting", "Compositing"]
    )

    # Add all knobs
    groupNode.addKnob(mov_export_button)
    groupNode.addKnob(frame_range)
    groupNode.addKnob(frame_in)
    groupNode.addKnob(frame_out)
    groupNode.addKnob(add_handles_button)
    groupNode.addKnob(divider1)
    groupNode.addKnob(department_dropdown)
    groupNode.addKnob(checkbox1)
    groupNode.addKnob(divider2)
    groupNode.addKnob(mov_export_path)
    groupNode.addKnob(open_folder_button)

    # EXR Export Tab
    exr_tab_name = "EXR Export"
    tab_knob = nuke.Tab_Knob(exr_tab_name)
    groupNode.addKnob(tab_knob)

    exr_export_script = """
group = nuke.thisNode()
first_frame = int(group["export_frame_in_exr"].value())
last_frame  = int(group["export_frame_out_exr"].value())

group.begin()
write_node = nuke.toNode("EXR_write")
if write_node:
    nuke.execute(write_node.name(), first_frame, last_frame, 1)
else:
    nuke.message("EXR_write node not found inside the group!")
group.end()
"""

    exr_export_button = nuke.PyScript_Knob(
        "exr_export", "Export EXR", exr_export_script
    )

    frame_range_exr = nuke.Text_Knob("frame_range_exr", "")
    frame_range_exr.setValue("Frame range is currently set to:")

    frame_in_exr = nuke.Int_Knob("export_frame_in_exr", "")
    frame_in_exr.setValue(get_in_out()[0])
    frame_out_exr = nuke.Int_Knob("export_frame_out_exr", "")
    frame_out_exr.setValue(get_in_out()[1])
    frame_out_exr.clearFlag(nuke.STARTLINE)

    note_exr = nuke.Text_Knob("note_exr", "")
    note_exr.setValue("\n(Please note, EXR's will NOT have text overlay)\n")

    full_path_exr = get_output_file_info_exr()[1]
    folder_path_exr = get_output_file_info_exr()[0]
    exr_export_path = nuke.Text_Knob("exr_export_path", "")
    exr_export_path.setValue(full_path_exr)

    button_script_open_exr = f"""
import os
import nuke

folder = "{folder_path_exr}"
if not os.path.exists(folder):
    nuke.message("This folder does not exist yet, but it will after you export")
else:
    os.system("xdg-open '" + folder + "'")
"""

    open_folder_button_exr = nuke.PyScript_Knob(
        "open_folder", "Open Folder", button_script_open_exr
    )
    open_folder_button_exr.clearFlag(nuke.STARTLINE)

    # Add EXR UI knobs
    groupNode.addKnob(exr_export_button)
    groupNode.addKnob(frame_range_exr)
    groupNode.addKnob(frame_in_exr)
    groupNode.addKnob(frame_out_exr)
    groupNode.addKnob(note_exr)
    groupNode.addKnob(divider3)
    groupNode.addKnob(exr_export_path)
    groupNode.addKnob(open_folder_button_exr)


def createLinks(groupNode, text_nodes, mov_node, exr_node, switch):
    # mov export tab:
    switch["which"].setExpression("parent.disable_text")
    text_nodes[4]["departmentDropdown"].setExpression(
        "parent.departmentDropdown"
    )  # department


def main():
    if check_saved():
        current_node = None
        selected_nodes = nuke.selectedNodes()
        if selected_nodes:
            current_node = selected_nodes[0]

        base_name = "LD_Write"
        final_name = base_name

        # Check if a node with the base name exists.
        if nuke.toNode(base_name) is not None:
            count = 2  # Start numbering at 2.
            final_name = "{}{}".format(base_name, count)
            # Increment count until a unique name is found.
            while nuke.toNode(final_name) is not None:
                count += 1
                final_name = "{}{}".format(base_name, count)

        # Create the group node and set its name to the unique name.
        groupNode = nuke.createNode("Group")
        groupNode["name"].setValue(final_name)

        # Enter the group to build its internal node graph.
        groupNode.begin()

        # input_node
        input_node = nuke.createNode("Input")

        # reformat node
        reformat_node = nuke.createNode("Reformat")
        reformat_node["format"].setValue("Love_and_Dungeons_aspect_ratio")
        reformat_node.setInput(0, input_node)

        # All text nodes
        text_nodes = make_text_nodes()

        # Switch Node
        text_node_pos_x = text_nodes[3].xpos()
        text_node_pos_y = text_nodes[3].ypos()
        switcheroo = nuke.createNode("Switch")
        switcheroo.setInput(0, text_nodes[3])
        switcheroo.setInput(1, reformat_node)
        switcheroo.setXYpos(text_node_pos_x + 100, text_node_pos_y)

        # reformat node
        nuke.createNode("Reformat")

        # MOV node
        mov_node = make_MOV_node()

        # update text nodes messages
        update_text_messages(
            text_nodes[0], text_nodes[1], text_nodes[2], text_nodes[3], text_nodes[4]
        )

        # update settings in mov node
        update_mov_node(mov_node)

        # output Node
        output_node = nuke.createNode("Output")
        output_node.setInput(0, switcheroo)
        output_node.setXYpos(text_node_pos_x, text_node_pos_y + 100)

        # EXR node
        mov_node_pos_x = mov_node.xpos()
        mov_node_pos_y = mov_node.ypos()
        exr_node = make_EXR_node()
        exr_node.setInput(0, reformat_node)
        exr_node.setXYpos(mov_node_pos_x + 100, mov_node_pos_y)

        # another mov node for demo reels
        exr_node_pos_x = exr_node.xpos()
        exr_node_pos_y = exr_node.ypos()
        demo_write_node = make_demoReel_mov_node()
        demo_write_node.setInput(0, reformat_node)
        demo_write_node.setXYpos(exr_node_pos_x + 100, exr_node_pos_y)

        makeUI(groupNode)
        createLinks(groupNode, text_nodes, mov_node, exr_node, switcheroo)
        # Create Links

        for n in nuke.allNodes():
            n.hideControlPanel()
        groupNode.end()

        groupNode.setSelected(True)

        if current_node:
            groupNode.setInput(0, current_node)

        groupNode["tile_color"].setValue(0xFF6699FF)  # Example: a blueish color


# main()


class CascadingComboBox(QtWidgets.QWidget):
    def __init__(self):
        super(CascadingComboBox, self).__init__()

        # Set up the window
        self.setWindowTitle("L&D Import Render Layers!!")
        self.setGeometry(100, 100, 800, 600)

        # Mode tracking: "renders" for showing render folders,
        # "layers" for showing render layers inside a render folder.
        self.current_mode = "renders"
        self.current_render = None  # Holds the selected render folder

        # Create a label for the title
        self.title_label = QtWidgets.QLabel(
            "This tool was not written by Scott, believe it or not", self
        )
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)

        # Create a tool button to mimic a cascading combobox
        self.tool_button = QtWidgets.QToolButton(self)
        self.tool_button.setText("Select Shot")
        self.tool_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        # Create the main menu
        self.menu = QtWidgets.QMenu(self)
        self.tool_button.setMenu(self.menu)

        # Get and categorize shots
        all_shots = self.get_shots()
        categorized_data = self.categorize_data(all_shots)

        # Populate the cascading menu
        self.populate_cascading_menu(categorized_data)

        # Get the default shot from the current Nuke file name
        self.default_shot = os.path.basename(nuke.Root().name())[:-3]
        if not bool(re.match(r"^[A-Za-z]_", self.default_shot)):
            self.default_shot = "A_010"

        # Create a label to display the current shot
        self.current_shot_label = QtWidgets.QLabel(
            f"Current Shot: {self.default_shot}", self
        )
        self.current_shot_label.setAlignment(QtCore.Qt.AlignLeft)

        # Create a list widget for displaying thumbnails
        self.thumbnail_list = QtWidgets.QListWidget(self)
        self.thumbnail_list.setViewMode(QtWidgets.QListWidget.IconMode)
        self.thumbnail_list.setIconSize(QtCore.QSize(150, 150))
        self.thumbnail_list.setResizeMode(QtWidgets.QListWidget.Adjust)
        # Initially, enforce single selection in "renders" mode.
        self.thumbnail_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )

        # Load render folders for the default shot.
        self.update_renders(self.default_shot)

        # Create the action button.
        # In "renders" mode, its text will be "Select Render".
        self.action_button = QtWidgets.QPushButton("Select Render", self)
        self.action_button.clicked.connect(self.on_action_button_clicked)

        # Create the back button (only visible in layers mode).
        self.back_button = QtWidgets.QPushButton("Back", self)
        self.back_button.clicked.connect(self.go_back)
        self.back_button.hide()  # Hide initially

        # Create the cancel button.
        self.cancel_button = QtWidgets.QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.close)

        # Button layout.
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.back_button)
        button_layout.addWidget(self.action_button)
        button_layout.addWidget(self.cancel_button)

        # Main layout.
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(self.title_label)
        main_layout.addWidget(self.tool_button)
        main_layout.addWidget(self.current_shot_label)
        main_layout.addWidget(self.thumbnail_list)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def get_shots(self):
        """Fetch the list of shots from the database."""
        try:
            conn = DB.Get(DB_Config)
            shots = conn.get_shot_code_list()
            return shots
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to fetch shots: {e}")
            return []

    def categorize_data(self, all_shots):
        """
        Categorize shots into groups based on their prefixes.
        """
        categorized_data = {"Other": []}
        for item in all_shots:
            if len(item) > 1 and item[0].isalpha() and item[1] == "_":
                category = item.split("_")[0]
                if category not in categorized_data:
                    categorized_data[category] = []
                categorized_data[category].append(item)
            else:
                categorized_data["Other"].append(item)

        # Sort each category alphabetically
        for key in categorized_data:
            categorized_data[key] = sorted(categorized_data[key])

        # Sort categories and ensure "Other" is last
        sorted_categories = {
            k: categorized_data[k] for k in sorted(categorized_data) if k != "Other"
        }
        if "Other" in categorized_data:
            sorted_categories["Other"] = categorized_data["Other"]
        return sorted_categories

    def populate_cascading_menu(self, categorized_data):
        """
        Populate the cascading menu with categorized shots.
        """
        for category, items in categorized_data.items():
            if category != "Other":
                submenu = self.menu.addMenu(f"{category} Sequence")
                for shot in items:
                    action = submenu.addAction(shot)
                    action.triggered.connect(partial(self.on_shot_selected, shot))
            else:
                other_menu = self.menu.addMenu("Other")
                for shot in items:
                    action = other_menu.addAction(shot)
                    action.triggered.connect(partial(self.on_shot_selected, shot))

    def on_shot_selected(self, shot):
        """
        Handle shot selection from the cascading menu.
        """
        self.tool_button.setText(shot)
        self.current_shot_label.setText(f"Current Shot: {shot}")
        self.default_shot = shot

        # Reset mode to renders and update render folders.
        self.current_mode = "renders"
        self.current_render = None
        self.thumbnail_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self.action_button.setText("Select Render")
        self.back_button.hide()
        self.update_renders(shot)

    def update_renders(self, shot_num):
        """
        Update the thumbnail list with render folders for the selected shot,
        sorted by creation date (newest first).
        Also, if a 'beauty' layer exists with a thumb image, use that thumbnail.
        Any folders named '.backup' are ignored.
        """
        self.thumbnail_list.clear()
        base_path = r"/groups/dungeons/production/shot"
        shot_path = os.path.join(base_path, shot_num, "render")
        items_list = []  # Will store tuples of (creation_time, list_item)
        default_thumb = str(
            get_pipe_path()
            / "software/nuke/tools/NungeonTools/images/noThumbnailIcon.jpg"
        )

        if os.path.exists(shot_path):
            for folder_name in os.listdir(shot_path):
                # Skip any folder named .backup
                if folder_name.lower() == ".backup":
                    continue

                folder_path = os.path.join(shot_path, folder_name)
                if os.path.isdir(folder_path):
                    # Set the thumbnail to the default.
                    thumbnail_path = default_thumb

                    # --- Check for a beauty layer thumbnail first ---
                    # Look for a folder named "beauty" (case insensitive).
                    beauty_folder = None
                    for subfolder in os.listdir(folder_path):
                        if subfolder.lower() == "beauty":
                            beauty_folder = os.path.join(folder_path, subfolder)
                            break
                    if beauty_folder and os.path.isdir(beauty_folder):
                        thumb_folder = os.path.join(beauty_folder, "thumb")
                        if os.path.exists(thumb_folder) and os.path.isdir(thumb_folder):
                            thumbs = [
                                f
                                for f in os.listdir(thumb_folder)
                                if f.lower().endswith((".png", ".jpg", ".jpeg"))
                            ]
                            if thumbs:
                                thumb_image = random.choice(thumbs)
                                thumbnail_path = os.path.join(thumb_folder, thumb_image)
                                print(
                                    "Using beauty layer thumbnail for render:",
                                    thumbnail_path,
                                )
                    else:
                        # --- Fallback: Check the render folder's own thumbnail folder ---
                        render_thumb_folder = os.path.join(folder_path, "thumbnail")
                        if os.path.exists(render_thumb_folder) and os.path.isdir(
                            render_thumb_folder
                        ):
                            thumbs = [
                                f
                                for f in os.listdir(render_thumb_folder)
                                if f.lower().endswith((".png", ".jpg", ".jpeg"))
                            ]
                            if thumbs:
                                thumb_image = random.choice(thumbs)
                                thumbnail_path = os.path.join(
                                    render_thumb_folder, thumb_image
                                )
                                print("Using render folder thumbnail:", thumbnail_path)
                        else:
                            print(
                                "Using default thumbnail for render folder:",
                                thumbnail_path,
                            )

                    # Create list widget item.
                    item = QtWidgets.QListWidgetItem()
                    pixmap = QtGui.QPixmap(thumbnail_path)
                    scaled_pixmap = pixmap.scaled(
                        316,
                        150,
                        QtCore.Qt.KeepAspectRatio,
                        QtCore.Qt.SmoothTransformation,
                    )
                    item.setIcon(QtGui.QIcon(scaled_pixmap))

                    # Define paths for images (to get creation time)
                    images_folder_path = os.path.join(folder_path, "images")
                    try:
                        file_times = [
                            os.path.getmtime(os.path.join(images_folder_path, f))
                            for f in os.listdir(images_folder_path)
                            if f.lower().endswith((".png", ".jpg", ".jpeg", ".exr"))
                        ]
                        if file_times:
                            creation_time = min(file_times)
                        else:
                            creation_time = os.path.getmtime(folder_path)
                    except Exception:
                        creation_time = os.path.getmtime(folder_path)

                    creation_date = time.strftime(
                        "%m-%d-%Y", time.localtime(creation_time)
                    )
                    item.setText(f"{folder_name}\n{creation_date}")
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    items_list.append((creation_time, item))

        # Sort items by creation time descending (newest first).
        sorted_items = sorted(items_list, key=lambda x: x[0], reverse=True)
        for _, item in sorted_items:
            self.thumbnail_list.addItem(item)

    def load_layers(self):
        """
        Load render layers for the selected render folder.
        The view is updated to show subfolders (render layers) within the selected render.
        Folders named '.backup' are ignored.
        """
        selected_items = self.thumbnail_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Please select a render folder."
            )
            return

        # Enforce single selection for render folder; get the folder name.
        render_folder = selected_items[0].text().split("\n")[0]
        self.current_render = render_folder

        base_path = r"/groups/dungeons/production/shot"
        shot_path = os.path.join(base_path, self.default_shot, "render", render_folder)

        # Now update the thumbnail list with render layers (subfolders).
        self.thumbnail_list.clear()

        if os.path.exists(shot_path):
            layer_items = []
            # Change selection mode to allow multiple selection for layers.
            self.thumbnail_list.setSelectionMode(
                QtWidgets.QAbstractItemView.ExtendedSelection
            )

            for layer_name in os.listdir(shot_path):
                # Skip folders named .backup
                if layer_name.lower() == ".backup":
                    continue

                layer_path = os.path.join(shot_path, layer_name)
                if os.path.isdir(layer_path):
                    default_thumb = str(
                        get_pipe_path()
                        / "software/nuke/tools/NungeonTools/images/noThumbnailIcon.jpg"
                    )
                    thumbnail_path = default_thumb

                    # Check for a thumb folder inside the layer folder.
                    thumb_folder = os.path.join(layer_path, "thumb")
                    if os.path.exists(thumb_folder) and os.path.isdir(thumb_folder):
                        thumbs = [
                            f
                            for f in os.listdir(thumb_folder)
                            if f.lower().endswith((".png", ".jpg", ".jpeg"))
                        ]
                        if thumbs:
                            thumb_image = random.choice(thumbs)
                            thumbnail_path = os.path.join(thumb_folder, thumb_image)
                            print("Layer thumbnail path:", thumbnail_path)
                    else:
                        print("Using default thumbnail for layer:", thumbnail_path)

                    item = QtWidgets.QListWidgetItem()
                    pixmap = QtGui.QPixmap(thumbnail_path)
                    scaled_pixmap = pixmap.scaled(
                        316,
                        150,
                        QtCore.Qt.KeepAspectRatio,
                        QtCore.Qt.SmoothTransformation,
                    )
                    item.setIcon(QtGui.QIcon(scaled_pixmap))
                    item.setText(layer_name)
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    layer_items.append(item)

            for item in layer_items:
                self.thumbnail_list.addItem(item)

            # Switch mode to "layers" and update button text.
            self.current_mode = "layers"
            self.action_button.setText("Import Layers")
            self.back_button.show()
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing Folder",
                f"The render folder '{render_folder}' does not exist.",
            )

    def on_action_button_clicked(self):
        """
        Action button click handler.
        In "renders" mode, it loads render layers.
        In "layers" mode, it imports the selected layers.
        """
        if self.current_mode == "renders":
            self.load_layers()
        elif self.current_mode == "layers":
            self.import_layers()

    def go_back(self):
        """
        Go back from the render layers view to the renders view.
        """
        self.current_mode = "renders"
        self.current_render = None
        self.thumbnail_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self.action_button.setText("Select Render")
        self.back_button.hide()
        self.update_renders(self.default_shot)

    def import_layers(self):
        """
        Import selected render layers into Nuke.
        It imports the EXR sequences from each selected layer's 'images_dn' folder.
        """
        selected_items = self.thumbnail_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.warning(
                self,
                "No Selection",
                "Please select at least one render layer to import.",
            )
            return

        base_path = r"/groups/dungeons/production/shot"
        for item in selected_items:
            layer_folder = (
                item.text()
            )  # In layers mode, the text is just the layer name.
            images_dn_path = os.path.join(
                base_path,
                self.default_shot,
                "render",
                self.current_render,
                layer_folder,
                "images_dn",
            )
            print("Importing from:", images_dn_path)

            if os.path.exists(images_dn_path):
                exr_files = [
                    f for f in os.listdir(images_dn_path) if f.lower().endswith(".exr")
                ]
                if exr_files:
                    try:
                        exr_files.sort(
                            key=lambda x: int(os.path.splitext(x)[0].split(".")[-1])
                        )
                    except Exception as e:
                        print("Error sorting EXR files:", e)

                    first_frame = int(os.path.splitext(exr_files[0])[0].split(".")[-1])
                    last_frame = int(os.path.splitext(exr_files[-1])[0].split(".")[-1])
                    print("First frame:", first_frame, "Last frame:", last_frame)

                    sequence_path = os.path.join(images_dn_path, "####.exr")
                    read = nuke.createNode("Read", f"file {{{sequence_path}}}")
                    read["first"].setValue(first_frame)
                    read["last"].setValue(last_frame)
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Missing Sequence",
                        f"No EXR files found in {images_dn_path}",
                    )
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Missing Folder",
                    f"The folder '{images_dn_path}' does not exist.",
                )
        self.close()


def show_simple_window():
    global simple_window  # Prevent garbage collection
    simple_window = CascadingComboBox()
    simple_window.show()


def run():
    show_simple_window()


# run()


project_file = nuke.root()["name"].value()


def get_project_name():
    project_name = ""
    if project_file:
        project_name_with_ext = os.path.basename(project_file)
        project_name, ext = os.path.splitext(project_name_with_ext)
    else:
        project_name = "Unsaved Project"
    return project_name


def get_frame_range(project_name):
    conn = DB.Get(DB_Config)
    shot_info = conn.get_shot_by_code(project_name)
    return [shot_info.cut_in, shot_info.cut_out]


def set_frame_range(frame_in, frame_out):
    nuke.root()["first_frame"].setValue(frame_in)
    nuke.root()["last_frame"].setValue(frame_out)
    nuke.root()["lock_range"].setValue(True)


def set_full_frame_size(root_node):
    root_node["format"].setValue("Love_and_Dungeons_aspect_ratio")


def set_frame_rate(root_node):
    root_node["fps"].setValue(24)


def run():
    project_name = get_project_name()
    root_node = nuke.root()
    set_full_frame_size(root_node)

    # set frame range if the file is saved
    if project_name == "Unsaved Project":
        return
    else:
        frame_in, frame_out = get_frame_range(project_name)
        print("Frame out: " + str(frame_out))
        set_frame_range(frame_in, frame_out)
        set_frame_rate(root_node)


# run()


plugin_widgets: list[QtWidgets.QWidget] = []


def start_plugin():
    # Create text widget for menu
    action = QtWidgets.QAction("LnD — Publish Textures")
    action.triggered.connect(launch_exporter)

    # Add widget to the File menu
    sp.ui.add_action(sp.ui.ApplicationMenu.File, action)

    # Store the widget for proper cleanup later
    plugin_widgets.append(action)


def close_plugin():
    for widget in plugin_widgets:
        sp.ui.delete_ui_element(widget)

    plugin_widgets.clear()


if __name__ == "__main__":
    window = start_plugin()


def launch_exporter():
    if not sp.project.is_open():
        MessageDialog(
            get_main_qt_window(),
            "Please open a project before trying to publish",
            "No project open",
        ).exec_()
        return

    # remove existing windows before opening a new one
    for widget in plugin_widgets:
        if isinstance(widget, SubstanceExportWindow):
            widget.close()
            sp.ui.delete_ui_element(widget)
            plugin_widgets.remove(widget)
            break

    # launch window
    global window
    window = SubstanceExportWindow()
    window.show()

    print("Launching Substance Exporter")


"""Preflight checks to run on file load"""


conn = DB.Get(DB_Config)


def start_plugin():
    sp.event.DISPATCHER.connect_strong(sp.event.ProjectEditionEntered, do_preflight)


def close_plugin():
    sp.event.DISPATCHER.disconnect(sp.event.ProjectEditionEntered, do_preflight)


def do_preflight(event: sp.event.Event) -> None:
    metaUpdater = MetadataUpdater()
    srgbChecker = sRGBChecker()
    metaUpdater.check() or metaUpdater.prompt_update()
    srgbChecker.check() or srgbChecker.prompt_srgb_fix()


if __name__ == "__main__":
    window = start_plugin()
