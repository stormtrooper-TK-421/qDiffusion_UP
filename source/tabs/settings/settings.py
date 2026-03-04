import math
import os
import platform
import subprocess
import sys
IS_WIN = platform.system() == 'Windows'

from PySide6.QtCore import Property, Signal, QObject, Slot, QUrl, QThread
from PySide6.QtQml import qmlRegisterSingletonType

from misc import MimeData
import git


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SYNC_INFER_REQUIREMENTS_SCRIPT = os.path.join(REPO_ROOT, "scripts", "sync_infer_requirements.py")

class Update(QThread):
    def run(self):
        git.git_reset(".", git.QDIFF_URL)
        inf = os.path.join("source", "sd-inference-server")
        if os.path.exists(inf):
            git.git_reset(inf, git.INFER_URL)
            self._sync_infer_requirements()

    def _sync_infer_requirements(self):
        status = subprocess.run(
            [sys.executable, SYNC_INFER_REQUIREMENTS_SCRIPT],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode != 0:
            details = (status.stderr or status.stdout or "(no output)").strip()
            raise RuntimeError(f"Failed to sync inference requirements after update: {details}")

class Settings(QObject):
    updated = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.priority = math.inf
        self.name = "Settings"
        self.gui = parent
        self._currentTab = "Remote"
        self._currentUpload = ""
        self._currentUploadMode = 0

        qmlRegisterSingletonType(Settings, "gui", 1, 0, "SETTINGS", lambda _qml, _js, obj=self: obj)

        self._needRestart = False
        self._currentGitInfo = None
        self._currentGitServerInfo = None
        self._triedGitInit = False
        self._updating = False
        self.getGitInfo()

    @Property(str, notify=updated)
    def currentTab(self): 
        return self._currentTab
    
    @currentTab.setter
    def currentTab(self, tab):
        self._currentTab = tab
        self.updated.emit()

    @Property(str, notify=updated)
    def currentUpload(self): 
        return self._currentUpload

    @Property(int, notify=updated)
    def currentUploadMode(self): 
        return self._currentUploadMode

    @Slot(str, int)
    def setUpload(self, file, mode):
        if file.startswith("file:"):
            file = QUrl(file).toLocalFile()
        self._currentUpload = file
        self._currentUploadMode = mode
        self.updated.emit()

    @Slot()
    def restart(self):
        self.updated.emit()
        self.gui.restartBackend()

    @Slot(str, str)
    def download(self, type, url):
        if not url:# or self.gui.remoteInfoStatus != "Connected":
            return
        request = {"type": type, "url":url}
        
        for t in ["hf_token", "civitai_token"]:
            token = self.gui.config.get(t, "")
            if token:
                request[t] = token
        
        id = self.gui.makeRequest({"type":"download", "data":request})
        self.gui.network.create(url, id, True)

    @Slot()
    def refresh(self):
        self.gui.makeRequest({"type":"options"})

    @Slot()
    def update(self):
        self._updating = True
        update = Update(self)
        update.finished.connect(self.getGitInfo)
        update.finished.connect(self.updateDone)
        update.start()
        self.updated.emit()

    @Slot()
    def updateDone(self):
        self._updating = False
        self.updated.emit()
    
    @Slot(str, str)
    def upload(self, type, file):
        file = QUrl.fromLocalFile(file)
        if not file.isLocalFile() or self.gui.remoteInfoStatus != "Connected":
            return
        file = file.toLocalFile().replace('/', os.path.sep)
        id = self.gui.makeRequest({"type":"upload", "data":{"type": type, "file": file}})
        self.gui.network.create(file.split(os.path.sep)[-1], id, False)

    @Slot(QUrl, result=str)
    def toLocal(self, url):
        return url.toLocalFile()
    
    @Slot(MimeData, result=str)
    def pathDrop(self, mimeData):
        mimeData = mimeData.mimeData
        for url in mimeData.urls():
            if url.isLocalFile():
                return url.toLocalFile() 

    @Property(str, notify=updated)
    def gitInfo(self):
        return self._gitInfo
    
    @Property(str, notify=updated)
    def gitServerInfo(self):
        return self._gitServerInfo
    
    @Property(bool, notify=updated)
    def needRestart(self):
        return self._needRestart
    
    @Property(bool, notify=updated)
    def updating(self):
        return self._updating
    
    @Slot()
    def getGitInfo(self):
        self._gitInfo = "Unknown"
        self._gitServerInfo = ""

        commit, label = git.git_last(".")

        if commit:
            if self._currentGitInfo == None:
                self._currentGitInfo = commit
            self._gitInfo = label
            self._needRestart = self._currentGitInfo != commit
        elif not self._triedGitInit:
            self._triedGitInit = True
            git.git_init(".", git.QDIFF_URL)

        server_dir = os.path.join("source","sd-inference-server")
        if os.path.exists(server_dir):
            try:
                commit, label = git.git_last(server_dir)
            except:
                pass
            if commit:
                if self._currentGitServerInfo == None:
                    self._currentGitServerInfo = commit
                self._gitServerInfo = label
                self._needRestart = self._needRestart or (self._currentGitServerInfo != commit)

        self.updated.emit()