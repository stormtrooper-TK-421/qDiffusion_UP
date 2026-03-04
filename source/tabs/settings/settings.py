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


def _windows_hidden_subprocess_kwargs() -> dict[str, object]:
    if not IS_WIN:
        return {}
    kwargs: dict[str, object] = {}
    startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
    startf_use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    if startupinfo_cls and startf_use_show_window:
        startupinfo = startupinfo_cls()
        startupinfo.dwFlags |= startf_use_show_window
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    creation_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if creation_flag:
        kwargs["creationflags"] = creation_flag
    return kwargs


class Update(QThread):
    status = Signal(str)
    failed = Signal(str)

    def __init__(self, settings):
        super().__init__(settings)
        self.settings = settings
        self.inference_commit_changed = False
        self.dependency_plan_changed = False
        self.error_message = ""

    def run(self):
        try:
            self.status.emit("Updating repositories...")
            pre_infer_commit, _ = self._safe_commit(git.INFER_REPO_PATH)

            git.git_reset(git.ROOT_REPO_PATH, git.QDIFF_URL)
            git.git_reset(git.INFER_REPO_PATH, git.INFER_URL)

            post_infer_commit, _ = self._safe_commit(git.INFER_REPO_PATH)
            self.inference_commit_changed = pre_infer_commit != post_infer_commit

            self.status.emit("Syncing inference requirements...")
            self._sync_infer_requirements()

            self.status.emit("Refreshing installer dependency metadata...")
            self.dependency_plan_changed = bool(self.settings.refreshInstallerPackagePlan())
            self.status.emit("Installer dependency metadata refreshed.")
        except Exception as exc:
            self.error_message = str(exc)
            self.failed.emit(self.error_message)

    def _safe_commit(self, path):
        try:
            return git.git_last(path)
        except Exception:
            return None, None

    def _sync_infer_requirements(self):
        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["QML_DISABLE_DISK_CACHE"] = "1"
        env["QT_DISABLE_SHADER_DISK_CACHE"] = "1"
        env["QSG_RHI_DISABLE_SHADER_DISK_CACHE"] = "1"
        status = subprocess.run(
            [sys.executable, SYNC_INFER_REQUIREMENTS_SCRIPT],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            **_windows_hidden_subprocess_kwargs(),
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
        self._updateStatusMessage = ""
        self._dependencyPlanNeedsRestart = False
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
        self._updateStatusMessage = "Updating repositories..."
        self._updateThread = Update(self)
        self._updateThread.status.connect(self._onUpdateStatus)
        self._updateThread.failed.connect(self._onUpdateFailed)
        self._updateThread.finished.connect(self.getGitInfo)
        self._updateThread.finished.connect(self.updateDone)
        self._updateThread.start()
        self.updated.emit()

    @Slot()
    def updateDone(self):
        self._updating = False
        if not self._updateThread.error_message:
            self._dependencyPlanNeedsRestart = self._dependencyPlanNeedsRestart or self._updateThread.dependency_plan_changed
            if self._updateStatusMessage == "":
                self._updateStatusMessage = "Update completed."
        elif not self._updateStatusMessage:
            self._updateStatusMessage = "Update failed."
        self.updated.emit()

    @Slot(str)
    def _onUpdateStatus(self, message):
        self._updateStatusMessage = message
        self.updated.emit()

    @Slot(str)
    def _onUpdateFailed(self, message):
        self._updateStatusMessage = f"Update failed: {message}"
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

    @Property(str, notify=updated)
    def updateStatusMessage(self):
        return self._updateStatusMessage
    
    @Property(bool, notify=updated)
    def updating(self):
        return self._updating
    
    @Slot()
    def getGitInfo(self):
        root_commit, root_label = self._repo_status(git.ROOT_REPO_PATH, "GUI")
        infer_commit, infer_label = self._repo_status(git.INFER_REPO_PATH, "Inference")

        if root_commit is None and not self._triedGitInit:
            self._triedGitInit = True
            git.git_init(git.ROOT_REPO_PATH, git.QDIFF_URL)
            root_commit, root_label = self._repo_status(git.ROOT_REPO_PATH, "GUI")

        if self._currentGitInfo is None:
            self._currentGitInfo = root_commit
        if self._currentGitServerInfo is None:
            self._currentGitServerInfo = infer_commit

        self._gitInfo = root_label
        self._gitServerInfo = infer_label
        code_needs_restart = (self._currentGitInfo != root_commit) or (self._currentGitServerInfo != infer_commit)
        self._needRestart = code_needs_restart or self._dependencyPlanNeedsRestart

        self.updated.emit()

    def _repo_status(self, path, name):
        commit, label = git.git_last(path)
        if commit:
            return commit, f"{name} repo ({path}) commit {commit[:12]}: {label}"
        return None, f"{name} repo ({path}) commit unknown"

    @Slot()
    def refreshInstallerPackagePlan(self):
        app = self.gui.parent()
        coordinator = getattr(app, "coordinator", None) if app else None
        if coordinator and hasattr(coordinator, "find_needed"):
            previous_plan = list(coordinator.packages) if hasattr(coordinator, "packages") else []
            if hasattr(coordinator, "clearCache"):
                coordinator.clearCache()
            coordinator.find_needed()
            refreshed_plan = list(coordinator.packages) if hasattr(coordinator, "packages") else []
            coordinator.updated.emit()
            return previous_plan != refreshed_plan
        return False
