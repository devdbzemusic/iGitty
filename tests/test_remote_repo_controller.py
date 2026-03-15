"""Tests fuer DB-first-Start und Delta-UI-Refresh des RemoteRepoControllers."""

from __future__ import annotations

import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from controllers.remote_repo_controller import RemoteRepoController
from core.app_state import AppState
from core.logger import AppLogger
from models.repo_models import RateLimitInfo, RemoteRepo


def _get_or_create_application() -> QApplication:
    """
    Liefert eine vorhandene Qt-Anwendung oder erzeugt eine neue Testinstanz.
    """

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _build_remote_repo(**overrides) -> RemoteRepo:
    """
    Erzeugt ein Remote-Repository-Testmodell mit ueberschreibbaren Standardwerten.
    """

    payload = {
        "repo_id": 7,
        "name": "demo",
        "full_name": "dbzs/demo",
        "owner": "dbzs",
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "archived": False,
        "fork": False,
        "clone_url": "https://github.com/dbzs/demo.git",
        "ssh_url": "git@github.com:dbzs/demo.git",
        "html_url": "https://github.com/dbzs/demo",
        "description": "Demo",
        "updated_at": "2026-03-10T10:00:00Z",
        "available_actions": ["set_private"],
        "state_status_hash": "hash-1",
    }
    payload.update(overrides)
    return RemoteRepo(**payload)


class FakeRemoteRepoService:
    """Kleines Test-Double fuer DB-first-Load und spaetere Delta-Reads."""

    def __init__(self, cached_sequences: list[list[RemoteRepo]]) -> None:
        """
        Speichert eine Folge vorbereiteter Cache-Schnappschuesse fuer aufeinanderfolgende Aufrufe.
        """

        self._cached_sequences = list(cached_sequences)

    def load_cached_repositories(self) -> list[RemoteRepo]:
        """
        Liefert den naechsten vorbereiteten Cache-Schnappschuss.
        """

        if len(self._cached_sequences) > 1:
            return self._cached_sequences.pop(0)
        return list(self._cached_sequences[0])

    def upsert_cached_repository(self, repository: RemoteRepo) -> RemoteRepo:
        """
        Gibt fuer Einzelupdates direkt das uebergebene Repository zurueck.
        """

        return repository

    def sync_repositories(self):  # noqa: ANN001
        """
        Wird in diesen Controller-Tests nicht benoetigt.
        """

        raise AssertionError("sync_repositories sollte in diesem Test nicht direkt aufgerufen werden.")


class FakeWindow(QObject):
    """Minimales Fenstertestobjekt fuer Remote-Controller-Tests ohne komplettes MainWindow."""

    refresh_remote_requested = Signal()
    remote_filter_changed = Signal(str)
    clone_requested = Signal()
    remote_repo_action_requested = Signal(object, str)

    def __init__(self) -> None:
        """
        Initialisiert Signale, Statusspeicher und Protokollfelder fuer Assertions.
        """

        super().__init__()
        self._repositories: list[RemoteRepo] = []
        self.populate_calls = 0
        self.upsert_calls = 0
        self.remove_calls = 0
        self.last_status = None
        self.loading_states: list[bool] = []
        self.log_lines: list[str] = []

    def populate_remote_repositories(self, repositories: list[RemoteRepo]) -> None:
        """
        Merkt sich einen Vollaufbau der Remote-Tabelle.
        """

        self.populate_calls += 1
        self._repositories = list(repositories)

    def upsert_remote_repository(self, repository: RemoteRepo) -> None:
        """
        Simuliert einen gezielten Remote-Row-Update.
        """

        self.upsert_calls += 1
        for index, current in enumerate(self._repositories):
            if current.repo_id == repository.repo_id:
                self._repositories[index] = repository
                break
        else:
            self._repositories.append(repository)

    def remove_remote_repository(self, repo_id: int) -> None:
        """
        Simuliert das gezielte Entfernen einer Remote-Tabellenzeile.
        """

        self.remove_calls += 1
        self._repositories = [
            repository
            for repository in self._repositories
            if repository.repo_id != repo_id
        ]

    def set_remote_loading(self, is_loading: bool) -> None:
        """
        Merkt sich den sichtbaren Ladezustand fuer Assertions.
        """

        self.loading_states.append(is_loading)

    def update_status(self, status) -> None:  # noqa: ANN001
        """
        Merkt sich den letzten UI-Status-Snapshot.
        """

        self.last_status = status

    def append_log_line(self, message: str) -> None:
        """
        Sammelt Logzeilen fuer spaetere Assertions.
        """

        self.log_lines.append(message)

    def set_remote_filter_text(self, filter_text: str) -> None:  # noqa: ARG002
        """
        Wird im Test nicht benoetigt.
        """

    def get_remote_repositories(self) -> list[RemoteRepo]:
        """
        Liefert die aktuell simulierten Tabellen-Repositories.
        """

        return list(self._repositories)


class DummyGitHubService:
    """Einfaches Test-Double fuer den benoetigten GitHub-Login im Statusbereich."""

    def __init__(self) -> None:
        """
        Initialisiert den festen Test-Login.
        """

        self.last_authenticated_login = "devdbzemusic"


class DummyCloneService:
    """Leeres Test-Double fuer den Clone-Service."""


class DummyRemoteVisibilityService:
    """Leeres Test-Double fuer den Visibility-Service."""


class DummyJobLogRepository:
    """Leeres Test-Double fuer das Job-Logging des Controllers."""

    def add_entry(self, entry) -> None:  # noqa: ANN001
        """
        Ignoriert Job-Eintraege, weil die Controller-Tests nur UI-Verhalten pruefen.
        """

    def add_action_record(self, result) -> None:  # noqa: ANN001
        """
        Ignoriert Aktionshistorie, weil diese Tests nur den Delta-Refresh pruefen.
        """


def test_remote_repo_controller_bootstraps_from_state_before_background_sync(tmp_path) -> None:  # noqa: ANN001
    """
    Prueft, dass der Controller beim Start zuerst den SQLite-Cache in die UI laedt.
    """

    _get_or_create_application()
    window = FakeWindow()
    cached_repository = _build_remote_repo()
    controller = RemoteRepoController(
        window=window,
        remote_repo_service=FakeRemoteRepoService([[cached_repository]]),
        github_service=DummyGitHubService(),
        clone_service=DummyCloneService(),
        remote_visibility_service=DummyRemoteVisibilityService(),
        state=AppState(current_target_dir=tmp_path),
        logger=AppLogger(tmp_path / "log.txt"),
        job_log_repository=DummyJobLogRepository(),
    )

    controller.bootstrap_remote_repositories()

    assert window.populate_calls == 1
    assert len(window.get_remote_repositories()) == 1
    assert window.get_remote_repositories()[0].repo_id == 7


def test_remote_repo_controller_applies_changed_and_removed_rows_without_full_repopulate(tmp_path) -> None:  # noqa: ANN001
    """
    Prueft, dass ein Background-Refresh geaenderte Remote-Repositories gezielt upsertet und entfernte loescht.
    """

    _get_or_create_application()
    window = FakeWindow()
    cached_repository = _build_remote_repo(state_status_hash="hash-1", available_actions=["set_private"])
    changed_repository = _build_remote_repo(
        visibility="private",
        available_actions=["set_public"],
        state_status_hash="hash-2",
    )
    controller = RemoteRepoController(
        window=window,
        remote_repo_service=FakeRemoteRepoService([[cached_repository], [changed_repository], []]),
        github_service=DummyGitHubService(),
        clone_service=DummyCloneService(),
        remote_visibility_service=DummyRemoteVisibilityService(),
        state=AppState(current_target_dir=tmp_path),
        logger=AppLogger(tmp_path / "log.txt"),
        job_log_repository=DummyJobLogRepository(),
    )

    controller.bootstrap_remote_repositories()
    controller._on_repositories_loaded([changed_repository], RateLimitInfo())  # noqa: SLF001
    controller._on_repositories_loaded([], RateLimitInfo())  # noqa: SLF001

    assert window.populate_calls == 1
    assert window.upsert_calls == 1
    assert window.remove_calls == 1
    assert window.get_remote_repositories() == []
