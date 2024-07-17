from __future__ import annotations

import logging
import re

from PySide2 import QtWidgets, QtCore
from typing import TYPE_CHECKING

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
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
            | (has_cancel_button and QtWidgets.QDialogButtonBox.Cancel)
        )

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
