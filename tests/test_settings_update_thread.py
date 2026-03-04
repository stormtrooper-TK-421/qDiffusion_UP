from __future__ import annotations

from PySide6.QtCore import QObject

from tabs.settings import settings as settings_module


class _FakeSignal:
    def __init__(self):
        self.count = 0

    def emit(self):
        self.count += 1


class _FakeCoordinator:
    def __init__(self):
        self.find_needed_calls = 0
        self.updated = _FakeSignal()

    def find_needed(self):
        self.find_needed_calls += 1


class _FakeApp(QObject):
    def __init__(self, coordinator=None):
        super().__init__()
        self.coordinator = coordinator


class _FakeGui(QObject):
    def __init__(self, app_parent):
        super().__init__(app_parent)

    def restartBackend(self):
        return None


class _FakeSettingsOwner(QObject):
    def __init__(self, app_parent):
        super().__init__(app_parent)
        self.refresh_calls = 0

    def refreshInstallerPackagePlan(self):
        self.refresh_calls += 1


def test_update_thread_resets_only_canonical_repos_and_syncs_when_inference_changes(monkeypatch):
    reset_calls = []

    monkeypatch.setattr(
        settings_module.git,
        "git_reset",
        lambda path, origin: reset_calls.append((path, origin)),
    )

    commits = {
        settings_module.git.INFER_REPO_PATH: [
            ("before-infer", "before"),
            ("after-infer", "after"),
        ]
    }

    def fake_git_last(path):
        if path in commits and commits[path]:
            return commits[path].pop(0)
        return ("root", "root")

    monkeypatch.setattr(settings_module.git, "git_last", fake_git_last)

    app = _FakeApp()
    fake_settings = _FakeSettingsOwner(app)
    update = settings_module.Update(fake_settings)

    sync_calls = {"count": 0}
    monkeypatch.setattr(update, "_sync_infer_requirements", lambda: sync_calls.__setitem__("count", sync_calls["count"] + 1))

    update.run()

    assert reset_calls == [
        (settings_module.git.ROOT_REPO_PATH, settings_module.git.QDIFF_URL),
        (settings_module.git.INFER_REPO_PATH, settings_module.git.INFER_URL),
    ]
    assert sync_calls["count"] == 1
    assert fake_settings.refresh_calls == 1


def test_update_thread_skips_sync_when_inference_commit_is_unchanged(monkeypatch):
    monkeypatch.setattr(settings_module.git, "git_reset", lambda path, origin: None)
    monkeypatch.setattr(settings_module.git, "git_last", lambda path: ("same-commit", "label"))

    app = _FakeApp()
    fake_settings = _FakeSettingsOwner(app)
    update = settings_module.Update(fake_settings)

    sync_calls = {"count": 0}
    monkeypatch.setattr(update, "_sync_infer_requirements", lambda: sync_calls.__setitem__("count", sync_calls["count"] + 1))

    update.run()

    assert update.inference_commit_changed is False
    assert sync_calls["count"] == 0
    assert fake_settings.refresh_calls == 1


def test_get_git_info_reports_both_canonical_repos_and_commit_ids(monkeypatch):
    monkeypatch.setattr(settings_module, "qmlRegisterSingletonType", lambda *args, **kwargs: None)
    responses = {
        settings_module.git.ROOT_REPO_PATH: ("1111222233334444", "root label"),
        settings_module.git.INFER_REPO_PATH: ("aaaabbbbccccdddd", "infer label"),
    }
    monkeypatch.setattr(settings_module.git, "git_last", lambda path: responses[path])

    coordinator = _FakeCoordinator()
    app = _FakeApp(coordinator)
    gui = _FakeGui(app)
    settings_obj = settings_module.Settings(gui)
    settings_obj.getGitInfo()

    assert "GUI repo (.) commit 111122223333" in settings_obj.gitInfo
    assert "Inference repo (source/sd-inference-server) commit aaaabbbbcccc" in settings_obj.gitServerInfo
    assert settings_obj.needRestart is False


def test_refresh_installer_package_plan_invokes_coordinator_find_needed(monkeypatch):
    monkeypatch.setattr(settings_module, "qmlRegisterSingletonType", lambda *args, **kwargs: None)
    coordinator = _FakeCoordinator()
    app = _FakeApp(coordinator)
    gui = _FakeGui(app)
    settings_obj = settings_module.Settings(gui)

    settings_obj.refreshInstallerPackagePlan()

    assert coordinator.find_needed_calls == 1
    assert coordinator.updated.count == 1
