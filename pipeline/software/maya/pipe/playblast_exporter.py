# Adopted from Student Accomplice
# https://github.com/Student-Accomplice-Pipeline-Team/accomplice_pipe/blob/prod/pipe/accomplice/software/maya/pipe/animation/playblastExporter.py

import os
from PySide2 import QtWidgets, QtCore, QtGui
import maya.cmds as mc

path_to_review_folder = "G:\\shrineflow\\working_files\\Animation\\Review"

class View():
    def __init__(self, name, cameraName):
        self.name = name
        self.cameraName = cameraName

class PlayblastExporter(QtWidgets.QMainWindow):
    def __init__(self):
        super(PlayblastExporter, self).__init__()

        self.filename = ""
        self.videoFormat = "qt"
        self.videoScalePct = 100
        self.videoCompression = "Animation"
        self.videoOutputType = "movie"
        self.width = 1920
        self.height = 1080
        
        self.createdCameras = []

        self.reviews = self.getReviews()
        self.filename = self.getFilename()

        self.setupUI()

    def getFilename(self):
        current_filepath = mc.file(q=True, sn=True)
        current_filename = os.path.basename(current_filepath)
        raw_name, extension = os.path.splitext(current_filename)
        return raw_name

    def getReviews(self):
        return [name for name in os.listdir(path_to_review_folder) if os.path.isdir(os.path.join(path_to_review_folder, name))]

    def setupUI(self):
        self.setWindowTitle("Playblast Exporter")
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.setFixedSize(325, 200)

        self.mainWidget = QtWidgets.QWidget()
        self.mainLayout = QtWidgets.QVBoxLayout(self.mainWidget)
        self.setCentralWidget(self.mainWidget)

        # LISTS
        self.listLayout = QtWidgets.QHBoxLayout()
        self.mainLayout.addLayout(self.listLayout)

        self.reviewLayout = QtWidgets.QVBoxLayout()
        self.listLayout.addLayout(self.reviewLayout)

        self.reviewLabel = QtWidgets.QLabel("Reviews")
        self.reviewLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.reviewLayout.addWidget(self.reviewLabel)

        self.reviewListWidget = QtWidgets.QListWidget()
        self.reviewListWidget.setFixedWidth(150)
        self.reviewListWidget.addItems(self.reviews)
        self.reviewLayout.addWidget(self.reviewListWidget)

        # BUTTONS
        self.buttonLayout = QtWidgets.QHBoxLayout()
        self.mainLayout.addLayout(self.buttonLayout)

        self.exportButton = QtWidgets.QPushButton("Playblast")
        self.exportButton.clicked.connect(self.playblast)
        self.buttonLayout.addWidget(self.exportButton)

        self.cancelButton = QtWidgets.QPushButton("Cancel")
        self.buttonLayout.addWidget(self.cancelButton)
        
        self.cancelButton.clicked.connect(self.close)

    def setup_views(self):
        # Front view
        front_view = View(name="FrontView", cameraName="front")

        # Back view
        back_view_camera = mc.camera(orthographic=True, name="backView")
        mc.move(0, 0, -1000.1)
        mc.rotate(0, 180, 0)
        back_view = View(name="BackView", cameraName=back_view_camera)
        self.createdCameras.append(back_view_camera)

        # Right view
        right_view_camera = mc.camera(orthographic=True, name="rightView")
        mc.move(1000.1, 0, 0)
        mc.rotate(0, 90, 0)
        right_view = View(name="RightView", cameraName=right_view_camera)
        self.createdCameras.append(right_view_camera)
        
        # Left view
        left_view_camera = mc.camera(orthographic=True, name="leftView")
        mc.move(-1000.1, 0, 0)
        mc.rotate(0, -90, 0)
        left_view = View(name="LeftView", cameraName=left_view_camera)
        self.createdCameras.append(left_view_camera)

        return [front_view, back_view, right_view, left_view]

    def discard_cameras(self):
        pass

    def playblast(self):
        """Exports a playblast of the current animation to ??."""
        currentReview = f"{self.reviewListWidget.currentItem().text()}"
        filepath_folder = os.path.join(path_to_review_folder, currentReview)
        filepath_base = os.path.join(filepath_folder, self.filename)

        print(filepath_base)

        previous_lookthru = mc.lookThru(q=True)
        
        views = self.setup_views()
        try:
            for view in views:
                filepath = f'{filepath_base}_{view.name}'
                mc.lookThru(view.cameraName)
                # mc.playblast(f=filepath, forceOverwrite=True, viewer=False, percent=self.videoScalePct,
                #          format=self.videoFormat, compression=self.videoCompression, widthHeight = [self.width, self.height])
                mc.playblast(f=filepath, forceOverwrite=True, viewer=False, percent=self.videoScalePct,
                                widthHeight = [self.width, self.height])
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error",
                                           "Error exporting playblasts. See the script editor for details.")
            print(e)
            return

        mc.lookThru(previous_lookthru)
        messageBox = QtWidgets.QMessageBox(self)
        messageBox.setText("Playblasts exported successfully!")
        openOutputFolderButton = messageBox.addButton("Open Output Folder", QtWidgets.QMessageBox.AcceptRole)
        openOutputFolderButton.clicked.connect(lambda: os.system('xdg-open "%s"' % os.path.dirname(filepath_folder)))
        openOutputFolderButton.clicked.connect(self.close)
        closeButton = messageBox.addButton("Close", QtWidgets.QMessageBox.RejectRole)
        closeButton.clicked.connect(self.close)
        messageBox.exec_()

    def run(self):
        self.show()
