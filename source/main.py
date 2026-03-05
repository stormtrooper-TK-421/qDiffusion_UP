import warnings
warnings.filterwarnings("ignore", category=UserWarning) 
warnings.filterwarnings("ignore", category=DeprecationWarning) 
warnings.filterwarnings("ignore", category=FutureWarning)

import sys
import signal
import traceback
import datetime
import subprocess
import os
import json
import hashlib
import argparse
from qml_compat import singleton_instance_provider
from pathlib import Path

os.environ["QT_DEBUG_PLUGINS"] = "1"
os.environ["QML_IMPORT_TRACE"] = "1"

from importlib.metadata import PackageNotFoundError, version

from runtime_requirements import missing_python_requirements

import platform
IS_WIN = platform.system() == 'Windows'
IS_MAC = platform.system() == 'Darwin'

from PySide6.QtCore import Signal as pyqtSignal, Slot as pyqtSlot, Property as pyqtProperty, QObject, QUrl, QCoreApplication, Qt, QElapsedTimer, QThread, qInstallMessageHandler, QtMsgType
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonType, qmlRegisterType
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QGuiApplication

from translation import Translator

NAME = "qDiffusion"
LAUNCHER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qDiffusion.exe")
APPID = "arenasys.qdiffusion." + hashlib.md5(LAUNCHER.encode("utf-8")).hexdigest()
ERRORED = False
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECTED_VENV = os.path.join(REPO_ROOT, ".venv")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from env_common import build_env as build_isolated_env
SOURCE_DIR = os.path.join(REPO_ROOT, "source")
QML_DIR = os.path.join(SOURCE_DIR, "qml")
TAB_DIR = os.path.join(SOURCE_DIR, "tabs")
INFERENCE_SERVER_REQUIREMENTS = os.path.join(REPO_ROOT, "requirements", "inference-server.txt")
GUI_CORE_REQUIREMENTS = os.path.join(REPO_ROOT, "requirements", "gui.txt")



def _portable_pyside6_root() -> Path:
    return Path(EXPECTED_VENV) / "Lib" / "site-packages" / "PySide6"


def _portable_qml_import_dir() -> Path | None:
    pyside6_root = _portable_pyside6_root()
    for candidate in (pyside6_root / "qml", pyside6_root / "Qt" / "qml"):
        if candidate.exists():
            return candidate
    return None


def _repo_file_url(path: Path) -> str:
    return QUrl.fromLocalFile(str(path.resolve())).toString()


def _repo_file_qurl(path: Path) -> QUrl:
    return QUrl.fromLocalFile(str(path.resolve()))


def _qml_file_url(*relative_parts: str) -> str:
    return _repo_file_url(Path(QML_DIR, *relative_parts))


def _qml_file_qurl(*relative_parts: str) -> QUrl:
    return _repo_file_qurl(Path(QML_DIR, *relative_parts))


def _tab_qml_file_url(*relative_parts: str) -> str:
    return _repo_file_url(Path(TAB_DIR, *relative_parts))


def _load_requirements(requirement_path):
    requirements = []
    with open(requirement_path, encoding="utf-8") as file:
        for line in file:
            requirement = line.split("#", 1)[0].strip()
            if requirement:
                requirements.append(requirement)
    return requirements



def qt_message_handler(mode, context, message):
    mode_map = {
        QtMsgType.QtDebugMsg: "DEBUG",
        QtMsgType.QtInfoMsg: "INFO",
        QtMsgType.QtWarningMsg: "WARNING",
        QtMsgType.QtCriticalMsg: "CRITICAL",
        QtMsgType.QtFatalMsg: "FATAL",
    }
    message_type = mode_map.get(mode, "UNKNOWN")
    context_file = context.file if context and context.file else "<unknown file>"
    context_line = context.line if context and context.line else 0
    context_function = context.function if context and context.function else "<unknown function>"
    timestamp = datetime.datetime.now().isoformat()

    with open("qt_crash.log", "a", encoding="utf-8") as f:
        f.write(
            f"[{timestamp}] [{message_type}] {message} "
            f"({context_file}:{context_line}, {context_function})\n"
        )

class Application(QApplication):
    t = QElapsedTimer()

    def event(self, e):
        return QApplication.event(self, e)
        
def check(requirements, enforce_version=True):
    return missing_python_requirements(requirements, enforce_version)


def _windows_hidden_subprocess_kwargs():
    if not IS_WIN:
        return {}
    kwargs = {}
    creation_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if creation_flag:
        kwargs["creationflags"] = creation_flag
    return kwargs


class Installer(QThread):
    output = pyqtSignal(str)
    updated = pyqtSignal()
    installing = pyqtSignal(str)
    installed = pyqtSignal(str)
    def __init__(self, parent, steps):
        super().__init__(parent)
        self.steps = steps
        self.proc = None
        self.stopping = False
        self.downloading = False
        self.download_progress = 1.0

    def run(self):
        for step in self.steps:
            self.installing.emit(step["label"])
            args = [sys.executable.replace("pythonw", "python"), "-m", *step["pip_args"]]

            self.proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=build_isolated_env(),
                **_windows_hidden_subprocess_kwargs(),
            )

            output = ""
            while self.proc.poll() == None:
                while line := self.proc.stdout.readline():
                    if line:
                        line = line.strip()
                        if line.startswith("Progress"):
                            _, current, _, total = line.split(" ")
                            if total:
                                self.download_progress = float(current)/float(total)
                                self.downloading = self.download_progress < 1.0

                                self.updated.emit()
                        else:
                            output += line + "\n"
                            self.output.emit(line)
                    if self.stopping:
                        return
            if self.stopping:
                return
            if self.proc.returncode:
                raise RuntimeError("Failed to install: ", step["label"], "\n", output)

            for package in step["report_packages"]:
                self.installed.emit(package)
        self.proc = None

    @pyqtSlot()
    def stop(self):
        self.stopping = True
        if self.proc:
            self.proc.kill()

class Coordinator(QObject):
    ready = pyqtSignal()
    show = pyqtSignal()
    proceed = pyqtSignal()
    cancel = pyqtSignal()

    output = pyqtSignal(str)

    updated = pyqtSignal()
    installedUpdated = pyqtSignal()
    def __init__(self, app, engine):
        super().__init__(app)
        self.app = app
        self.engine = engine
        self.installer = None

        self._needRestart = False
        self._installed = []
        self._installing = ""

        self._modes = ["nvidia", "amd", "remote"]

        self._mode = 0
        self.in_venv = "VIRTUAL_ENV" in os.environ


        self.override = False

        self.enforce = True

        try:
            with open("config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if "show_installer" in cfg:
                    self.override = cfg["show_installer"]
                if "enforce_versions" in cfg:
                    self.enforce = cfg["enforce_versions"]
                mode = self._modes.index(cfg["mode"].lower())
                self._mode = mode
        except Exception:
            pass

        self.optional: list[str] = []
        self.find_needed()

    def find_needed(self):
        self.torch_version = ""
        self.torchvision_version = ""
        self.directml_version = ""

        try:
            self.torch_version = version("torch")
        except PackageNotFoundError:
            pass

        try:
            self.torchvision_version = version("torchvision")
        except PackageNotFoundError:
            pass

        try:
            self.directml_version = version("torch-directml")
        except PackageNotFoundError:
            pass

        self.amd_torch_directml_version = "0.2.0.dev230426"
        
        self.core = _load_requirements(GUI_CORE_REQUIREMENTS)

        self.optional = _load_requirements(INFERENCE_SERVER_REQUIREMENTS)
        self.optional_need = check(self.optional, self.enforce)

    def _mode_backend_needed(self, mode):
        backend_needed = []
        if mode == "amd":
            if IS_WIN:
                if not self.directml_version:
                    backend_needed += ["torch-directml==" + self.amd_torch_directml_version]
        return backend_needed
    
    @pyqtProperty(list, constant=True)
    def modes(self):
        return ["Nvidia", "AMD", "Remote"]

    @pyqtProperty(int, notify=updated)
    def mode(self):
        return self._mode
    
    @mode.setter
    def mode(self, mode):
        self._mode = mode
        self.writeMode()
        self.updated.emit()

    def writeMode(self):
        cfg = {}
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            pass
        cfg['mode'] = self._modes[self._mode]
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    
    def clearCache(self):
        # Installer subprocesses are no-cache; keep compatibility for callers.
        return

    @pyqtProperty(bool, notify=updated)
    def enforceVersions(self):
        return self.enforce
    
    @enforceVersions.setter
    def enforceVersions(self, enforce):
        self.enforce = enforce
        self.find_needed()
        self.updated.emit()

    @pyqtProperty(list, notify=updated)
    def packages(self):
        return self.get_needed()
    
    @pyqtProperty(list, notify=installedUpdated)
    def installed(self):
        return self._installed
    
    @pyqtProperty(str, notify=installedUpdated)
    def installing(self):
        return self._installing
    
    @pyqtProperty(bool, notify=installedUpdated)
    def disable(self):
        return self.installer != None
    
    @pyqtProperty(bool, notify=updated)
    def needRestart(self):
        return self._needRestart

    def get_needed(self):
        mode = self._modes[self._mode]
        backend_needed = self._mode_backend_needed(mode)
        return [*backend_needed, *self.optional_need]

    def _build_install_steps(self, mode, backend_needed, inference_needed):
        steps = []

        if backend_needed:
            backend_args = ["pip", "install", "-U", *backend_needed]
            backend_args += ["--progress-bar", "raw"]
            steps.append(
                {
                    "label": "backend packages",
                    "pip_args": backend_args,
                    "report_packages": list(backend_needed),
                }
            )

        if inference_needed:
            inference_args = ["pip", "install", "-U", "-r", INFERENCE_SERVER_REQUIREMENTS]
            if IS_WIN:
                inference_args += ["--only-binary=:all:"]
            inference_args += ["--progress-bar", "raw"]
            steps.append(
                {
                    "label": "inference requirements",
                    "pip_args": inference_args,
                    "report_packages": list(inference_needed),
                }
            )

        return steps

    @pyqtSlot()
    def load(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon = os.path.join(root, "source", "qml", "icons", "placeholder.svg")
        self.app.setWindowIcon(QIcon(icon))
        self.loaded()

    @pyqtSlot()
    def loaded(self):
        ready()
        self.ready.emit()

        if self.override or (self.in_venv and self.packages):
            self.show.emit()
        else:
            self.done()
        
    @pyqtSlot()
    def done(self):
        start(self.engine, self.app)
        self.proceed.emit()

    @pyqtSlot()
    def install(self):
        if self.installer:
            self.cancel.emit()
            return
        mode = self._modes[self._mode]
        backend_needed = self._mode_backend_needed(mode)
        inference_needed = list(self.optional_need)
        packages = [*backend_needed, *inference_needed]
        if not packages:
            self.done()
            return
        self.installer = Installer(self, self._build_install_steps(mode, backend_needed, inference_needed))
        self.installer.installed.connect(self.onInstalled)
        self.installer.installing.connect(self.onInstalling)
        self.installer.output.connect(self.onOutput)    
        self.installer.updated.connect(self.onInstallUpdate)
        self.installer.finished.connect(self.doneInstalling)
        self.app.aboutToQuit.connect(self.installer.stop)
        self.cancel.connect(self.installer.stop)
        self.installer.start()
        self.installedUpdated.emit()

    @pyqtSlot(str)
    def onInstalled(self, package):
        self._installed += [package]
        self.installedUpdated.emit()
    
    @pyqtSlot(str)
    def onInstalling(self, package):
        self._installing = package
        self.installedUpdated.emit()
    
    @pyqtSlot(str)
    def onOutput(self, out):
        self.output.emit(out)

    @pyqtProperty(float, notify=installedUpdated)
    def progress(self):
        if self.installer and self.installer.downloading:
            return self.installer.download_progress
        return -1.0

    @pyqtSlot()
    def onInstallUpdate(self):
        self.installedUpdated.emit()
    
    @pyqtSlot()
    def doneInstalling(self):
        self.writeMode()
        self.clearCache()

        self._installing = ""
        self.installer = None
        self.installedUpdated.emit()
        self.find_needed()
        if not self.packages:
            self.done()
            return
        self.installer = None
        self.installedUpdated.emit()
        if all([p in self._installed for p in self.packages]):
            self._needRestart = True
            self.updated.emit()

    @pyqtProperty(float, constant=True)
    def scale(self):
        primary_screen = QGuiApplication.primaryScreen()
        if not primary_screen:
            return 1.0

        factor = round(primary_screen.logicalDotsPerInch() * (100/96))
        if IS_WIN:
            if factor == 125:
                return 0.82
        if IS_MAC:
            if factor == 75:
                return 1.25
        return 1.0
    
def launch(url):
    import misc
    import gui
    import sql
    import canvas
    import parameters
    import manager

    if url:
        sgnl = misc.Signaller()
        if sgnl.status():
            sgnl.send(url)
            exit()

    if IS_WIN:
        misc.setAppID(APPID)
    
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    scaling = False
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                scaling = json.load(f)["scaling"]
    except:
        pass

    if scaling:
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = Application([NAME])
    qInstallMessageHandler(qt_message_handler)
    signal.signal(signal.SIGINT, lambda sig, frame: app.quit())
    app.startTimer(100)

    app.setOrganizationName("qDiffusion")
    app.setOrganizationDomain("qDiffusion")
    app.endpoint = url
    
    engine = QQmlApplicationEngine()
    portable_qml_dir = _portable_qml_import_dir()
    if portable_qml_dir is not None:
        engine.addImportPath(str(portable_qml_dir))
    qml_warnings: list = []

    def _capture_qml_warnings(warnings_list):
        qml_warnings.extend(warnings_list)

    # PySide6 exposes QQmlEngine.warnings as a signal (not a callable method).
    # Capture warnings via the signal so failures can still be logged when
    # splash QML fails to instantiate root objects.
    engine.warnings.connect(_capture_qml_warnings)
    engine.quit.connect(app.quit)

    sql.registerTypes()
    canvas.registerTypes()
    canvas.registerMiscTypes()
    parameters.registerTypes()
    manager.registerTypes()
    misc.registerTypes()

    backend = gui.GUI(parent=app)
    app.backend = backend

    engine.addImageProvider("sync", backend.thumbnails.sync_provider)
    engine.addImageProvider("async", backend.thumbnails.async_provider)
    engine.addImageProvider("big", backend.thumbnails.big_provider)

    qmlRegisterSingletonType(gui.GUI, "gui", 1, 0, "GUI", singleton_instance_provider(backend))
    
    translator = Translator(app)
    coordinator = Coordinator(app, engine)
    app.coordinator = coordinator
    qmlRegisterSingletonType(Coordinator, "gui", 1, 0, "COORDINATOR", singleton_instance_provider(coordinator))

    app_qml_root_url = _repo_file_url(Path(QML_DIR))
    app_tabs_root_url = _repo_file_url(Path(TAB_DIR))
    startup_qml_dir_url = app_qml_root_url

    engine.rootContext().setContextProperty("APP_QML_ROOT_URL", app_qml_root_url)
    engine.rootContext().setContextProperty("APP_TABS_ROOT_URL", app_tabs_root_url)
    engine.rootContext().setContextProperty("STARTUP_QML_DIR_URL", startup_qml_dir_url)
    splash_url = _qml_file_qurl("Splash.qml")

    with open("qt_crash.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().isoformat()}] [INFO] Splash startup URL: {splash_url.toString()}\n")

    engine.load(splash_url)

    if not engine.rootObjects():
        warning_messages = "\n".join(str(warning) for warning in qml_warnings)
        timestamp = datetime.datetime.now().isoformat()
        crash_message = (
            f"GUI {timestamp}\n"
            "CRITICAL: Failed to load Splash.qml. Engine root objects is empty.\n"
            f"QML warnings:\n{warning_messages if warning_messages else '<none>'}\n\n"
        )
        with open("crash.log", "a", encoding="utf-8") as f:
            f.write(crash_message)
        print(crash_message.strip())
        app.quit()
        QCoreApplication.exit(-1)
        return -1

    if IS_WIN:
        hwnd = engine.rootObjects()[0].winId()
        misc.setWindowProperties(hwnd, APPID, NAME, LAUNCHER)

    return app.exec()

def ready():
    qmlRegisterSingletonType(_qml_file_qurl("Common.qml"), "gui", 1, 0, "COMMON")




def loadTabs(gui_backend, parent):
    from tabs.basic.basic import Basic
    from tabs.explorer.explorer import Explorer
    from tabs.gallery.gallery import Gallery
    from tabs.merger.merger import Merger
    from tabs.trainer.trainer import Trainer
    from tabs.settings.settings import Settings

    tabs = [
        Basic(parent),
        Explorer(parent),
        Gallery(parent),
        Merger(parent),
        Trainer(parent),
        Settings(parent),
    ]

    tab_sources = {
        "Generate": _tab_qml_file_url("basic", "Basic.qml"),
        "Models": _tab_qml_file_url("explorer", "Explorer.qml"),
        "History": _tab_qml_file_url("gallery", "Gallery.qml"),
        "Merge": _tab_qml_file_url("merger", "Merger.qml"),
        "Train": _tab_qml_file_url("trainer", "Trainer.qml"),
        "Settings": _tab_qml_file_url("settings", "Settings.qml"),
    }

    for tab in tabs:
        tab.source = tab_sources[tab.name]

    gui_backend.registerTabs(tabs)

def start(engine, app):
    backend = getattr(app, "backend", None)
    if backend:
        loadTabs(backend, app)
        backend.startBackendAfterStartup()

def exceptHook(exc_type, exc_value, exc_tb):
    global ERRORED
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    with open("crash.log", "a", encoding='utf-8') as f:
        f.write(f"GUI {datetime.datetime.now()}\n{tb}\n")
    print(tb)
    print("TRACEBACK SAVED: crash.log")

    if IS_WIN and os.path.exists(LAUNCHER) and not ERRORED:
        ERRORED = True
        message = f"{tb}\nError saved to crash.log"
        subprocess.run([LAUNCHER, "-e", message], **_windows_hidden_subprocess_kwargs())

    QApplication.exit(-1)

def main():
    if not os.path.exists("source"):
        os.chdir('..')

    sys.excepthook = exceptHook

    url = None
    try:
        parser = argparse.ArgumentParser(description='qDiffusion')
        parser.add_argument("url", type=str, help="remote endpoint URL", nargs='?')
        url = parser.parse_args().url
    except Exception:
        pass
    
    sys.exit(launch(url))

if __name__ == "__main__":
    main()
