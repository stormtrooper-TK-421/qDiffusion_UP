from PySide6.QtCore import Property, Slot, Signal, QObject, QUrl
from PySide6.QtGui import QImage

import parameters
import os

class BasicOutput(QObject):
    updated = Signal()
    def __init__(self, basic, image):
        super().__init__(basic)
        self.basic = basic
        self._image = image or QImage()
        self._metadata = None
        self._artifacts = {}
        self._artifactNames = []
        self._display = None
        self._file = ""
        self._parameters = ""
        self._dragging = False
        self._ready = False
        self._fetching = False

    def __del__(self):
        print("BasicOutput deleted")

    def setResult(self, image, metadata, file):
        self._image = image
        self._ready = True
        self._fetching = False
        self._file = file

        if metadata:
            self._metadata = metadata

            self._parameters = parameters.formatParameters(self._metadata)
            self._image.setText("parameters", self._parameters)

        self.updated.emit()

    def setTemporary(self, image):
        self._fetching = True
        self.setPreview(image)

    def setPreview(self, image):
        self._image = image
        self.updated.emit()

    def setArtifacts(self, artifacts):
        self._artifacts = artifacts
        self._artifactNames = list(self._artifacts.keys())
        self._display = None
        self.updated.emit()

    def addArtifact(self, name, image):
        self._artifacts[name] = image
        self._artifactNames = list(self._artifacts.keys())
        self._display = None
        self.updated.emit()

    @Slot(QUrl)
    def saveImage(self, file):
        file = file.toLocalFile()
        if not "." in file.rsplit(os.path.sep,1)[-1]:
            file = file + ".png"
        try:
            self.display.save(file)
        except Exception:
            pass

    @Property(bool, notify=updated)
    def ready(self):
        return self._ready

    @Property(QImage, notify=updated)
    def image(self):
        return self._image
    
    @Property(QImage, notify=updated)
    def display(self):
        if not self._display:
            return self._image
        return self._artifacts[self._display]
    
    @Property(str, notify=updated)
    def displayName(self):
        return self._display
    
    @Property(str, notify=updated)
    def displayIndex(self):
        if not self._artifacts:
            return ""
        if not self._display:
            return f"1 of {len(self._artifactNames)+1}"
        else:
            idx = self._artifactNames.index(self._display)
            return f"{idx+2} of {len(self._artifactNames)+1}"
        
    @Property(QImage, notify=updated)
    def displayFull(self):
        return self.display

    @Slot()
    def nextDisplay(self):
        if not self._display:
            if self._artifactNames:
                self._display = self._artifactNames[0]
        else:
            idx = self._artifactNames.index(self._display) + 1
            if idx < len(self._artifactNames):
                self._display = self._artifactNames[idx]
            else:
                self._display = None
        self.updated.emit()
    
    @Slot()
    def prevDisplay(self):
        if not self._display:
            if self._artifactNames:
                self._display = self._artifactNames[-1]
        else:
            idx = self._artifactNames.index(self._display) - 1
            if idx >= 0:
                self._display = self._artifactNames[idx]
            else:
                self._display = None
        self.updated.emit()

    @Property(bool, notify=updated)
    def showingArtifact(self):
        return self._display != None

    @Property(str, notify=updated)
    def file(self):
        return self._file
    
    @Property(str, notify=updated)
    def mode(self):
        if not self._metadata:
            return ""
        return self._metadata["mode"]
    
    @Property(int, notify=updated)
    def width(self):
        return self.display.width()
    
    @Property(int, notify=updated)
    def height(self):
        return self.display.height()

    @Property(bool, notify=updated)
    def empty(self):
        return self._image.isNull()
        
    @Property(str, notify=updated)
    def size(self):
        if self._image.isNull():
            return ""
        return f"{self._image.width()}x{self._image.height()}"
    
    @Property(bool, notify=updated)
    def fetching(self):
        return self._fetching

    @Property(str, notify=updated)
    def parameters(self):
        return self._parameters

    @Slot()
    def drag(self):
        if not self._display:
            self.basic.gui.dragFiles([self._file])
        else:
            self.basic.gui.dragImage(self.display)

    @Slot()
    def copy(self):
        if not self._display:
            self.basic.gui.copyFiles([self._file])
        else:
            self.basic.gui.copyImage(self.display)

    @Property(list, notify=updated)
    def artifacts(self):
        return list(self._artifacts.keys())

    @Slot(str, result=QImage)
    def artifact(self, name):
        return self._artifacts[name]