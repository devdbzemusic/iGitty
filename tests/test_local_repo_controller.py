"""Tests fuer DB-first-Start und Delta-UI-Refresh des LocalRepoControllers."""

from __future__ import annotations

import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from controllers.local_repo_controller import LocalRepoController
from core.app_state import AppState
from core.logger import AppLogger
from models.repo_models import LocalRepo


def _get_or_create_application() -> QApplication:
    """
    Liefert eine vorhandene Qt-Anwendung oder erzeugt eine neue Testinstanz.
    """

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _build_local_repo(**overrides) -> LocalRepo:
    """
    Erzeugt ein lokales Repository-Testmodell mit ueberschreibbaren Defaults.
    """

    payload = {
        "name": "demo",
        "full_path": "C:/demo",
        "current_branch": "main",
        "has_remote": True,
        "remote_url": "https://github.com/dbzs/demo.git",
        "has_changes": False,
        "untracked_count": 0,
        "modified_count": 0,
        "last_commit_hash": "abc123",
        "last_commit_date": "2026-03-15T10:00:00+00:00",
        "last_commit_message": "Demo",
        "remote_status": "REMOTE_OK",
        "recommended_action": "Normal pushen",
        "state_status_hash": "hash-1",
        "available_actions": ["remove_remote"],
    }
    payload.update(overrides)
    return LocalRepo(**payload)


class FakeLocalRepoService:
    """Kleines Test-Double fuer DB-first-Load und spaetere Delta-Reads."""

    def __init__(self, cached_sequences: list[list[LocalRepo]]) -> None:
        """
        Speichert eine Folge vorbereiteter Cache-Schnappschuesse fuer aufeinanderfolgende Aufrufe.
        """

        self._cached_sequences = list(cached_sequences)

    def load_cached_repositories(self, root_path) -> list[LocalRepo]:  # noqa: ANN001
        """
        Liefert den naechsten vorbereiteten Cache-Schnappschuss.
        """

        if len(self._cached_sequences) > 1:
            return self._cached_sequences.pop(0)
        return list(self._cached_sequences[0])

    def refresh_repository(self, repo_path) -> LocalRepo | None:  # noqa: ANN001
        """
        Wird in diesem Test nicht benoetigt.
        """

        return None


class FakeWindow(QObject):
    """Minimales Fenstertestobjekt fuer Controller-Tests ohne komplettes MainWindow."""

    scan_local_requested = Signal()
    local_filter_changed = Signal(str)
    local_repo_selected = Signal(object)

    def __init__(self) -> None:
        """
        Initialisiert Signale, Statusspeicher und Protokollfelder fuer Assertions.
        """

        super().__init__()
        self._repositories: list[LocalRepo] = []
        self.populate_calls = 0
        self.upsert_calls = 0
        self.remove_calls = 0
        self.last_status = None
        self.loading_states: list[bool] = []
        self.log_lines: list[str] = []

    def populate_local_repositories(self, repositories: list[LocalRepo]) -> None:
        """
        Merkt sich einen Vollaufbau der lokalen Tabelle.
        """

        self.populate_calls += 1
        self._repositories = list(repositories)

    def upsert_local_repository(self, repository: LocalRepo) -> None:
        """
        Simuliert einen gezielten Local-Row-Update.
        """

        self.upsert_calls += 1
        for index, current in enumerate(self._repositories):
            if current.full_path == repository.full_path:
                self._repositories[index] = repository
                break
        else:
            self._repositories.append(repository)

    def remove_local_repository(self, local_path: str) -> None:
        """
        Simuliert das gezielte Entfernen einer lokalen Tabellenzeile.
        """

        self.remove_calls += 1
        self._repositories = [
            repository
            for repository in self._repositories
            if repository.full_path != local_path
        ]

    def set_local_loading(self, is_loading: bool) -> None:
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

    def set_local_filter_text(self, filter_text: str) -> None:  # noqa: ARG002
        """
        Wird im Test nicht benoetigt.
        """

    def get_local_repositories(self) -> list[LocalRepo]:
        """
        Liefert die aktuell simulierten Tabellen-Repositories.
        """

        return list(self._repositories)


class DummyJobLogRepository:
    """Leeres Test-Double fuer das Job-Logging des Controllers."""

    def add_entry(self, entry) -> None:  # noqa: ANN001
        """
        Ignoriert Job-Eintraege, weil die Controller-Tests nur UI-Verhalten pruefen.
        """


def test_local_repo_controller_bootstraps_from_state_before_background_sync(tmp_path) -> None:  # noqa: ANN001
    """
    Prueft, dass der Controller beim Start zuerst den SQLite-Cache in die UI laedt.
    """

    _get_or_create_application()
    window = FakeWindow()
    cached_repository = _build_local_repo()
    controller = LocalRepoController(
        window=window,
        local_repo_service=FakeLocalRepoService([[cached_repository]]),
        state=AppState(current_target_dir=tmp_path),
        logger=AppLogger(tmp_path / "log.txt"),
        job_log_repository=DummyJobLogRepository(),
    )

    controller.bootstrap_local_repositories()

    assert window.populate_calls == 1
    assert len(window.get_local_repositories()) == 1
    assert window.get_local_repositories()[0].full_path == "C:/demo"


def test_local_repo_controller_applies_changed_rows_without_full_repopulate(tmp_path) -> None:  # noqa: ANN001
    """
    Prueft, dass ein Background-Refresh geaenderte Repositories gezielt upsertet statt die Liste voll neu aufzubauen.
    """

    _get_or_create_application()
    window = FakeWindow()
    cached_repository = _build_local_repo(state_status_hash="hash-1", recommended_action="Normal pushen")
    changed_repository = _build_local_repo(
        state_status_hash="hash-2",
        recommended_action="Remote reparieren",
        remote_status="REMOTE_MISSING",
        available_actions=["repair_remote", "remove_remote"],
    )
    controller = LocalRepoController(
        window=window,
        local_repo_service=FakeLocalRepoService([[cached_repository], [changed_repository]]),
        state=AppState(current_target_dir=tmp_path),
        logger=AppLogger(tmp_path / "log.txt"),
        job_log_repository=DummyJobLogRepository(),
    )

    controller.bootstrap_local_repositories()
    controller._on_repositories_loaded([changed_repository])  # noqa: SLF001

    assert window.populate_calls == 1
    assert window.upsert_calls == 1
    assert window.remove_calls == 0
    assert window.get_local_repositories()[0].recommended_action == "Remote reparieren"
