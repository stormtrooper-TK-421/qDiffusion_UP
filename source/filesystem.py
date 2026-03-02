import glob
import os
import threading

from PySide6.QtCore import Slot, Signal, QObject, QThreadPool, QRunnable, QFileSystemWatcher

class WatcherRunnableSignals(QObject):
    result = Signal(str, list, list)
    finished = Signal(str, int)
    def __init__(self, folder):
        super().__init__()
        self.stopping = False
        self.folder = folder

    @Slot(str)
    def die(self, folder):
        if folder == self.folder:
            self.stopping = True

class WatcherRunnable(threading.Thread):
    def __init__(self, folder):
        super().__init__()
        self.signals = WatcherRunnableSignals(folder)
        self.folder = folder
        self.daemon = True
    
    def run(self):
        try:
            files = glob.glob(os.path.join(self.folder, "*.*"))
            files = sorted(files, key = os.path.getmtime, reverse=True)

            file_batch = []
            idx_batch = []
            batch_size = 128
            for i, file in enumerate(files):
                if self.signals.stopping:
                    return
                file_batch += [os.path.abspath(file)]
                idx_batch += [len(files)-1-i]
                if len(file_batch) >= batch_size or i == len(files) - 1:
                    self.signals.result.emit(self.folder, file_batch, idx_batch)
                    file_batch = []
                    idx_batch = []
            
            if not self.signals.stopping:
                self.signals.finished.emit(self.folder, len(files))
        except Exception:
            return

class Watcher(QObject):
    started = Signal(str)
    parent_changed = Signal(str)
    folder_changed = Signal(str, list, list)
    file_changed = Signal(str)
    finished = Signal(str, int)
    kill = Signal(str)

    instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.onFolderChanged)
        self.watcher.fileChanged.connect(self.onFileChanged)

        self.folders = set()
        self.parents = {}

        self.pool = QThreadPool.globalInstance()
        self.running = {}

        Watcher.instance = self

        self.stopping = False

    def wait(self):
        self.stopping = True
        self.pool.waitForDone()

    @Slot(str)
    def watchFile(self, file):
        self.watcher.addPath(file)

    @Slot(str)
    def unwatchFile(self, file):
        self.watcher.removePath(file)
        
    @Slot(str)
    def watchFolder(self, folder):
        if folder in self.folders:
            return
        
        self.folders.add(folder)
        parentFolder = os.path.dirname(folder)
        self.parents[folder] = parentFolder

        self.watcher.addPath(folder)
        self.watcher.addPath(parentFolder)

        self.watcherStart(folder)

    @Slot(str)
    def unwatchFolder(self, folder):
        self.kill.emit(folder)

        self.folders.remove(folder)
        parent = self.parents[folder]
        del self.parents[folder]

        self.watcher.removePath(folder)
        if not parent in self.parents.values():
            self.watcher.removePath(parent)

    def watcherStart(self, folder):
        if self.stopping:
            return

        if folder in self.running:
            self.running[folder].signals.result.disconnect()
            self.running[folder].signals.finished.disconnect()
            self.kill.emit(folder)

        watcher = WatcherRunnable(folder)
        watcher.signals.result.connect(self.onWatcherResult)
        watcher.signals.finished.connect(self.onWatcherFinished)
        self.kill.connect(watcher.signals.die)

        self.running[folder] = watcher

        watcher.start()
        self.started.emit(folder)
    
    @Slot(str)
    def onFileChanged(self, file):
        self.file_changed.emit(file)

    @Slot(str)
    def onFolderChanged(self, folder):
        if folder in self.folders:
            self.watcherStart(folder)
            return
        else:
            self.parent_changed.emit(folder)
            for child, parent in list(self.parents.items()):
                if parent == folder:
                    self.watcher.addPath(child)
                    self.watcherStart(child)

    @Slot(str, int)
    def onWatcherFinished(self, folder, total):
        if folder in self.running:
            del self.running[folder]
        self.finished.emit(folder, total)

    @Slot(str, list, list)
    def onWatcherResult(self, folder, files, idxs):
        self.folder_changed.emit(folder, files, idxs)